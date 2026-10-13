# PROJECT X — Runtime Knowledge Graph

**Companion artifact to `RUNTIME_BIBLE.md`** · every node = a real runtime entity (agent, optimizer, object, dataset, validator, context, feedback, output); every edge = the actual relationship (calls / creates / reads / writes / owns / passes / consumes / returns).

Only active-runtime entities are nodes; shipped-but-dead items are listed separately at the end (marked `(dead)`), so the graph reflects what actually executes.

---

## 1. Master Runtime Knowledge Graph

```mermaid
flowchart TD
    %% ── ENTRY & DATA ──
    DRIVER["tests/test_orchestrator.py::test_orchestrator\n(json.dump :1696)"]
    DS["data/datasets/large_shipping_problem.json\n333 ports / 9622 demands"]
    NL["NetworkLoader.load_network"]
    P["Problem\n(333, 9622, services=[])"]
    DRIVER --> NL --> P
    POP[("pipeline_output.json")] -->|"json.dump(result)"| DRIVER

    %% ── ORCHESTRATOR ──
    ORCH["OrchestratorAgent.process"]
    P -->|owns/reads| ORCH
    ORCH -->|calls| AN["analyze_problem\n<small>LLM &#124; fallback</small>"]
    ORCH -->|calls| PC["PortClustering.cluster_ports"]
    PC -->|returns| CLU["clusters dict"]
    ORCH -->|calls| RS["RegionalSplitter.split"]
    RS -->|returns| RPR["regional_problems\n<small>deepcopy(Problem) × n</small>"]
    ORCH -. "SharedContext(from scratch)" .-> SC["SharedContext"]
    HT["health_tracker (singleton)"] -.-> ORCH

    %% ── ITERATION LOOP ──
    subgraph LOOP["for iteration in range(MAX_ITERATIONS=3)"]
        RPR -->|submit → thread pool| RA["RegionalAgent.process × n"]
        RA -->|returns| RR["regional_results[]"]
        RR -->|reads| CO["CoordinatorAgent.process"]
        CO -->|reads| LLM["LLMClient.chat\n<small>OpenCode endpoint</small>"]
        LLM -->|parses| DEC["decisions + feedback"]
        DEC -->|reads| RW["WeightValidator"]
        CO -->|reads| LAT["..result dict"]
        RR -->|reads| CE["ConsensusEngine.process"]
        DEC -->| "coordinator_decision"| CE
        CE -->|returns| CR["consensus_result\n<small>previous_consensus @ :608</small>"]
        CR -->|writes| Pw["problem.\nprofit/coverage/cost_weight"]
        ORCH -->|rebuilds| SH["SharedContext\n+update_hub_strategy"]
        DEC -->| feedback | STOP{"needs_rerun ?\ncoverage-gain≥1.0 ?"}
        STOP -->|yes| ARF["_apply_feedback\n<small>mutates problem</small>"]
        ARF --> RPR
        STOP -->|no| AGG["aggregate_results"]
    end

    %% ── REGION INTERNALS ──
    contextORCH -.-> LOOP
    RA -->|hub detection| HD["HubDetector.detect_hubs"]
    RA -->|calls| SGA["ServiceGeneratorAgent.generate_services"]
    SGA -->|calls| CSG["CandidateServiceGenerator"]
    CSG -->|returns| CS["candidate_services[]"]
    SGA --> SAT["..archetype_params"]
    RA -->|filters| FLS["_filter_services → kept"]
    RA -->|calls| HGA["HierarchicalGA.run"]
    HGA -->|fitness uses| SVCGA["ServiceGA (ObjectiveWeights)"]
    HGA -->|fitness uses| FREQGA["FrequencyGA"]
    HGA -->|returns| CHR["chromosome dict\n{services, frequencies, coverage_est, skip_milp}"]
    CHR -->|constructor| MILP["HubMILP(sub, chromosome).solve"]
    MILP -->|solver| CBR["PuLP PULP_CBC_CMD"]
    MILP -->|returns| SEL["selected_services"]
    SEL -->|merge by id :472| RR

    %% ── AGGREGATION / SUMMARY ──
    RR --> AGG["aggregate_results"]
    AGG --> MET["summary_metrics\n(cover = demand-weighted)"]
    AGG --> EXSU["executive_summary\n<small>deterministic, no LLM</small>"]
    MET -->|to keys| ORCH2["llm_runtime_metrics"]
    AGG -->|269| POP2["selected_services (509)"]

    %% ── OUTPUT CONSUMPTION ──
    POP -->|read| REND["/api/pipeline-output (server.py:326)"]
    POP -->|WS| WSE["/ws/pipeline (server.py)"]
    REND -->|<small>normalize</small>| DASH["React dashboard"]

    %% styling
    style POP fill:#4a4,color:#fff
    style LOOP fill:#ddd
    style LLM fill:#66f,color:#fff
    style MILP fill:#f90
```

---

## 2. Edge Catalog (all relationships, with evidence)

|Edge|From|To|Relationship|Evidence|
|---|---|---|---|---|
|E1|test driver|NetworkLoader|calls `load_network`|tests/test_orchestrator.py:1577|
|E2|load_network|Problem|creates|tests/test_orchestrator.py:103-139|
|E3|test driver|OrchestratorAgent.process|calls|tests/test_orchestrator.py:1608|
|E4|process|analyze_problem|calls|orchestrator_agent.py:343|
|E5|process|cluster_ports|calls|orchestrator_agent.py:363|
|E6|cluster_ports|clusters dict|returns|port_clustering.py:27-90|
|E7|process|split|calls|orchestrator_agent.py:411|
|E8|split|regional_problems|returns|regional_splitter.py:56-93|
|E9|process|RegionalAgent.process (×n)|submits to thread pool|orchestrator_agent.py:434|
|E10|RegionalAgent|ServiceGeneratorAgent|calls|regional_agent.py (process)|
|E11|ServiceGeneratorAgent|CandidateServiceGenerator|calls|service_generator_agent.py|
|E12|ServiceGeneratorAgent|candidate_services[]|returns|svc_gen ~:244|
|E13|RegionalAgent|`_filter_services`|calls|regional_agent.py:191|
|E14|RegionalAgent|HierarchicalGA.run|calls (no arg)|regional_agent.py:197-208|
|E15|HierarchicalGA|ServiceGA / FrequencyGA|calls (fitness)|hierarchical_ga.py|
|E16|HierarchicalGA|chromosome dict|returns|hierarchical_ga.py:208-214|
|E17|RegionalAgent|HubMILP(sub, chromosome)|constructs|hub_milp.py:34|
|E18|HubMILP|optimized services|returns|hub_milp.py:530-541|
|E19|RegionalAgent|regional_results[]|stores|orchestrator_agent.py:446|
|E20|process|CoordinatorAgent.process|calls|orchestrator_agent.py:512|
|E21|CoordinatorAgent|LLMClient.chat|calls|coordinator_agent.py:381|
|E22|CoordinatorAgent|decisions + feedback|returns|coordinator_agent.py:95-106|
|E23|process|ConsensusEngine.process|calls|orchestrator_agent.py:602|
|E24|ConsensusEngine|consensus_result → _previous_consensus|returns/stores|orchestrator_agent.py:608|
|E25|process|problem.profit/coverage/cost_weight|writes|orchestrator_agent.py:610-615|
|E26|process|SharedContext (rebuild)|creates|orchestrator_agent.py:633-647|
|E27|process|SharedContext.update_hub_strategy|calls|orchestrator_agent.py:648|
|E28|process|iteration_audit|appends|orchestrator_agent.py:561|
|E29|process|break (stop)|control|orchestrator_agent.py:671-696|
|E30|process|`_apply_feedback` → problem|mutates|orchestrator_agent.py:703|
|E31|process|aggregate_results|calls|orchestrator_agent.py:715|
|E32|aggregate_results|summary_metrics|returns|orchestrator_agent.py:730-738|
|E33|process|executive_summary|builds|orchestrator_agent.py:801-817|
|E34|process|llm_runtime_metrics|builds|orchestrator_agent.py:850-886|
|E35|test driver|pipeline_output.json|json.dump|tests/test_orchestrator.py:1696|
|E36|pipeline_output.json|backend REST|reads|backend/server.py:326-335|
|E37|pipeline_output.json|backend WS|reads|backend/server.py:343|
|E38|backend|React dashboard|serves (normalize)|frontend runtimeAdapter|

---

## 3. Region-internal data flow (Phase 9 trace)

```text
RegionalAgent.process (regional_agent.py:87-474)
   ├─ HubDetector.detect_hubs            → hubs (regional_agent.py:112, :390)
   ├─ ServiceGeneratorAgent.generate_services  → candidate_services[]  (svc_gen:244)
   ├─ normalize + region-prefix          → regional service ids      (regional_agent.py:169-187)
   ├─ _filter_services                   → kept list (filters)       (regional_agent.py:191)
   ├─ HierarchicalGA.run()               → chromosome dict           (hierarchical_ga.py:208-214)
   │     └─ fitness: ServiceGA (ObjectiveWeights, service_ga.py:347) + FrequencyGA
   ├─ HubMILP(sub, chromosome).solve()   → optimized selected_services (hub_milp.py:34, :530-541)
   └─ dedup/merge by service id          → result["selected_services"] (regional_agent.py:278-305, :472)
```

> **Critical contract:** `HierarchicalGA.run()` returns keys `services`, `frequencies`, `coverage_estimate`, `skip_milp`. Only `services` + `frequencies` are consumed by `HubMILP` (via constructor). `coverage_estimate` and `skip_milp` are **written but never read** → the MILP runs unconditionally.

---

## 4. Node → Neighbor Lookup (quick answers)

|Question|Answer|
|---|---|
|Who writes `problem.profit/coverage/cost_weight`?|orchestrator :311-313 (CONFIG), :612-614 (consensus), `_apply_feedback` :254-256|
|Who reads `candidate_services`?|RegionalAgent `_filter_services` (:191) and HierarchicalGA (as chromosome basis)|
|Who reads `selected_services`?|CoordinatorAgent conflict detection (:211-237), orchestrator aggregation (:824-828)|
|Who owns `clusters`?|`process()` frame (read-only after clustering)|
|Who owns `regional_problems`?|`process()` frame — fresh deepcopy each iteration|
|Who owns `problem`?|the caller (test driver), passed by reference and **mutated**|
|Who owns `_previous_consensus`?|OrchestratorAgent (self) — **cross-iteration state**|
|Who owns `health_tracker`?|module singleton|
|Who owns `logger`?|module singleton (structlog)|
|Who consumes `pipeline_output.json`?|backend REST + WS + React dashboard|
|Who consumes `SharedContext`?|only final serialization (:901) — **rebuilt each iteration, no persistence**|

---

## 5. Dead / Orphan Nodes (Black Boxes, written but never read)

|Entity|Status|Evidence|
|---|---|---|
|`chromosome.coverage_estimate`|created, never read|hierarchical_ga.py:211-213|
|`chromosome.skip_milp`|created, never read|hierarchical_ga.py:211-213|
|`FlowOptimizer.compute_metrics()`|never called|flow_optimizer.py|
|`summary_prompt` (orchestrator)|built, never sent|orchestrator_agent.py:763-789|
|`llm_success` counter|never incremented|coordinator_agent.py:33|
|`regional_metrics.py` / `regional_policy_mapping.py`|not reachable from runtime path|src/agents/|
|`graph_builder.py` / `preprocess.py`|zero callers|src/data/|
|GA `seed_chromosome` / `seed_solution` args|never passed|hierarchical_ga.py:141,153; service_ga.py:459|
|`final_archetype_params` (consensus)|computed, not applied|consensus_engine.py|
|`service_archetype_plan` (SharedContext)|never populated|shared_context.py:122|

---

*End of Runtime Knowledge Graph — companion to `RUNTIME_BIBLE.md`. Every edge cites real `file:line`.*
