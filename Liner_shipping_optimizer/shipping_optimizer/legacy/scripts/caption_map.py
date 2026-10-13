#!/usr/bin/env python3
"""
Caption and explanation mapping for all Mermaid diagrams.
Maps document + diagram index to descriptive captions and explanations.
"""

# Each entry: (section_context, descriptive_caption, technical_explanation)
# The map is: doc_name -> diagram_index (1-based) -> (caption, explanation)

MERMAID_CAPTIONS = {
    "MASTER_TECHNICAL_DOCUMENTATION_V2": {
        # graph LR - Liner Network Structure, §2.2
        1: (
            "Hub-and-Spoke and Hybrid Network Topologies",
            "This diagram illustrates the two primary network topology models used in liner shipping: "
            "hub-and-spoke (left) and hybrid (right). In the hub-and-spoke model, feeder ports connect "
            "exclusively to a central hub (e.g., Hub A serving Feeders 1-4), concentrating cargo for "
            "inter-hub trunk services. The hybrid model supplements this with direct port-to-port links "
            "(D1-D2) alongside traditional hub-and-spoke connections (H2-F1). The system dynamically "
            "selects between these topologies per region based on demand concentration: high-density "
            "corridors receive more direct services, while low-density peripheries use feeder-hub "
            "routing. This topology selection is performed by the RegionalAgent's LLM strategy "
            "generation step, which classifies each region as Type A (dense-direct), Type B (balanced), "
            "or Type C (hub-dominant)."
        ),
        # gantt - Project Evolution, §3.1
        2: (
            "Project Evolution Timeline",
            "This Gantt chart traces the chronological development of the AI Vessel Routing System "
            "across six major phases spanning approximately two years. Phase P established the LLM "
            "prompt auditing and certification framework. Phase A implemented the agent activation "
            "sprint covering orchestrator, coordinator, regional, and service generator agents with "
            "LLM integration. Phase B extended the system with validators, archetype parameter "
            "generation, and regional metrics. Phase C added the ConsensusEngine for multi-agent "
            "reconciliation using weighted voting. Phase D focused on frontend visualization and "
            "dashboard state management. Phase 1.0 represents the current release candidate, "
            "incorporating fleet constraint analysis, MILP solver tuning, and comprehensive regression "
            "testing. The gantt reflects actual implementation milestones, not planned dates."
        ),
        # flowchart TB - Data Flow, §5.1
        3: (
            "End-to-End Data Pipeline: CSV Ingestion to Dashboard Visualization",
            "This flowchart traces the complete data path from raw CSV files through the multi-stage "
            "optimization pipeline to the frontend dashboard. Four input files (ports.csv, demand.csv, "
            "fleet.csv, distance.csv) are loaded by NetworkLoader into dataclass instances (Port, "
            "Demand, Fleet, DistanceMatrix), which compose a Problem object passed to the "
            "OrchestratorAgent. The orchestrator decomposes the problem into five regional sub-problems "
            "via K-means clustering (k=5) on geographic coordinates. Each RegionalAgent independently "
            "executes service generation (LLM-guided), service filtering (profitability gate), "
            "HierarchicalGA optimization (ServiceGA + FrequencyGA), and HubMILP flow optimization "
            "(PuLP/CBC solver, 120s time limit). The CoordinatorAgent aggregates results, detects "
            "inter-regional conflicts, and generates feedback signals. The ConsensusEngine reconciles "
            "competing weight adjustments through weighted voting (coordinator 0.4, regional 0.4, "
            "service generator 0.2). Final results are serialized to pipeline_output.json, which "
            "the FastAPI backend serves to the React dashboard via REST endpoints and WebSocket events."
        ),
        # flowchart TB - GA, §10.1
        4: (
            "Genetic Algorithm Optimization: Service Selection and Frequency Optimization",
            "This flowchart details the HierarchicalGA optimization pipeline. The ServiceGA operates "
            "on a binary chromosome (0/1 per candidate service), with a population of 80 initialized "
            "via demand-proportional sampling. Fitness is computed as w_p * normalized_profit + "
            "w_c * normalized_coverage - w_k * normalized_cost, with penalties for capacity "
            "overcommit, negative-margin services, and unserved demand. Elite selection retains the "
            "top 10 individuals via heapq. Single-point crossover and demand-biased mutation (50% "
            "high-demand activation, 50% random flip) provide genetic diversity. Early termination "
            "triggers after 8 generations without improvement or 90 seconds elapsed, whichever "
            "occurs first. The FrequencyGA then takes the selected service set and optimizes integer "
            "frequencies (0-3 sailings/week) with a fleet constraint of 300 vessels maximum. "
            "Both GAs are implemented with numpy arrays for performance, not external GA libraries."
        ),
        # graph TB - AI Layer, §11.1
        5: (
            "Multi-Agent AI Layer: Orchestrator, Coordinator, and Regional Agent Architecture",
            "This diagram shows the three-tier agent hierarchy. The OrchestratorAgent (903 lines, "
            "src/agents/orchestrator_agent.py) functions as the master controller, managing the "
            "complete optimization lifecycle across up to three iterations. It creates five "
            "RegionalAgent instances (one per geographic region: Asia, Europe, Americas, Middle East, "
            "Africa), one CoordinatorAgent for global decision-making, one ConsensusEngine for "
            "weighted reconciliation, and a SharedContext for cross-agent state. The LLMClient "
            "(src/llm/client.py) provides OpenAI-compatible API access with MD5-cached responses, "
            "a circuit breaker (5 failures = 60s timeout), and a fallback chain through five "
            "model providers. Each RegionalAgent runs independently in a ThreadPoolExecutor "
            "(max_workers=5), executing service generation, GA optimization, and MILP solving. "
            "The CoordinatorAgent detects service overlaps across regions and resolves conflicts "
            "by dropping lower-profit services."
        ),
        # graph TB - Backend Architecture, §13.2
        6: (
            "Backend FastAPI Module Architecture and Service Composition",
            "This diagram maps the backend server architecture with three application entry points "
            "(main.py, unified_main.py, server.py), each defining a FastAPI application on port 8000. "
            "The server modules expose REST endpoints (/api/health, /api/status, /api/metrics, "
            "/api/regions, /api/iterations, /api/corridors, /api/export, /api/optimize) and "
            "WebSocket endpoints (/ws or /ws/pipeline). The ws_manager.py module handles WebSocket "
            "connection lifecycle with 19 typed event schemas defined in event_schemas.py. The "
            "routes/ subpackage (metrics.py, pipeline.py, regions.py, websocket.py) defines "
            "additional APIRouter endpoints that are defined but not registered in any server "
            "instance. The services layer (optimization_service.py, pipeline_service.py) bridges "
            "the backend API to the src/ core via real_orchestrator_integration.py. The "
            "pipeline_streamer.py module provides service-level event streaming for long-running "
            "optimization processes."
        ),
        # graph TB - Frontend Architecture, §14.2
        7: (
            "Frontend React Component Hierarchy and Dashboard Architecture",
            "This diagram shows the complete React component tree. MaritimeDashboard.jsx is the "
            "single-page application entry point wrapped in an ErrorBoundary class component. "
            "State management is handled by the useOptimizationState custom hook (useState + "
            "useCallback), not Redux or Zustand (both listed in package.json but unused). The "
            "hook connects to apiClient.js (fetch-based REST client with 7 endpoints) and "
            "websocketManager.js (event-driven pub/sub handling 12 event types). Data normalization "
            "is performed by runtimeAdapter.js converting all backend snake_case to JavaScript "
            "camelCase. The 14 main views are switched via renderMain() function: Landing, "
            "Overview (KpiCard x6 + WorldMap), FleetDashboard, RouteTable, PortPanel, PipelineView, "
            "Regional Intelligence, FeedbackView, FunnelView, ConflictView, WorldMap, "
            "ScenarioWorkspace, ExportPanel, and SummaryView with BackendCertification."
        ),
        # sequenceDiagram - Runtime, §16.2
        8: (
            "Runtime WebSocket Event Sequence Across Three Optimization Iterations",
            "This sequence diagram traces the message flow during a live optimization run. The "
            "Dashboard sends a start_pipeline event to the FastAPI server, which triggers the "
            "OrchestratorAgent. For each of up to three iterations, the sequence shows: problem "
            "analysis, regional decomposition, parallel regional optimization (five regions "
            "concurrently in ThreadPoolExecutor), coordinator decision generation, consensus "
            "reconciliation, and feedback application. Between iterations, the dashboard receives "
            "WebSocket JSON events at each phase boundary (iteration_complete, pipeline_progress, "
            "pipeline_complete). The total runtime spans approximately 40 seconds with ~40 WebSocket "
            "events across all iterations. The pipeline_streamer.py module on the backend side "
            "serializes agent events into the typed event schema defined in event_schemas.py "
            "before broadcasting to connected WebSocket clients."
        ),
        # flowchart TB - System Context, §17.1
        9: (
            "System Context Diagram: External Integrations and Boundary",
            "This context diagram defines the system boundary and external integrations. The core "
            "AI Vessel Routing Engine interfaces with external CSV data sources (ports, demand, "
            "fleet, distance), an LLM API provider (OpenAI-compatible endpoint at the configured "
            "LLM_BASE_URL), and produces pipeline_output.json consumed by the React dashboard. "
            "The LLMClient communicates with the external API via HTTPS, with all prompts and "
            "responses cached by MD5 hash. The system has no direct database integration; all "
            "runtime state is held in memory by the SharedContext singleton and serialized only "
            "on pipeline completion. The HealthTracker singleton provides runtime monitoring "
            "metrics accessible via the /api/health endpoint. External users interact exclusively "
            "through the React dashboard via a REST API and WebSocket connection."
        ),
        # flowchart LR - Pipeline DAG, §17.2
        10: (
            "Pipeline DAG: Eight-Layer Architecture from Data Ingestion to Validation",
            "This diagram illustrates the eight-layer pipeline architecture: L1 (DATA): CSV input "
            "files parsed by NetworkLoader into dataclass structures. L2 (CONFIG): Configuration "
            "loading from environment variables via Config class and optimizer_config.py. L3 (DECOMP): "
            "PortClustering (KMeans, k=5) and RegionalSplitter dividing the global problem into "
            "regional sub-problems. L4 (AGENTS): The multi-agent AI layer performing strategy "
            "generation, service generation, and explanation. L5 (OPTIMIZE): HierarchicalGA and "
            "HubMILP solvers computing optimal service frequencies and cargo flows. L6 (COORD): "
            "CoordinatorAgent global conflict resolution and feedback generation. L7 (VAL): "
            "Validation layer with weight/archetype/policy validators and ConsensusEngine. "
            "L8 (OUTPUT): Serialization to pipeline_output.json and dashboard rendering."
        ),
        # flowchart TB - Deployment, §17.3
        11: (
            "Deployment Architecture: Service Communication and Runtime Flow",
            "This deployment diagram shows the runtime communication paths between system layers. "
            "The Orchestrator delegates regional optimization to five RegionalAgent instances "
            "running in parallel threads. Each RegionalAgent coordinates with a ServiceGeneratorAgent "
            "for LLM-based service design and a HubDetector for identifying hub ports from demand "
            "patterns. The HierarchicalGA (ServiceGA + FrequencyGA) performs service selection "
            "before the HubMILP solver optimizes cargo flows via PuLP/CBC. The CoordinatorAgent "
            "aggregates regional results, detects conflicts, and generates weight adjustments. The "
            "ConsensusEngine reconciles competing weight proposals from coordinator, regional, "
            "and service generator agents. The Validation layer (weight_validator, "
            "archetype_validator, regional_policy_validator_v2) enforces constraints before "
            "final output is generated. The output flows through the FastAPI backend to the "
            "React dashboard."
        ),
        # flowchart TB - Validation, §18.1
        12: (
            "Three-Pass Validation Pipeline: Weight, Archetype, and Policy Validation",
            "This flowchart details the three-pass validation system. Pass 1 (weight_validator.py): "
            "validate_weight_adjustments() clamps profit/coverage/cost weights to [0,1], normalizes "
            "them to sum to 1.0, and returns AI_VALIDATED or AI_REJECTED tags. Pass 2 "
            "(archetype_validator.py): validate_archetype_params() validates the mix ratios for "
            "direct/hub-loop/feeder/trunk service archetypes, ensuring they sum to 1.0 and each "
            "is within [0.05, 0.90]. Defaults are direct=0.60, hub_loop=0.15, feeder=0.20, "
            "trunk=0.05. Pass 3 (regional_policy_validator_v2.py): validate_regional_policy_v2() "
            "is the strictest validator, checking anti-neutrality (policy must not be 0.5/0.5), "
            "metric citation (every policy decision must reference a computed metric), vessel "
            "sanity checks (fleet usage cannot exceed available vessels), and drift detection "
            "(policy change from previous iteration capped at 0.3). The ConsensusEngine uses "
            "the validated outputs with weighted voting (coordinator 0.4, regional 0.4, "
            "service generator 0.2) and produces a confidence score between 0.0 and 1.0."
        ),
    },

    "ARCHITECTURE_REFERENCE": {
        # flowchart TB - System Context, §1.3
        1: (
            "System Context: Component Interaction and Data Flow",
            "This diagram shows the high-level interaction between the three main system components: "
            "data layer (CSV + pipeline_output.json), the core Python optimization engine (src/ "
            "package with 8 subpackages, ~15,000 LOC), and the FastAPI async backend (20 modules, "
            "~4,500 LOC) serving the React dashboard. The optimization engine reads raw CSV data "
            "through NetworkLoader, processes it through the multi-agent pipeline, and writes "
            "results to pipeline_output.json. The backend reads this output and serves it to "
            "the frontend via REST and WebSocket endpoints."
        ),
        # flowchart LR - Pipeline High-Level, §1.4
        2: (
            "High-Level Optimization Pipeline: Eight Sequential Stages",
            "This diagram summarizes the eight sequential stages of the optimization pipeline: "
            "DATA (CSV ingestion), OPS (problem construction), DECOMP (clustering and splitting), "
            "AGENTS (multi-agent orchestration), OPT (GA + MILP optimization), COORD (global "
            "coordination and conflict resolution), VAL (three-pass validation), and OUT "
            "(serialization and dashboard rendering). Each stage produces artifacts consumed by "
            "the next stage, with feedback loops from COORD back to AGENTS for iterative refinement."
        ),
        # graph TB - Architecture, §4.1
        3: (
            "High-Level System Architecture: Component Relationships",
            "This diagram depicts the system architecture with four main layers. The Presentation "
            "Layer (React dashboard with 14 navigation views) communicates via HTTP REST and "
            "WebSocket with the Application Layer (FastAPI server with event validation). The "
            "Agent Layer contains the OrchestratorAgent, CoordinatorAgent, five RegionalAgents, "
            "and the ServiceGeneratorAgent, each with distinct responsibilities. The Optimization "
            "Layer implements the HierarchicalGA, FrequencyGA, and HubMILP solvers. The Data "
            "Layer manages CSV ingestion, caching, and pipeline output serialization."
        ),
        # flowchart TB - 8-Layer Pipeline, §5.1
        4: (
            "Eight-Layer Pipeline Architecture: Detailed Stage Breakdown",
            "This layered architecture diagram breaks down each of the eight pipeline stages into "
            "their constituent modules. L1 (DATA) includes ports.csv, demand.csv, fleet.csv and "
            "NetworkLoader. L2 (CONFIG) covers environment variables, the Config class, and "
            "optimizer_config.py. L3 (DECOMP) comprises PortClustering (KMeans) and "
            "RegionalSplitter. L4 (AGENTS) lists all agent types and their LLM integration. "
            "L5 (OPTIMIZE) shows the GA and MILP solver modules. L6 (COORD) covers the "
            "CoordinatorAgent and its conflict resolution. L7 (VAL) lists all five validators. "
            "L8 (OUTPUT) includes pipeline_output.json and the dashboard rendering pipeline."
        ),
        # graph TB - Backend, §6.2
        5: (
            "Backend Architecture: Module Dependency and Service Composition",
            "This diagram shows the internal structure of the backend package, including three "
            "competing FastAPI application entry points (main.py, unified_main.py, server.py), "
            "four APIRouter modules (metrics, pipeline, regions, websocket) that are defined but "
            "not registered in any server instance, the WebSocket manager and event system, and "
            "the service layer bridging to the src/ core package. The architecture highlights "
            "the distinction between the real_orchestrator_integration.py bridge and the "
            "pipeline services that connect the REST API to the optimization pipeline."
        ),
        # ... more diagrams follow in the file
        6: (
            "Frontend Architecture: Component Hierarchy and Data Flow",
            "This diagram maps the React frontend architecture including the component tree, "
            "state management via useOptimizationState hook, API and WebSocket service clients, "
            "and the runtime adapter layer. The 14 navigable views are organized under "
            "MaritimeDashboard with layout components (Header, Sidebar, Footer)."
        ),
        7: (
            "WebSocket Event Flow and Communication Protocol",
            "This diagram illustrates the WebSocket communication protocol between the frontend "
            "dashboard and the FastAPI backend. Events flow bidirectionally: the dashboard sends "
            "control events (start_pipeline, stop_pipeline, ping) while the backend broadcasts "
            "status events (pipeline_progress, iteration_complete, pipeline_complete, error). "
            "The WebSocketManager handles connection pooling and the EventValidator ensures "
            "message schema compliance against 19 defined event types."
        ),
        8: (
            "LLM Integration Architecture: Client, Cache, and Fallback Chain",
            "This diagram details the LLMClient architecture with its multi-layer fallback chain "
            "across five model providers, MD5-based response caching, circuit breaker (5 "
            "consecutive failures = 60s timeout), the LLMEvaluator scoring system (structure 40%, "
            "completeness 30%, relevance 30%), and the evaluation threshold (total < 0.5 triggers "
            "hardcoded fallback). Four agent types make LLM calls: Orchestrator (problem analysis), "
            "Coordinator (decision JSON), Regional (strategy + explanation), and "
            "ServiceGenerator (archetype parameters)."
        ),
        9: (
            "Data Processing Flow: From Raw CSV to Dashboard",
            "This diagram traces data through the complete pipeline: raw CSV files loaded by "
            "NetworkLoader into dataclass objects, composed into a Problem, decomposed into "
            "regional sub-problems via clustering, processed through the multi-agent optimization "
            "pipeline, serialized to pipeline_output.json, served via FastAPI, and rendered "
            "by the React dashboard components."
        ),
        10: (
            "Optimization Pipeline: GA and MILP Solver Coordination",
            "This diagram shows the optimization engine architecture. The HierarchicalGA "
            "coordinates ServiceGA (binary chromosome for service selection) and FrequencyGA "
            "(integer chromosome for frequency allocation), followed by HubMILP (PuLP/CBC solver "
            "with 120s time limit) for cargo flow optimization. The FlowOptimizer calculates "
            "final metrics including profit, coverage, operating cost, fuel cost, transshipment "
            "cost, and port handling cost."
        ),
        11: (
            "Validation Architecture: Three-Pass System with AI Tags",
            "This diagram shows the three-pass validation system: weight validation, archetype "
            "parameter validation, and regional policy validation (v2 with anti-neutrality, metric "
            "citation, vessel sanity, and drift checks). Each validator emits AI log tags "
            "(AI_GENERATED, AI_VALIDATED, AI_REJECTED, AI_FALLBACK). The ConsensusEngine performs "
            "weighted voting reconciliation with configurable voting weights."
        ),
        12: (
            "Agent Architecture: Multi-Agent Workflow and Communication",
            "This diagram details the multi-agent workflow showing the OrchestratorAgent delegating "
            "to five RegionalAgents, the CoordinatorAgent performing global conflict resolution, "
            "the ServiceGeneratorAgent designing service archetypes, and the ConsensusEngine "
            "reconciling competing proposals through weighted voting."
        ),
        13: (
            "Optimizer Internals: Hierarchical GA and MILP Workflow",
            "This diagram shows the detailed internal workflow of the optimization engine, "
            "from candidate service generation (800-2000 candidates) through the profitability "
            "gate, ServiceGA service selection, FrequencyGA frequency optimization, HubMILP "
            "flow optimization, and FlowOptimizer metric calculation."
        ),
        14: (
            "Runtime Execution Sequence: Pipeline Lifecycle",
            "This diagram traces the complete runtime execution sequence from configuration "
            "loading through data loading, clustering, regional optimization, coordination, "
            "validation, consensus, and output generation. The sequence spans approximately "
            "40 seconds for a full three-iteration run."
        ),
        15: (
            "Multi-Agent Orchestration: Interaction and Data Dependencies",
            "This diagram maps the interaction between all agent types, their input/output "
            "dependencies, and the shared state managed by SharedContext. The coordination "
            "loop spans problem analysis, decomposition, parallel regional execution, "
            "aggregation, conflict resolution, feedback generation, and consensus reconciliation."
        ),
        16: (
            "Deployment Infrastructure: Container and Service Architecture",
            "This diagram shows the deployment architecture with Docker containerization "
            "(python:3.10-slim multi-stage build), the three-tier application structure, "
            "and external dependencies including the LLM API provider and CSV data sources."
        ),
    },

    "CODE_REFERENCE": {
        # graph TB - Module Dependencies
        1: (
            "Module Dependency Graph: Package Relationships and Import Hierarchy",
            "This diagram maps the import relationships between all Python packages in the src/ "
            "directory. The agents package imports from optimization, llm, data, decomposition, "
            "validation, and utils. The optimization package imports from utils and data. "
            "The llm package is standalone with no internal dependencies. The validation package "
            "imports from utils only. The utils package has no internal dependencies. This "
            "structure enforces a layered dependency rule: agents (highest) → optimization → "
            "data/decomposition → utils (lowest). No circular dependencies exist between packages."
        ),
        # flowchart LR - Execution Flow
        2: (
            "Runtime Execution Flow: Coordinator Initialization Through Output Generation",
            "This flowchart traces the complete execution flow from user invocation through "
            "configuration loading, data loading (NetworkLoader), problem construction, "
            "orchestrator initialization, regional agent creation (5 instances), GA optimization, "
            "MILP optimization, global aggregation, result validation, output generation as "
            "pipeline_output.json, and dashboard rendering. This sequence reflects the actual "
            "call chain in orchestrator_agent.py process() method, traced through all sub-modules."
        ),
    },
}


# DOT diagram captions and explanations
DOT_CAPTIONS = {
    "MASTER_TECHNICAL_DOCUMENTATION_V2": [
        (
            "Overall System Architecture: End-to-End AI Vessel Routing System",
            "This architecture diagram maps the complete system from data ingestion through "
            "multi-agent AI optimization to dashboard visualization. The six-layer architecture "
            "comprises: (1) Frontend — React dashboard with MaritimeDashboard entry point, "
            "WebSocket client for real-time events, and REST API client for data fetching; "
            "(2) Backend — FastAPI server with three application variants (main.py, "
            "unified_main.py, server.py), WebSocket manager processing 19 event types, "
            "and REST API routes for metrics, pipeline control, region data, and export; "
            "(3) Multi-Agent AI Layer — OrchestratorAgent master controller, "
            "CoordinatorAgent for global decisions, RegionalAgent x5 (Asia, Europe, "
            "Americas, Middle East, Africa), and ServiceGeneratorAgent for LLM-guided "
            "service design; (4) Optimization Engine — HierarchicalGA (ServiceGA + "
            "FrequencyGA) implemented with numpy arrays, HubMILP PuLP/CBC solver with "
            "120s time limit, and FlowOptimizer for post-MILP metric calculation; "
            "(5) Data Layer — CSV sources loading via NetworkLoader into dataclass "
            "Problem objects, K-means clustering (k=5) for regional decomposition, "
            "and pipeline_output.json serialization; (6) Validation Layer — Weight "
            "Validator, Archetype Validator, Regional Policy Validator V2, and "
            "ConsensusEngine (975 lines) performing weighted voting reconciliation "
            "with confidence scoring. The LLMClient singleton provides OpenAI-compatible "
            "API access with MD5 caching, circuit breaker (5 failures = 60s timeout), "
            "and five-model fallback chain."
        ),
        (
            "Multi-Agent AI Architecture: Agent Responsibilities and Communication Flow",
            "This diagram details the three-tier agent hierarchy and their interaction patterns. "
            "The OrchestratorAgent (src/agents/orchestrator_agent.py, 903 lines) serves as the "
            "master controller, executing analyze_problem() via LLM call then decomposing the "
            "global problem via PortClustering (KMeans k=5) and RegionalSplitter. It runs up to "
            "three optimization iterations, each dispatching five RegionalAgents in parallel via "
            "ThreadPoolExecutor (max_workers=5). Each RegionalAgent (src/agents/regional_agent.py, "
            "474 lines) executes: LLM strategy generation (A/B/C based on demand dispersion), "
            "ServiceGeneratorAgent for LLM-guided service archetype parameter generation, "
            "HierarchicalGA optimization (ServiceGA binary chromosome + FrequencyGA integer "
            "chromosome), HubMILP flow optimization, LLM explanation generation (verdict/"
            "strengths/weaknesses/actions), and deterministic regional policy derivation from "
            "10 computed metrics. The CoordinatorAgent (src/agents/coordinator_agent.py, 574 "
            "lines) performs: inter-regional conflict detection (service overlap analysis), "
            "conflict resolution (drops lower-profit services), global metric aggregation, "
            "system evaluation (score 0-5), LLM-based decision generation with weight "
            "validation, and gradient feedback signal generation. The ConsensusEngine "
            "(src/validation/consensus_engine.py, 975 lines) reconciles competing weight "
            "proposals via weighted voting (coordinator 0.4, regional 0.4, service generator "
            "0.2) and produces a confidence score (0.0-1.0)."
        ),
        (
            "Backend Service Architecture: FastAPI Routes, Services, and WebSocket Communication",
            "This diagram maps the backend package structure showing three application entry "
            "points (main.py 597 lines, unified_main.py 1280 lines, server.py 618 lines), each "
            "defining a FastAPI instance on port 8000. Four APIRouter modules (routes/metrics.py, "
            "routes/pipeline.py, routes/regions.py, routes/websocket.py) define 16+ endpoints "
            "but are not registered via app.include_router() in any server — these are dead code "
            "defined for potential future activation. The websocket_manager.py handles connection "
            "lifecycle and event broadcasting with 19 typed events from event_schemas.py. The "
            "real_orchestrator_integration.py bridge connects backend services to the src/ "
            "optimization engine. Two Pydantic model sets exist (api_models.py and models/"
            "schemas.py) with overlapping but non-identical field definitions. The service layer "
            "(optimization_service.py, pipeline_service.py, pipeline_streamer.py) provides "
            "the operational interface between REST API handlers and the optimization pipeline."
        ),
        (
            "Frontend Component Architecture: React Dashboard Hierarchy and State Flow",
            "This diagram maps the complete React frontend architecture. MaritimeDashboard.jsx "
            "(240 lines, src/views/) is the single-page entry, wrapped in ErrorBoundary.jsx "
            "(class component). State management uses a custom useOptimizationState hook "
            "with useState + useCallback — not Redux or Zustand (both in package.json but "
            "unused). The apiClient.js module exposes 7 fetch-based REST endpoints "
            "(getPipelineStatus, startPipeline, stopPipeline, getMetrics, getRegions, "
            "healthCheck, loadRuntimeTruth). websocketManager.js handles 12 WebSocket event "
            "types (pipeline_complete, iteration_complete, pipeline_error, progress_update, "
            "region_update, conflict_detected, weight_adjusted, consensus_reached, "
            "agent_status, llm_call, benchmark_result, metrics_update). runtimeAdapter.js "
            "normalizes both REST (pipeline_output.json) and WebSocket data to camelCase. "
            "The 14 navigation views are rendered via renderMain() function switching on view "
            "state: LandingView, KpiCard x6 + WorldMap overview, FleetDashboard + FleetPanel, "
            "RouteTable, PortPanel, PipelineView + FunnelView + RegionPipelineNode, "
            "RegionDetails + RegionalIntelligence + RegionCard, FeedbackView + DecisionTrace + "
            "DecisionExplanation, ConflictView, WorldMap (react-simple-maps), "
            "ScenarioWorkspace, ExportPanel, and SummaryView with BackendCertification."
        ),
        (
            "Optimization Pipeline: Genetic Algorithm and MILP Solver Workflow",
            "This diagram details the optimization engine internals. The pipeline begins with "
            "800-2000 candidate services from ServiceGeneratorAgent, filtered through a "
            "profitability gate (revenue > operating cost + fuel cost + port cost). The "
            "HierarchicalGA coordinates two GAs: ServiceGA uses binary chromosomes (0/1 per "
            "candidate) with population 80, elite-10 selection via heapq, single-point crossover, "
            "demand-biased mutation (50% high-demand activation, 50% random flip), and early "
            "stop at 8 generations or 90 seconds. The fitness function computes "
            "w_profit * normalized_profit + w_coverage * normalized_coverage - w_cost * "
            "normalized_cost with penalties for negative-margin services, capacity overcommit, "
            "and unserved demand. Selected services pass to FrequencyGA (integer chromosomes "
            "[0,1,2,3] for sailings/week) with analytical initialization from ceil(demand/"
            "capacity) + jitter and the same early-stop criteria. The HubMILP (PuLP, 563 lines) "
            "defines decision variables for direct flow, transfer flow (transshipment pairs "
            "prioritized by hub demand), and unserved demand, with constraints for service "
            "capacity, port capacity, and fleet limit (300 vessels). The solver runs "
            "PULP_CBC_CMD with 120s time limit."
        ),
        (
            "End-to-End Data Processing Flow: From Raw CSV to Dashboard Visualization",
            "This diagram traces every data transformation step. Four CSV sources feed into "
            "NetworkLoader (src/data/network_loader.py): ports.csv (333 ports, 11 columns: "
            "UNLocode, name, country, region, coordinates, costs), demand_world_large.csv "
            "(40K+ origin-destination pairs with FFEPerWeek and Revenue), fleet_world_large.csv "
            "(6 vessel classes totaling 501 vessels: Feeder_450, Feeder_800, Panamax_1200, "
            "Panamax_2400, Post_panamax, Super_panamax), and distance_dense.csv (port-to-port "
            "distance matrix with Panama/Suez canal flags). NetworkLoader produces dataclass "
            "instances (Port, Demand, Service, DistanceMatrix) composed into a Problem object. "
            "PortClustering (KMeans scikit-learn, k=5) groups ports by geographic coordinates; "
            "RegionalSplitter creates per-cluster sub-problems. The multi-agent pipeline "
            "processes each region independently, producing selected services with frequencies, "
            "hub assignments, and flow allocations. FlowOptimizer calculates 14 summary metrics "
            "(weekly_profit, annual_profit, revenue, operating_cost, fuel_cost, port_cost, "
            "transship_cost, total_services, satisfied_demand, unserved_demand, coverage_pct, "
            "total_runtime). Results serialize to pipeline_output.json with complete runtime "
            "state including regional results, consensus result, and LLM runtime metrics."
        ),
        (
            "Validation Pipeline: Multi-Layer Validation with AI Tagging",
            "This diagram maps the three-pass validation system with its AI confidence tagging. "
            "weight_validator.py: validate_weight_adjustments() clamps profit/coverage/cost "
            "weights to [0,1] and renormalizes to sum 1.0. archetype_validator.py: "
            "validate_archetype_params() checks direct/hub-loop/feeder/trunk ratios sum to 1.0 "
            "and each in [0.05, 0.90]; default is {direct: 0.60, hub_loop: 0.15, feeder: 0.20, "
            "trunk: 0.05, vessel_bias: balanced}. regional_policy_validator.py: validates policy "
            "keys and value ranges. regional_policy_validator_v2.py: strictest validator with "
            "anti-neutrality (policy != 0.5/0.5), metric citation (each decision references a "
            "computed metric), vessel sanity (fleet <= 300), and drift detection (change from "
            "prior iteration <= 0.3). ConsensusEngine (src/validation/consensus_engine.py, 975 "
            "lines): coordinates conflict detection across weight disparity, archetype mismatch, "
            "and hub set conflicts, then reconciles via weighted voting with 0.4/0.4/0.2 weights. "
            "Confidence score thresholds: >0.7 = ACCEPTED, 0.3-0.7 = MODIFIED, <0.3 = REJECTED. "
            "Eight AI log tags track provenance through the pipeline."
        ),
        (
            "LLM Integration Architecture: Client, Evaluator, Metrics, and Fallback Chain",
            "This diagram details the LLMClient singleton architecture. The client (src/llm/"
            "client.py, 254 lines) wraps the OpenAI Python SDK with custom base URL pointing "
            "to opencode.ai/zen/v1 (configurable via LLM_BASE_URL env var). The primary model "
            "is opencode/deepseek-v4-flash-free with a fallback chain through five providers. "
            "Each call is hashed (MD5 of model|system|user_message) and cached to avoid "
            "redundant API calls. A circuit breaker trips after 5 consecutive failures, "
            "imposing a 60-second cooldown before retrying. The LLMEvaluator (src/llm/"
            "evaluator.py, 67 lines) scores responses on three axes: Structure (40%, checks "
            "for Strategy and Reason keywords), Completeness (30%, line count threshold), "
            "and Relevance (30%, domain keywords: demand, port, hub, capacity, route). "
            "If total score < 0.5, the response is rejected and a hardcoded fallback is used. "
            "Four agent types call the LLM: OrchestratorAgent (problem analysis and executive "
            "summary), CoordinatorAgent (decision JSON with skip_evaluator=True), "
            "RegionalAgent (strategy A/B/C classification and explanation), and "
            "ServiceGeneratorAgent (archetype params with skip_evaluator=True)."
        ),
        (
            "Configuration Architecture: Environment Variables and Module Configuration",
            "This diagram maps configuration loading across the system. Environment variables "
            "are loaded from .env file: OPENCODE_API_KEY and OPENROUTER_API_KEY for LLM "
            "authentication, LLM_BASE_URL for API endpoint, ORCHESTRATOR_MODEL and "
            "REGIONAL_MODEL for model selection (default: opencode/deepseek-v4-flash-free), "
            "GA_POPULATION_SIZE (80), GA_GENERATIONS (120), and MILP_TIME_LIMIT (120s). "
            "src/utils/config.py provides a static Config class reading environment variables. "
            "src/config/optimizer_config.py defines ObjectiveConfig dataclass with CONFIG "
            "singleton. Constants include FLEET_SIZE = 300, MAX_ITERATIONS = 3, "
            "COVERAGE_TARGET = 70.0%, TRANSSHIP_COST = $80/TEU, UNSERVED_PENALTY = $300/TEU, "
            "BUNKER_PRICE = $600/ton, Elite size = 10, No-improve limit = 8 generations."
        ),
        (
            "Repository Structure: Complete Project Organization",
            "This diagram shows the repository directory tree with 8 top-level directories. "
            "src/ contains 8 subpackages (agents, config, data, decomposition, llm, "
            "optimization, pipeline (empty/reserved), services, utils, validation). backend/ "
            "contains 3 competing FastAPI apps, 4 dead APIRouter modules, WebSocket manager, "
            "event system, and 3 service modules. frontend/ contains React dashboard with "
            "views/, components/ (common, layout, overview, regions, optimization, map), "
            "services/, hooks/, utils/, and runtime/ adapter. tests/ has 14 test files "
            "(test_orchestrator.py at 3947 lines being the largest). scripts/ has 17 "
            "diagnostic tools. data/ splits into datasets/ (3 JSON problem files) and raw/ "
            "(5 CSV source files). Dockerfile uses multi-stage python:3.10-slim build."
        ),
    ],
    "ARCHITECTURE_REFERENCE": [
        (
            "Overall System Architecture: End-to-End AI Vessel Routing System",
            "This diagram maps the complete system architecture from data sources through "
            "multi-agent optimization to the frontend dashboard. The system comprises six "
            "layers: Frontend (React/Vite), Backend (FastAPI/WebSockets), Multi-Agent AI "
            "(Orchestrator, Coordinator, Regional x5, ServiceGenerator), Optimization "
            "(HierarchicalGA, HubMILP, FlowOptimizer), Data (CSV, NetworkLoader, Problem), "
            "and Validation (Weight, Archetype, Policy, ConsensusEngine). External LLM API "
            "integration is provided by the LLMClient singleton with fallback chain."
        ),
        (
            "Multi-Agent AI Architecture: Agent Responsibilities and Communication Flow",
            "This diagram details the three-tier agent hierarchy with 6-stage orchestration "
            "lifecycle: problem analysis, decomposition, parallel regional execution (5 "
            "regions in ThreadPoolExecutor), global coordination, consensus reconciliation, "
            "and feedback-driven iteration (max 3 iterations). The ConsensusEngine performs "
            "weighted voting (coordinator 0.4, regional 0.4, service generator 0.2) to "
            "reconcile competing proposals."
        ),
        (
            "Backend Service Architecture: FastAPI Routes, Services, and WebSocket Communication",
            "This diagram maps the backend package showing three application entry points, "
            "four defined-but-unregistered APIRouter modules, the WebSocket manager with "
            "19 typed events, and the service layer bridging to the optimization engine."
        ),
        (
            "Validation Pipeline: Multi-Layer Validation with AI Tagging",
            "This diagram maps the three-pass validation system. Each validator emits AI "
            "provenance tags (AI_GENERATED, AI_VALIDATED, AI_REJECTED, AI_FALLBACK). "
            "The ConsensusEngine performs weighted voting and confidence scoring."
        ),
        (
            "LLM Integration Architecture: Client, Evaluator, and Fallback Chain",
            "This diagram details the LLMClient architecture with MD5 caching, circuit "
            "breaker (5 failures = 60s timeout), LLMEvaluator scoring (3 axes, threshold "
            "0.5), and five-model fallback chain for resilience."
        ),
        (
            "Configuration Architecture: Environment Variables and Module Configuration",
            "This diagram maps the configuration system from .env file through Config class "
            "and optimizer_config.py to all consumers (LLMClient, GA, MILP, agents)."
        ),
    ],
    "CODE_REFERENCE": [
        (
            "Repository Structure: Complete Project Organization",
            "This diagram shows the project directory tree with ~15,000 LOC across 40+ Python "
            "files, 34 frontend source files, and 14 test files totaling ~10,000 test LOC."
        ),
        (
            "Optimization Pipeline: Genetic Algorithm and MILP Solver Workflow",
            "This diagram details the optimization engine: 800-2000 candidate services, "
            "profitability gate, ServiceGA binary-chromosome selection, FrequencyGA integer-"
            "chromosome optimization, HubMILP PuLP/CBC flow optimization, and FlowOptimizer "
            "metric calculation. Fleet constraint = 300 vessels max. Coverage target = 70.0%."
        ),
        (
            "End-to-End Data Processing Flow: From Raw CSV to Dashboard Visualization",
            "This diagram traces data through the complete pipeline: CSV → NetworkLoader → "
            "dataclass Problem → KMeans clustering → RegionalSplitter → multi-agent "
            "optimization → pipeline_output.json → FastAPI → React dashboard."
        ),
    ],
}


def get_mermaid_caption(doc_name, diagram_index):
    """Get descriptive caption and explanation for a Mermaid diagram."""
    doc_map = MERMAID_CAPTIONS.get(doc_name, {})
    entry = doc_map.get(diagram_index)
    if entry:
        return entry
    return None, None


def get_dot_captions(doc_name):
    """Get all DOT diagram captions and explanations for a document."""
    return DOT_CAPTIONS.get(doc_name, [])
