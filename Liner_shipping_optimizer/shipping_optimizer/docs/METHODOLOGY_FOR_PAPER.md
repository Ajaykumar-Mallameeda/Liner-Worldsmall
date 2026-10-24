# Methodology — Hierarchical Multi-Agent Liner Network Design (paper draft text)

| Item | Value |
|---|---|
| Written | 2026-10-18 |
| Basis | (1) the core source code of the present working configuration (`src/`, `tests/test_orchestrator.py`); (2) `docs/COST_REVENUE_PROFIT_FORMULATION.md` and `docs/ARCHITECTURE_BLOCK_DIAGRAM.md`, which are the text sources of `Cost_Revenue_Profit_Formulation.pdf` and `System_Architecture_Diagram.pdf`; (3) `docs/MULTI_DATASET.md` and the benchmark driver `Benchmark/run_benchmark.py`. |
| How it was checked | Every statement in Part B was compared with the code: constants, the MILP rows, the ledger's imports, the coordinator thresholds, the selection weights and the C3 flag set. Part C lists each claim with the file that supports it. The two PDFs could not be machine-read in this environment (no PDF library); they were treated as renderings of the two Markdown files of the same titles, which were written first. **Please skim the PDFs once yourselves and confirm that nothing was edited only there.** |

---

## Part A — Notes for the authors (not paper text)

1. **Originality.** The prose in Part B was composed for this document from the code and from the project's own formulation notes. It is not copied from a paper. I cannot certify that a text is "plagiarism-proof": run it through your institution's similarity checker (iThenticate / Turnitin) after you adapt it, and keep the citations of Part A.5 attached to the statements they support.
2. **Wording that comes from the benchmark sources.** The data semantics (what a column means, a 24-hour port stay, a 48-hour minimum transshipment time, the 600 USD/t bunker price) originate in the LINERLIB benchmark and its authors' material. Paraphrase them and cite them; do not present them as your own findings.
3. **What is a claim and what is an assumption.** The model contains modelling conventions without a published source (3.5-day expected transfer wait, integer vessel counts, a single design-speed operating point). Part B states them as assumptions on purpose. Keep them as assumptions.
4. **No optimality claim.** The solver is time-limited. The code itself refuses to call a result optimal (`src/network/solve_semantics.py`). Do not write "optimal" in the paper; write "ledger-verified feasible plan".
5. **References to add (verify the bibliographic details before use).**
   - LINERLIB benchmark suite and its base integer programming model: Brouer, Alvarez, Plum, Pisinger, Sigurd, *A base integer programming model and benchmark suite for liner-shipping network design*, Transportation Science, 2014.
   - The reinforcement-learning liner-network paper that the project compares against (arXiv:2411.09068, Dutta, Lin, Jin; cited in the code as the source of the paper-comparison ledger).
   - PuLP and the COIN-OR CBC solver (PuLP 2.7.0, CBC 2.10.3 in the stored runs).
   - Whatever you cite for k-means and for genetic algorithms.
6. **LLM availability during the benchmark.** Part of the 20-seed benchmark ran while the language-model provider was rate-limited, so the language-model steps used their rule-based fallbacks (each run records how many calls failed). Section B.10 explains why this does not touch the economic numbers, but a reviewer will ask. Decide how you disclose it; the per-seed count is stored in each `*_benchmark_summary.json` under `per_seed[].llm_failed_call_lines`.
7. **Result numbers are not in this file.** The benchmark was still running when this was written. Fill the results section from `Benchmark/<dataset>/<dataset>_benchmark_summary.json`.

---

## Part B — Methodology (paper text)

### B.1 Problem setting

We consider the design of a liner-shipping network for a single carrier over one steady-state operating week. The inputs are a set of ports, a set of origin–destination (OD) demand records, a directed distance matrix, and a heterogeneous owned fleet. The carrier chooses which cyclic **services** to operate, how many weekly departures each runs, how many vessels each needs, and how the cargo of each OD is routed over the resulting network, possibly with up to two transshipments. The objective is weekly **operating profit**: cargo revenue minus vessel hire, fuel, port-call, cargo-handling and transshipment cost. Coverage (the share of demand carried) is an outcome that is reported, not an objective term; unserved cargo is neither rewarded nor penalised in the final network.

The problem couples combinatorial service selection, integer frequency and fleet decisions, and a multi-commodity flow. Exact solution over all conceivable rotations is out of reach, so the method (i) generates a bounded pool of candidate services, (ii) solves one network-design mixed-integer program over the whole pool, and (iii) prices the resulting plan with an accounting module that shares no code with the optimiser.

### B.2 Data model and unit normalisation

Each dataset is a package of five tab-separated tables: ports (with draft and four cost fields), OD demand (weekly volume in forty-foot-equivalent units, revenue per unit, maximum transit time), directed distances (with canal and draft attributes), the fleet class table (capacity, hire rate, design speed, fuel use at sea and in port, canal fees) and the fleet inventory per class.

All unit conversion happens once, in the loader, so that no downstream stage converts again: one forty-foot unit equals two twenty-foot units (TEU); quantities are multiplied by two and per-unit rates are divided by two, which keeps the product of volume and rate unchanged for every record. A blank canal fee is read as "this class cannot pass", not as zero. When the distance file lists several routes for a directed pair, the model uses one record per pair (the first listed, which was verified to be the shortest). Each run loads a canonical JSON form of the dataset and proves, field by field, that it equals the problem built directly from the tables; both hashes are stored with the run.

Five datasets are used: three LINERLIB instances (a global network with 47 ports, a Baltic regional network and the WAF regional network; **describe WAF's geography from the LINERLIB documentation, which this project's files do not state**) and two synthetic networks of 500 and 1000 ports. The synthetic networks were generated by a deterministic procedure calibrated on LINERLIB statistics (anchor ports, lognormal cost dispersion, a sparse gravity demand model, a demand-calibrated fleet); they are benchmarks for scale, not observations, and their distances are approximations.

### B.3 Overview of the system

The system is a hierarchical multi-agent pipeline with a deliberately narrow trust boundary. A master **Orchestrator** decomposes the problem and runs a fixed three-iteration feedback loop. In every iteration, **Regional Agents** work in parallel on disjoint sub-problems and return *candidate services and frequency hints*. A **global reconciliation stage** then discards the regional economics, merges all candidates and solves one network-design MILP over the whole demand. An **independent ledger** recomputes revenue and every cost item from the raw data. A **Coordinator** converts the verified figures into feedback, and an **Iteration Selector** picks the best of the three iterations. Language models appear only in advisory roles behind validators (B.10).

The design principle is separation of *search* from *valuation*: heuristic and learned components may change which plans are explored, but never how a plan is priced.

### B.4 Decomposition

Ports are grouped by k-means on their coordinates, with three clusters when the instance has fewer than fifty ports and five otherwise. Demand is split by **origin** only, so the regional sub-problems are disjoint and no demand is duplicated; every region keeps the full port catalogue so that routes can leave its own cluster. Regions are labelled positionally and the labels carry no geographic guarantee; they affect only how results are grouped, because the global stage re-solves the entire network.

### B.5 Regional agents: candidate generation and surrogate search

Each Regional Agent produces a pool of candidate services in several families: direct services on the strongest corridors, hub loops, hub-to-hub trunks, feeders from spokes to their best hub, a heuristic base pool, and demand-coherent loops of three to five ports. Each candidate rotation passes a physical feasibility screen (distances and port records present, draft limits, canal passability for the vessel class, a bunker price available) and a per-rotation class screen that keeps a time-feasible vessel class. A stand-alone economic filter then caps the pool.

A two-level genetic algorithm searches within the pool: a service-level algorithm with a binary chromosome selects services, and a frequency-level algorithm with an integer chromosome chooses weekly departures, with repair operators for fleet inventory. Both use a **surrogate** economy, a simplified profit estimate with direct-only cargo sharing and no transshipment term, so their fitness is a search guide and not a valuation. A regional MILP with fixed frequencies completes the regional step. What the region contributes downstream is its candidate pool and its frequency hints (used only as a warm start); its own profit figure is superseded.

### B.6 Global reconciliation and the network-design MILP

The regional pools are merged and de-duplicated by canonical rotation and vessel class, and a set of **trunk candidates** is added: for every under-subscribed vessel class, twelve class-forced long rotations of up to ten ports, chosen as a diverse set cover.

**Service model.** For service $s$ of class $c$ with ports $p_1,\dots,p_n$ (closed rotation), the rotation time is
$$T_s=\Big\lceil \sum_{(a,b)\in\text{legs}} \frac{D(a,b)}{24\,v_c} + n\,\tfrac{H}{24}\Big\rceil \text{ days},$$
with design speed $v_c$ and port stay $H=24$ h. With $f_s$ weekly departures the service needs $N_s=\lceil T_s f_s/7\rceil$ vessels and offers $\mathrm{cap}_c f_s$ TEU of capacity on every leg. Rounding $T_s$ up and counting whole vessels is conservative by construction.

**Paths.** For every OD, valid paths use one to three service segments (at most two transfers). A path is admitted only if its end-to-end transit time (sailing days of the legs ridden, one port stay at each intermediate port, and a dwell of $M/24+W=5.5$ days at every transfer) is within the OD's limit. The ten fastest paths per OD enter the integer model.

**Formulation.** Let $f_s,n_s\in\mathbb Z_{\ge0}$ be departures and vessels, $q_k\ge0$ the TEU routed on path $k$ of OD $d(k)$, and $u_d\ge0$ the unserved volume.
$$\max\;\sum_k (r_{d(k)}-\pi_k)\,q_k\;-\;\sum_s\big[7\,TC_{c(s)}\,n_s+(F_s+G_s)\,f_s\big]\;-\;\lambda\sum_d u_d$$
subject to
$$\sum_{k\in d}q_k+u_d=Q_d\ \ \forall d;\qquad \sum_{k\ni(s,l)}q_k\le \mathrm{cap}_{c(s)}f_s\ \ \forall s,l;\qquad 7n_s\ge T_sf_s\ \ \forall s;\qquad \sum_{s\in c}n_s\le N_c\ \ \forall c.$$
Here $r_d$ is revenue per TEU, $\pi_k$ the per-TEU path charge (handling at origin and destination plus transshipment at each hub), $F_s$ the fuel cost of one rotation, $G_s$ the port-call fixed, port-capacity and canal charge of one rotation, $TC_c$ the daily hire rate, $Q_d$ the OD volume, $N_c$ the class inventory. The penalty weight $\lambda$ is zero in the global stage, so the objective equals operating profit. A strengthening inequality $q_k\le Q_{d(k)}f_s$ for every service on a path is added; it removes no integer-feasible point.

**Solution procedure.** The linear relaxation yields an upper bound valid for the capped model and a set of services with positive frequency (the LP support). The integer problem keeps at most 105 support services and is solved with CBC under a 120-second stage budget, of which 15 seconds are reserved for local search. The raw solver status is never reported as optimal; the stage reports a gap to its own bound and states that the final plan is not comparable to that bound as evidence of optimality.

### B.7 Post-solution improvement

Three steps follow, each keeping the plan valid. (i) **Local search**: add, drop and ±1-frequency moves, each move evaluated by solving the exact cargo LP for the resulting configuration. (ii) **Flow re-optimisation**: with frequencies and vessels fixed, an LP re-routes cargo over *all* valid time-feasible paths of the operated services, not only the ten used in the integer model, and replaces the flows only if the margin improves. (iii) **Profit-floor repair**: only when profit is negative, the worst loss-making services are switched off and cargo is re-routed.

### B.8 Independent ledger and trust boundary

The reported profit comes from a ledger that receives only the plan (which services run, at what frequency, which TEU rode which segments) and recomputes everything from the raw distance matrix, fleet and port records. Its module imports only the Python standard library, so it shares no code with the service model or the MILP. It evaluates

$$\Pi = R - \big(C_{\text{vessel}}+C_{\text{fuel}}+C_{\text{port-call}}+C_{\text{handling}}+C_{\text{transshipment}}\big),$$
where $C_{\text{port-call}}$ contains the fixed per-call charge, the per-capacity port charge and canal fees. Fuel is the sum, over services, of $f_s$ times the fuel burnt per rotation (sea days times the sea rate plus port days times the idle rate) times a uniform price of 600 USD/t. Handling is charged at origin and destination only; transshipment replaces the discharge-and-reload at a hub.

The ledger also checks fleet inventory per class, leg capacity, demand conservation, transit-time limits, draft and canal feasibility, and path validity. The optimiser's own profit is compared with the ledger's; if they differ by more than a tight tolerance the plan is not marked verified. Only verified figures are reported, and the figures are additive over regions: revenue and cargo charges go to the origin region, and every service's cost goes to exactly one region by a deterministic rule, so the regional figures sum to the network total.

### B.9 Coordination, feedback and iteration selection

The Coordinator receives the verified regional and global figures, detects conflicts (service overlaps), evaluates each region and issues feedback. A rerun is requested if regional coverage is below 70 %, profit is not above zero, or a conflict exists; these are targets and advisories, not constraints of the optimiser. A consensus engine and a shared context validate weight and policy updates before they are applied. Exactly three iterations are always run: convergence is suppressed until three candidates exist, so that the selector always chooses among three.

The Iteration Selector filters the three snapshots by Pareto dominance over profit, demand-weighted coverage, total cost, unserved volume, loss-making regions, violations and conflicts, and then ranks the non-dominated ones by a fixed weighted score of normalised profit (0.60), coverage (0.25) and total cost (0.15). The final result is taken from the selected snapshot only.

### B.10 Role of the language models

Language models are used for narrative text, archetype hints for the candidate mix, weight suggestions and an iteration-choice proposal. Each use sits behind a validator and has a deterministic rule-based fallback; the provider layer routes by role, caches responses, trips a circuit breaker on repeated errors and records, for every decision, whether it came from a model or from the rule. No model output enters the service model, the MILP, the local search, the flow LP or the ledger, so reported profit, cost and coverage do not depend on model availability. (The candidate mix and weight hints can, in principle, change which plans are explored; this is the one channel through which model availability could influence outcomes, and it is why each run stores the number of failed model calls.)

### B.11 Experimental protocol

**Configuration.** All experiments use one frozen configuration ("C3"): the strengthening inequality on, local search on, twelve diverse trunk candidates per class with at most ten ports, and the 105-service support cap, on top of the defaults described above (flow re-optimisation and profit-floor repair on; 120-second global stage; single-threaded CBC). The reference runner `tests/test_orchestrator.py` applies these settings itself; the benchmark driver adds only a seed and a fixed hash seed and changes nothing else.

**Seeds and runs.** Each dataset is run twenty times, with seeds 0 to 19, strictly one run after another in a fresh process, with the same code, data and solver settings. Each run writes its full result and a flat metrics record.

**Metrics.** Weekly profit, revenue and total cost; the five cost items; coverage (served over total demand TEU); number of services and departures per week; vessels assigned, idle and the deployment ratio (assigned over owned); productive load factor (carried over offered TEU-legs); profit per assigned vessel; model size; the solver's gap to its own bound; and runtime (global solver phase, pipeline, wall clock).

**Statistics.** For every metric we report minimum, maximum, mean, median, sample standard deviation and sample variance over the runs that produced a result, plus the coefficient of variation. Variance across seeds is taken as the measure of sensitivity to the stochastic components (the genetic algorithms and the time-limited solver).

### B.12 Limitations

(1) The plans are feasible and ledger-verified but not proven optimal; the optimum is over a candidate pool, not over all rotations. (2) Several inputs are assumptions: the uniform bunker price, the port stay, the expected transfer wait, the reading of per-unit port costs and the single design-speed operating point. (3) The objective is profit only; coverage is an outcome. (4) Whole-vessel counting is more conservative than fractional counting. (5) The genetic algorithms use a surrogate economy that can mis-rank candidates, which affects exploration, not the price of a given plan. (6) Synthetic datasets test scale, not realism. (7) Runtimes depend on the machine, and on model-call latency where the language-model layer is reachable.

---

## Part C — Claim-to-code map (for verification, not for the paper)

| Statement | Where it is established |
|---|---|
| Three iterations, always | `src/agents/orchestrator_agent.py` lines 33–34, 721, 1028 |
| 3 clusters below 50 ports, else 5 | `orchestrator_agent.py` line 667 |
| 120 s global stage budget | `orchestrator_agent.py` line 355 |
| C3 flag set | `tests/test_orchestrator.py` lines 3149–3155 |
| MILP objective and rows (demand, leg capacity, vessels, fleet, strengthening inequality) | `src/network/network_milp.py` lines 378–420 |
| Ten paths per OD, at most two transfers | `src/network/paths.py` lines 57, 91 |
| Ledger imports only the standard library | `src/network/ledger.py` lines 27–32 |
| Profit reconciliation tolerance | `src/network/plan.py` line 409 |
| Coverage target 70 %, profit floor 0 | `src/agents/coordinator_agent.py` lines 19–20 |
| Selection weights 0.60 / 0.25 / 0.15 and Pareto filter | `src/pipeline/iteration_selection.py` lines 12–14, 78–80 |
| Language-model roles (orchestrator, regional, service generator, coordinator, iteration selector) | `src/agents/*.py` (`llm_role`) |
| All cost, revenue and unit formulas, assumptions and their status | `docs/COST_REVENUE_PROFIT_FORMULATION.md` sections 3–8, 13 |
| Layered architecture and trust boundary | `docs/ARCHITECTURE_BLOCK_DIAGRAM.md` Fig. 1, 6, 7 |
| Dataset registry and synthetic generation | `docs/MULTI_DATASET.md`; `scripts/multi_dataset/generate_synthetic.py` |
| Benchmark protocol (20 seeds, sequential, statistics) | `Benchmark/run_benchmark.py` |
