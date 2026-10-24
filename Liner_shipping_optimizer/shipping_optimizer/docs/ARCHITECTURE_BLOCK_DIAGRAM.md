# System Architecture - Block Diagrams of the Present Working Configuration

AI Vessel Routing System (hierarchical multi-agent GA + MILP liner-shipping network design)

| Item | Value |
|---|---|
| Written | 2026-10-17 |
| Code state | git `HEAD` `47bbdb9` + uncommitted working tree (see `COST_REVENUE_PROFIT_FORMULATION.md`, header) |
| Companion document | `docs/COST_REVENUE_PROFIT_FORMULATION.md` (all cost / revenue / profit formulas and assumptions) |
| Basis | Every box below was traced to a source file that was read (Section 11 lists them). Where a box exists in the code but is switched off in this configuration it is drawn dashed / marked `[OFF]`. |
| Figures | Fig. 1 is plain ASCII (renders anywhere, copy-paste safe). Figs. 2-9 are Mermaid (render on GitHub/GitLab, VS Code Markdown preview, Obsidian, mermaid.live). |

**Reading key.** `[C3]` = switched on by the C3 flag set; `[DEFAULT]` = on in the code defaults; `[OFF]` = present in code, off in this configuration; `[LLM]` = a step that calls a language model and has a deterministic fallback; `{TRUST}` = a boundary that defines which numbers may be reported.

---

## 0. One-paragraph description

Five tab-separated LINERLIB files are loaded once, with the FFE -> TEU unit conversion applied at the loader boundary, into a single `Problem`. An **Orchestrator** clusters the ports (k-means, 3 clusters for 47 ports), splits the demand by origin into three disjoint regional problems and runs a bounded feedback loop of exactly three iterations. In each iteration three **Regional Agents** run in parallel threads: they generate a pool of candidate service rotations, filter it, select services and frequencies with a two-level genetic algorithm that uses a *surrogate* economy, and allocate cargo with a MILP. Their results are then **discarded as economic truth**: a **global reconciliation stage** unites all regional candidate pools and solves **one** network design MILP (services, integer weekly frequencies, vessels, cargo flows) over the whole demand, improves it by exact-LP local search, flow re-optimisation and (if needed) profit-floor repair, and hands the plan to an **independent ledger** that recomputes revenue, every cost item and every constraint from the raw data alone. Only ledger-verified figures are reported. A **Coordinator** turns the verified numbers into feedback signals, an **Iteration Selector** picks the best of the three iterations (Pareto + deterministic score), and the result is written to `pipeline_output.json`, which a FastAPI backend and a React dashboard present. Language models are used for narrative text, candidate-mix hints, weight suggestions and iteration choice - always behind validators with rule-based fallbacks - and never inside the ledger.

---

## Fig. 1 - Master block diagram (ASCII)

```
+==================================================================================================+
| L7  PRESENTATION / SERVICE                                                                       |
|     React 18 + Vite + Tailwind + d3-geo  (frontend/)                                             |
|        runtimeAdapter normalises /pipeline_output.json and WebSocket events                      |
|             ^  HTTP /api/*  +  WebSocket /ws  (live stage events)                                |
|     FastAPI backend (backend/unified_main.py, routes/, pipeline_streamer, websocket_manager)     |
|        real_orchestrator_integration.py  --> starts the OrchestratorAgent with a stream callback |
+============================================^=====================================================+
                                             | pipeline_output.json (root + frontend/public), sqlite
+============================================|=====================================================+
| L6  ORCHESTRATION (src/agents/orchestrator_agent.py)                                             |
|                                                                                                  |
|   analyze_problem [LLM] -> PortClustering (k-means, k=3 for <50 ports)                           |
|        -> RegionalSplitter (demand by ORIGIN only: disjoint, zero duplication)                   |
|                                                                                                  |
|   FOR iteration = 0,1,2   (MIN = MAX = 3)                                                        |
|     +-----------------------------------------------------------------------------------------+  |
|     | (a) 3 x RegionalAgent in parallel threads  ----------------------> candidate pools, hints |  |
|     | (b) GLOBAL RECONCILIATION  {TRUST}  ----------> verified network_ledger + regional split  |  |
|     | (c) CoordinatorAgent  ---> conflicts, evaluation, decisions, feedback signals            |  |
|     | (d) ConsensusEngine + SharedContext ---> validated weight / policy update                 |  |
|     | (e) iteration snapshot (metrics, services, network_ledger)                                |  |
|     | (f) stop if (iteration+1 >= 3) AND no rerun needed; else apply feedback, next iteration   |  |
|     +-----------------------------------------------------------------------------------------+  |
|   IterationSelector (Pareto dominance + weighted score; LLM proposal validated) -> final result  |
|   executive summary [LLM, rule-based fallback]                                                   |
+==========+=====================================================================+=================+
           |                                                                     |
           v                                                                     v
+---------------------------------------------------+   +--------------------------------------+
| L5  REGIONAL STAGE  (x3, parallel)                |   | L4  GLOBAL RECONCILIATION STAGE      |
|  src/agents/regional_agent.py                     |   |  src/network/reconcile.py            |
|                                                   |   |                                      |
|  HubDetector -> strategy text [LLM]               |   |  union of regional pools             |
|  ServiceGeneratorAgent                            |   |   (dedupe: canonical rotation+class) |
|    A direct  B hub loops  C hub trunks            |   |  + trunk candidates          [C3]    |
|    D feeders E heuristic  F demand-coherent loops |   |  + class variants           [OFF]    |
|    G route operators / elitism [OFF]              |   |            |                         |
|    + per-rotation class screening (k=1)           |   |            v                         |
|  regional ECONOMIC filter (cap, stand-alone econ.)|   |  NetworkPlanner.plan                 |
|  HierarchicalGA                                   |   |   1 build_service_model  (economics) |
|    ServiceGA  (binary chromosome, surrogate)      |   |   2 build_paths  (transit-limited)   |
|    FrequencyGA (integer departures, surrogate)    |   |   3 solve_network (CBC)              |
|  HubMILP = NetworkPlanner with FIXED frequencies  |   |       LP relaxation -> bound         |
|  explanation text [LLM]; regional policy validate |   |       support cap 105 [C3] + VUB [C3]|
|                                                   |   |       integer MILP, 120 s stage      |
|  outputs: last_candidate_pool, last_milp_result   |   |   4 local search (exact LP)  [C3]    |
|           (frequencies used only as a MILP hint)  |   |   5 flow re-optimisation LP          |
|                                                   |   |   6 profit-floor repair (if < 0)     |
|  regional economics are SUPERSEDED by L4          |   |   7 compute_ledger {TRUST}           |
+---------------------------------------------------+   |   8 reconcile MILP vs ledger         |
           |  pools + hints                              |  partition to regions (sum = global) |
           +-------------------------------------------> |  strategy_report                     |
                                                         +------------------+-------------------+
                                                                            |
+===========================================================================|======================+
| L3  CANONICAL ECONOMICS AND NETWORK MODEL (src/network/)                  v                      |
|   economics.py  ServiceModel: T, vessels = ceil(T f / 7), fuel, port-call, hire                  |
|   physical_rules.py  draft + canal rules       bunker_prices.py  600 USD/t uniform [DEFAULT]     |
|   paths.py  OD paths, <= 2 transfers, end-to-end TransitTime enforced                           |
|   network_milp.py  objective = operating profit      flow_reopt.py   local_search.py            |
|   ledger.py  INDEPENDENT recomputation (does not import the service model or the MILP) {TRUST}  |
|   metrics.py  canonical decision-layer economics (revenue, all-in cost, profit, margin band)     |
|   assumption_register.py   solve_semantics.py (what "Optimal" does / does not prove)             |
+==========================================================^=======================================+
                                                           |
+==========================================================|=======================================+
| L2  DATA LAYER                                           |                                       |
|   src/data/network_loader.py   validate + convert once: FFEPerWeek x2, Revenue /2, Capacity x2,  |
|                                per-FFE port costs /2, blank canal fee -> None                    |
|   dataset_registry.py, problem_json.py (canonical JSON proven identical to the CSV-built Problem)|
|   Problem(ports, demands, distance_matrix + canal_flags + edge_draft, fleet, services=[])        |
+==========================================================^=======================================+
                                                           |
+==========================================================|=======================================+
| L1  RAW DATA   data/raw/WorldSmall/ (tab-separated)      |                                       |
|   ports.csv (47)  Demand_WorldSmall_Fixed_Sep.csv (1764 ODs)  dist_dense.csv (2162 directed pairs)|
|   fleet_data.csv (6 classes)  fleet_WorldSmall.csv (263 vessels)                                 |
|   optional [OFF]: data/pricing/bunker_snapshot_*.json    data/maritime/snapshots/                |
+==================================================================================================+

  CROSS-CUTTING
  +--------------------------------------------------------------------------------------------+
  | LLM SUBSYSTEM  src/llm/: llm_client -> ProviderRouter (role -> model, cache, circuit breaker,|
  |   provider switch, hard fallback) -> OpenRouter | Groq | Cerebras | Google; ActuationLedger  |
  | VALIDATION     archetype_validator, regional_policy_validator(_v2), weight_validator,        |
  |   consensus_engine - an LLM suggestion is accepted only after validation, else rule-based    |
  | MARITIME INTELLIGENCE [OFF]  maritime/optimizer_bridge: weather speed factor, port-capacity   |
  |   override (only when MARITIME_INTELLIGENCE_ENABLED=1)                                      |
  | TELEMETRY      health_tracker, shared_context, structured logger, actuation records         |
  +--------------------------------------------------------------------------------------------+
```

---

## Fig. 2 - Layered architecture (Mermaid)

```mermaid
flowchart TB
  subgraph UI["L7 Presentation and service"]
    FE["React 18 + Vite dashboard<br/>runtimeAdapter, map, regions, console"]
    BE["FastAPI backend<br/>REST /api/*, WebSocket /ws"]
  end

  subgraph ORC["L6 Orchestration - OrchestratorAgent"]
    AN["Problem analysis (LLM text)"]
    CL["PortClustering k-means, k = 3"]
    SP["RegionalSplitter, demand by origin"]
    LOOP["Feedback loop, exactly 3 iterations"]
    SEL["IterationSelector<br/>Pareto + deterministic score"]
  end

  subgraph REG["L5 Regional stage x3 parallel"]
    RA["RegionalAgent"]
  end

  subgraph GLB["L4 Global reconciliation"]
    RC["reconcile: union of pools,<br/>one NetworkPlanner solve"]
  end

  subgraph DEC["Decision layer"]
    CO["CoordinatorAgent"]
    CE["ConsensusEngine + validators"]
    SC["SharedContext"]
  end

  subgraph NET["L3 Canonical economics and network model"]
    EC["economics: ServiceModel"]
    PA["paths: OD paths"]
    MI["network_milp: CBC"]
    PO["local search, flow re-opt, repair"]
    LG["ledger: independent recomputation"]
  end

  subgraph DAT["L1-L2 Data"]
    LD["NetworkLoader: unit boundary FFE to TEU"]
    RAW["data/raw/WorldSmall"]
  end

  subgraph LLM["Cross-cutting: LLM subsystem"]
    RT["ProviderRouter"]
    PR["OpenRouter / Groq / Cerebras / Google"]
  end

  RAW --> LD --> AN
  FE <--> BE
  BE <--> LOOP
  AN --> CL --> SP --> LOOP
  LOOP --> RA
  RA -->|candidate pools, hints| RC
  RC --> EC --> PA --> MI --> PO --> LG
  LG -->|verified network_ledger| RC
  RC -->|verified, additive regional numbers| CO
  CO --> CE --> SC
  SC -->|weights, priorities| LOOP
  LOOP --> SEL
  SEL -->|pipeline_output.json| BE
  AN -.-> RT
  RA -.-> RT
  CO -.-> RT
  SEL -.-> RT
  RT --> PR
```

---

## Fig. 3 - Data layer and the unit boundary (Mermaid)

```mermaid
flowchart LR
  subgraph F["data/raw/WorldSmall (tab-separated)"]
    P["ports.csv<br/>CostPerFULL, CostPerFULLTrnsf,<br/>PortCallCostFixed, PortCallCostPerFFE, Draft"]
    D["Demand_WorldSmall_Fixed_Sep.csv<br/>FFEPerWeek, Revenue_1, TransitTime"]
    X["dist_dense.csv<br/>Distance nm, IsPanama, IsSuez, Draft"]
    FQ["fleet_WorldSmall.csv<br/>Quantity"]
    FS["fleet_data.csv<br/>Capacity FFE, TC rate, speeds,<br/>bunker t/day, idle t/day, canal fees"]
  end

  NL["NetworkLoader<br/>schema + range validation<br/>dataset identity guard"]
  CONV["Unit boundary - applied ONCE<br/>quantities x 2 (demand, capacity)<br/>per-FFE rates / 2 (revenue, port costs)<br/>blank canal fee = None"]
  PJ["problem_json (canonical JSON)<br/>hash-identical to CSV-built Problem"]
  PB["Problem<br/>ports, demands, services = empty,<br/>distance_matrix + canal_flags + edge_draft, fleet"]

  P --> NL
  D --> NL
  X --> NL
  FQ --> NL
  FS --> NL
  NL --> CONV --> PB
  CONV --> PJ
  PJ -. "proven identical at run start" .-> PB
```

---

## Fig. 4 - One iteration, in time order (Mermaid sequence)

```mermaid
sequenceDiagram
  autonumber
  participant O as Orchestrator
  participant R as RegionalAgent x3
  participant G as Global stage (reconcile)
  participant L as Independent ledger
  participant C as Coordinator
  participant K as ConsensusEngine / SharedContext
  participant S as IterationSelector

  O->>O: split problem (3 regions, demand by origin)
  par three regions in parallel
    O->>R: process(regional Problem)
    R->>R: generate candidates, filter, ServiceGA, FrequencyGA
    R->>R: HubMILP with fixed frequencies
    R-->>O: regional result + candidate pool + frequency hints
  end
  O->>G: pools, hints, region_of_od, 120 s budget
  G->>G: union pools, trunk candidates (C3)
  G->>G: service models, OD paths, LP relaxation, integer MILP
  G->>G: local search (C3), flow re-optimisation, repair
  G->>L: services, frequencies, routed flows only
  L-->>G: revenue, cost items, profit, violations
  G->>G: MILP profit equals ledger profit? (tolerance 1e-6)
  G-->>O: network_ledger (verified flag) + regional split (sum = global)
  O->>C: regional results + network_ledger
  C-->>O: conflicts, evaluation, decisions, feedback (rerun?)
  O->>K: coordinator weights + regional policies
  K-->>O: validated weight adjustments
  O->>O: snapshot iteration, apply feedback to Problem
  Note over O: repeat until 3 iterations are complete
  O->>S: three snapshots
  S-->>O: selected iteration (Pareto + score)
  O-->>O: final result from the selected snapshot only
```

---

## Fig. 5 - Regional agent internals (Mermaid)

```mermaid
flowchart TB
  IN["Regional Problem<br/>own ports, origin-owned demands,<br/>port_catalog = all ports"]
  HD["HubDetector: top-5 hubs"]
  ST["Strategy text<br/>(LLM, rule-based fallback)"]

  subgraph GEN["ServiceGeneratorAgent - candidate pool"]
    A["A direct services, top corridors"]
    B["B hub loop services"]
    Cc["C hub-to-hub trunks"]
    Dd["D feeders, spoke to best hub"]
    E["E heuristic base pool"]
    F["F demand-coherent loops<br/>budget 60, 3-5 ports [DEFAULT]"]
    G["G route operators, elitism [OFF]"]
    SCR["Feasibility screen: evaluate_rotation<br/>+ class screening k = 1, time-feasible class"]
    AR["Archetype mix hints<br/>(LLM, validated)"]
  end

  FLT["Regional ECONOMIC filter<br/>cap by stand-alone economics<br/>[DEFAULT]"]

  subgraph HGA["HierarchicalGA"]
    PF["Pre-filter: modellable services on a demand corridor"]
    SGA["ServiceGA: binary chromosome<br/>surrogate fitness, fleet-repair"]
    FGA["FrequencyGA: integer departures<br/>surrogate margin, inventory repair"]
  end

  HM["HubMILP = NetworkPlanner.plan<br/>fixed frequencies, ledger inside"]
  EX["Explanation text<br/>(LLM, rule-based fallback)"]
  PV["Regional policy validator"]
  OUT["Result dict + last_candidate_pool + last_milp_result"]

  IN --> HD --> ST
  IN --> GEN
  AR -.-> GEN
  A --> SCR
  B --> SCR
  Cc --> SCR
  Dd --> SCR
  E --> SCR
  F --> SCR
  G -.-> SCR
  SCR --> FLT --> PF --> SGA --> FGA --> HM --> OUT
  HM --> EX --> PV --> OUT
```

---

## Fig. 6 - Global reconciliation stage and network planner (Mermaid)

```mermaid
flowchart TB
  POOLS["Regional candidate pools<br/>+ frequency hints (MILP warm start only)"]
  UN["Union and de-duplicate<br/>key = canonical rotation + vessel class"]
  TK["Trunk candidates [C3]<br/>12 per under-subscribed class,<br/>diverse set cover, up to 10 ports"]
  CV["Class variants [OFF]"]

  subgraph PLAN["NetworkPlanner.plan"]
    M1["1 build_service_model per candidate<br/>reject: missing distance or port record,<br/>draft, canal not passable, no price"]
    M2["2 build_paths per OD<br/>direct, 1 transfer, 2 transfers (if needed)<br/>end-to-end TransitTime enforced<br/>10 fastest per OD enter the MILP"]
    M3["3 solve_network (CBC, 120 s stage)"]
    M3a["LP relaxation: bound + LP-support services"]
    M3b["support cap 105 [C3]<br/>VUB inequality [C3]"]
    M3c["integer MILP: f, n, q, u<br/>max profit"]
    M4["4 local search [C3]<br/>exact LP: add, drop, freq +-1"]
    M5["5 flow re-optimisation LP<br/>all valid paths of operated services"]
    M6["6 profit-floor repair<br/>only if profit below 0"]
    M7["7 compute_ledger<br/>independent recomputation"]
    M8["8 reconcile<br/>MILP profit vs ledger profit"]
  end

  PART["Partition to regions<br/>revenue and cargo charges by origin region,<br/>service costs to one owner region"]
  BLOCK["network_ledger block<br/>weekly_usd, demand_teu_per_week, plan,<br/>optimality, assumptions, register, strategy_report"]

  POOLS --> UN --> M1
  TK --> M1
  CV -.-> M1
  M1 --> M2 --> M3
  M3 --> M3a --> M3b --> M3c
  M3c --> M4 --> M5 --> M6 --> M7 --> M8
  M8 --> PART --> BLOCK
```

---

## Fig. 7 - Trust boundaries: what may enter a reported number (Mermaid)

```mermaid
flowchart LR
  subgraph HEUR["Heuristic / advisory zone - may change WHICH plan is explored, never HOW it is priced"]
    GA["GA surrogates<br/>ServiceGA, FrequencyGA"]
    SCREEN["Stand-alone screens<br/>class screening, trunk, regional filter"]
    LLMX["LLM text, archetype hints,<br/>weight and iteration suggestions"]
    COORD["Coordinator feedback<br/>coverage 70 percent, profit floor 0"]
  end

  subgraph SOLVE["Optimisation zone"]
    PL["Candidate pool"]
    MILP["Network MILP + local search<br/>+ flow re-optimisation + repair"]
  end

  subgraph TRUST["TRUST zone - the only source of reported numbers"]
    SM["economics.ServiceModel<br/>(prices the plan inside the optimiser)"]
    LED["ledger.compute_ledger<br/>(re-derives everything from raw files,<br/>does not import the service model or the MILP)"]
    CHK["Checks: fleet inventory, leg capacity,<br/>demand conservation, transit time,<br/>draft, canal, path validity"]
    REP["Reported: revenue, 6 cost items,<br/>profit, margin, coverage"]
  end

  GA --> PL
  SCREEN --> PL
  LLMX -.-> PL
  PL --> MILP
  SM --> MILP
  MILP -->|services, frequencies, flows| LED
  LED --> CHK --> REP
  REP --> COORD
  COORD -.->|weights, rerun| PL
```

---

## Fig. 8 - Agents, LLM subsystem and fallbacks (Mermaid)

```mermaid
flowchart TB
  subgraph AG["Agents (src/agents/)"]
    ORCH["OrchestratorAgent<br/>role: orchestrator"]
    REGA["RegionalAgent x3<br/>role: regional"]
    SVC["ServiceGeneratorAgent<br/>role: service_generator"]
    COORDA["CoordinatorAgent<br/>role: coordinator, iteration_selector"]
  end

  CLIENT["llm_client (single entry)"]
  subgraph ROUTER["ProviderRouter (src/llm/providers/)"]
    MAP["role to per-provider model"]
    CACHE["response cache"]
    CB["circuit breaker + provider switch"]
    HF["hard fallback record"]
  end
  subgraph PROV["Providers"]
    P1["OpenRouter"]
    P2["Groq"]
    P3["Cerebras"]
    P4["Google"]
  end

  VAL["Validators<br/>archetype, regional policy, weights,<br/>consensus engine, iteration-selection contract"]
  RULE["Deterministic rule-based fallbacks<br/>(text templates, default policy,<br/>Pareto + weighted score)"]
  ACT["ActuationLedger + provider telemetry<br/>(decision_source = llm or rule-based)"]

  ORCH --> CLIENT
  REGA --> CLIENT
  SVC --> CLIENT
  COORDA --> CLIENT
  CLIENT --> MAP --> CACHE --> CB
  CB --> P1
  CB --> P2
  CB --> P3
  CB --> P4
  CB --> HF
  CLIENT --> VAL
  VAL -->|accepted| AG
  VAL -->|rejected or unavailable| RULE --> AG
  CLIENT --> ACT
```

---

## Fig. 9 - Runtime and deployment view (Mermaid)

```mermaid
flowchart LR
  USER["Analyst browser"]
  subgraph FEA["frontend/ (Vite dev server)"]
    VIEWS["views: console, overview, regions,<br/>map, maritime panels"]
    RA2["runtimeAdapter<br/>RUNTIME_TRUTH_URL = /pipeline_output.json"]
    WS["websocketManager"]
  end
  subgraph BEA["backend/ (FastAPI + uvicorn)"]
    API["REST: /api/health, status, metrics,<br/>regions, iterations, corridors, history"]
    WSS["WebSocket /ws and /pipeline"]
    STR["pipeline_streamer + real_orchestrator_integration"]
  end
  subgraph CORE["src/ (Python 3.11)"]
    ORC2["OrchestratorAgent.process"]
  end
  subgraph OUTS["Artifacts"]
    PO["pipeline_output.json<br/>(repo root and frontend/public)"]
    DB["optimization_results.db (sqlite)"]
    REP2["reports/ evidence folders"]
  end
  subgraph REF["Reference runner (evidence runs)"]
    TO["tests/test_orchestrator.py<br/>applies C3 flags, writes dataset_run block"]
  end

  USER --> VIEWS --> RA2
  RA2 -->|fetch| PO
  VIEWS --> WS <--> WSS
  API --- DB
  STR --> ORC2
  WSS --- STR
  ORC2 --> PO
  TO --> ORC2
  TO --> REP2
```

---

## 10. Component table

| Block | Responsibility | Main source files |
|---|---|---|
| Loader / unit boundary | validate tab-separated sources; FFE -> TEU once; dataset identity guard | `src/data/network_loader.py`, `dataset_registry.py`, `dataset_validation.py`, `problem_json.py` |
| Orchestrator | analysis, clustering, split, 3-iteration loop, feedback, selection, final aggregation | `src/agents/orchestrator_agent.py` |
| Decomposition | k-means port clusters; origin-only demand split | `src/decomposition/port_clustering.py`, `regional_splitter.py` |
| Regional agent | per-region candidate generation, GA, HubMILP | `src/agents/regional_agent.py` |
| Candidate generation | sections A-G, feasibility, class screening, demand-coherent loops | `src/agents/service_generator_agent.py`, `src/services/*` |
| Regional filter | economic cap of the pool | `src/services/regional_filter.py` |
| GA | two-level surrogate search | `src/optimization/hierarchical_ga.py`, `service_ga.py`, `frequency_ga.py`, `normalization.py`, `adaptive_budget.py` |
| Canonical model | service physics and cost, OD paths, MILP, ledger | `src/network/economics.py`, `paths.py`, `network_milp.py`, `ledger.py`, `physical_rules.py`, `bunker_prices.py` |
| Planner | models -> paths -> MILP -> post-solve -> ledger | `src/network/plan.py` |
| Post-solve | local search, flow re-optimisation, repair | `src/network/local_search.py`, `flow_reopt.py` |
| Global stage | union pools, trunk candidates, planner, regional partition | `src/network/reconcile.py`, `trunk_candidates.py`, `class_variants.py` |
| Decision metrics | canonical economics for coordinator/selector; advisory margin band | `src/network/metrics.py` |
| Coordinator | conflicts, evaluation, decisions, feedback | `src/agents/coordinator_agent.py` |
| Consensus / validation | weight and policy validation | `src/validation/*` |
| Iteration selection | scorecards, Pareto, deterministic or validated-LLM choice | `src/pipeline/iteration_selection.py` |
| LLM subsystem | client, router, providers, actuation telemetry | `src/llm/*`, `src/llm/providers/*` |
| Reporting / audit | assumption register, solve semantics, strategy report, paper-comparison ledger | `src/network/assumption_register.py`, `solve_semantics.py`, `strategy_report.py`, `src/benchmark/*` |
| Service + UI | REST, WebSocket, dashboard | `backend/*`, `frontend/src/*` |
| Optional | maritime intelligence (weather, port capacity) | `maritime/*` (default OFF) |

## 11. Controlling parameters visible in the diagrams

| Parameter | Value in this configuration | Where |
|---|---|---|
| Clusters / regional agents used | 3 (`n_clusters = 3 if ports < 50 else 5`); 5 agents are constructed, the first `n_clusters` are used | `orchestrator_agent.py:666-670, 760` |
| Iterations | 3 (`MIN_ITERATIONS = MAX_ITERATIONS = 3`) | `orchestrator_agent.py:33-34` |
| Global stage budget | 120 s (`GLOBAL_STAGE_TIME_LIMIT_SEC`); 15 s of it reserved for local search [C3] | `orchestrator_agent.py:355`, `local_search.py:61` |
| Rerun triggers | coverage < 70 %, profit < 0, any overlap conflict | `coordinator_agent.py` |
| ServiceGA / FrequencyGA | population and generations from `AdaptiveBudget`; hard runtime cap 90 s each; `HierarchicalGA(max_runtime_sec=55)` is a warning threshold | `adaptive_budget.py`, `service_ga.py:36`, `frequency_ga.py:36` |
| Paths | 10 per OD into the MILP, <= 2 transfers | `paths.py:57, 61` |
| Solver | PuLP 2.7.0, CBC 2.10.3, single thread | `network_milp.py`, stored `dataset_run.solver` |
| Reference timing (stored run) | 818.8 s for the 3-iteration pipeline; final-iteration planner stage 105.8 s (model + paths 5.5, MILP 92.1, local search 7.4, flow re-opt 0.8, ledger 0.02) | `pipeline_output.json` |

## 12. Notes a reader of the diagram should know

1. **Region labels are positional.** `RegionalAgent`s are constructed as Asia, Europe, Americas, Middle East, Africa, but with 47 ports only the first three are used and cluster `i` is simply handed to agent `i`. K-means cluster numbering is arbitrary, so the labels do not guarantee that "Asia" is geographically Asia. They do not affect the economics (the global stage re-solves the whole network); they affect only how results are grouped and named.
2. **Regional economics are not final.** The regional GA + HubMILP produce candidate pools and frequency *hints*. The numbers shown per region after each iteration are the global ledger partitioned back to regions (`sum(regions) == global`).
3. **Three iterations are always run.** Convergence is suppressed until three candidates exist; the Iteration Selector then chooses among them (stored run: iteration 2 of {0,1,2}; profits 30.2 M, 40.9 M, 45.0 M USD/week).
4. **GA objectives are surrogates.** In `profit_first` mode the Coordinator's weight adjustments do not enter the ServiceGA fitness (they act only in `legacy` mode); the fitness uses fixed profit_first weights. The GA affects which candidates the regional stage hints, while the global MILP chooses and the ledger prices.
5. **Legacy modules are kept.** `*_legacy.py` files in `src/optimization/` and `src/utils/` are preserved verbatim for traceability and are not on the execution path. Experimental modules `dual_screen`, `targeted_paths`, `trunk_lanes` were moved to `archive/experimental_not_retained_2026-10-15/` and are not in the diagram.
6. **Two backend entry files** (`backend/main.py`, `backend/unified_main.py`) have the same FastAPI skeleton; the diagram shows the unified one. The evidence runs behind the reported figures use the reference runner `tests/test_orchestrator.py` (it applies the C3 flags and writes the `dataset_run` block), not the web backend.
7. **Other datasets.** The same architecture runs `baltic`, `WAF`, `World-500`, `World-1000` through the dataset registry (`docs/MULTI_DATASET.md`); only the data layer (L1/L2) changes.
8. **Rendering.** All eight Mermaid figures were rendered without error with `@mermaid-js/mermaid-cli` 11.4.2. Ready-to-insert vector files and their sources are in `docs/figures_architecture/` (`fig2.svg` ... `fig9.svg`, `fig2.mmd` ... `fig9.mmd`; the number is the figure number above). Fig. 1 (ASCII) has no image file; redraw it in a drawing tool for a paper if a block figure with boxes is needed. Fig. 2's automatic layout is functional but not typeset for print.
