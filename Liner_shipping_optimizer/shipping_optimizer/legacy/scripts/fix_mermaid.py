#!/usr/bin/env python3
"""
Fix Mermaid syntax errors in source documentation files.

Known issues:
1. \n inside node labels - use <br /> instead
2. & multi-edge syntax
3. Unicode chars (arrows, special chars)
4. Parentheses (in text labels conflicting with round node syntax)
5. Edge label pipe syntax spacing
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FIXES = {
    # ── MASTER_TECHNICAL_DOCUMENTATION_V2.md ──
    "MASTER_TECHNICAL_DOCUMENTATION_V2.md": [
        # Fix #1 (line 339-358): flowchart TB with \n inside [] labels
        {
            "old": r'CSV\[CSV Input Data\\nports\.csv, demand\.csv, fleet\.csv, distance\.csv\]',
            "new": 'CSV["CSV Input Data<br/>ports.csv, demand.csv, fleet.csv, distance.csv"]',
        },
        {
            "old": r'ETL\[ETL & Validation\\nPydantic schema checks\\nFFE->TEU x2\.0\]',
            "new": 'ETL["ETL & Validation<br/>Pydantic schema checks<br/>FFE to TEU x2.0"]',
        },
        {
            "old": r'SP\[Shipping Problem\\n333 ports, 9,622 lanes, 1\.67M TEU/wk\]',
            "new": 'SP["Shipping Problem<br/>333 ports, 9,622 lanes, 1.67M TEU/wk"]',
        },
        {
            "old": r'OPT\[Per Region:\\nService Generation \(800-2k candidates\)\\n-> GA Filtering \(80 pop x 120 gen\)\\n-> MILP Solve \(120s time limit\)\]',
            "new": 'OPT["Per Region:<br/>Service Generation (800-2k candidates)<br/>to GA Filtering (80 pop x 120 gen)<br/>to MILP Solve (120s time limit)"]',
        },
        {
            "old": r'CA\[Coordinator Agent\\nLLM evaluation\\nWeight adjustment\\nConvergence check\]',
            "new": 'CA["Coordinator Agent<br/>LLM evaluation<br/>Weight adjustment<br/>Convergence check"]',
        },
        {
            "old": r'FB{Converged\?\\nScore > 0\.97\?}',
            "new": 'FB{"Converged?<br/>Score > 0.97?"}',
        },
        # Fix #10 (line 1091-1107): flowchart LR with & operator
        {
            "old": r'subgraph "L1:DATA" P\[Ports\] & D\[Demand\] & F\[Fleet\] & M\[Distance\]\s+end',
            "new": 'subgraph "L1:DATA"\n        P[Ports]\n        D[Demand]\n        F[Fleet]\n        M[Distance]\n    end',
        },
        {
            "old": r'subgraph "L2:ETL" ETL\[ETL \+ Validation\]\s+end',
            "new": 'subgraph "L2:ETL"\n        ETL["ETL + Validation"]\n    end',
        },
        {
            "old": r'subgraph "L3:CTRL" ORCH\[Orchestrator\] & SPLIT\[Splitter\]\s+end',
            "new": 'subgraph "L3:CTRL"\n        ORCH[Orchestrator]\n        SPLIT[Splitter]\n    end',
        },
        {
            "old": r'subgraph "L4:REG" REG\[5 Regional GA\+MILP\]\s+end',
            "new": 'subgraph "L4:REG"\n        REG["5 Regional GA+MILP"]\n    end',
        },
        {
            "old": r'subgraph "L5:RES" AGGR\[Aggregation\] & COORD\[Coordinator\]\s+end',
            "new": 'subgraph "L5:RES"\n        AGGR[Aggregation]\n        COORD[Coordinator]\n    end',
        },
        {
            "old": r'subgraph "L6-8:OUT" VAL\[Validator\] & FINAL\[Final Opt\] & OUT\[Output\]\s+end',
            "new": 'subgraph "L6-8:OUT"\n        VAL[Validator]\n        FINAL["Final Opt"]\n        OUT[Output]\n    end',
        },
        {
            "old": r'P & D & F & M --> ETL --> ORCH --> SPLIT --> REG --> AGGR --> COORD',
            "new": 'P --> ETL\n    D --> ETL\n    F --> ETL\n    M --> ETL\n    ETL --> ORCH\n    ORCH --> SPLIT\n    SPLIT --> REG\n    REG --> AGGR\n    AGGR --> COORD',
        },
        {
            "old": r'COORD -->\|Rerun <= 3\| SPLIT',
            "new": 'COORD -->|Rerun up to 3| SPLIT',
        },
        {
            "old": r'COORD --> VAL --> FINAL --> OUT',
            "new": 'COORD --> VAL\n    VAL --> FINAL\n    FINAL --> OUT',
        },
    ],

    # ── ARCHITECTURE_REFERENCE.md ──
    "ARCHITECTURE_REFERENCE.md": [
        # Fix #5 (graph TB with \n in labels)
        {
            "old": r'M\[main\.py\\nApp Entry\]',
            "new": 'M["main.py<br/>App Entry"]',
        },
        {
            "old": r'ES\[event_schemas\.py\\n22 Event Models\]',
            "new": 'ES["event_schemas.py<br/>22 Event Models"]',
        },
        {
            "old": r'EV\[event_validator\.py\\ncreate_event\(\)\\nvalidate_incoming\(\)\\nto_json\(\)\]',
            "new": 'EV["event_validator.py<br/>create_event()<br/>validate_incoming()<br/>to_json()"]',
        },
        {
            "old": r'WM1\[WebSocket Manager\\nmain\.py version\\nList \+ Lock\]',
            "new": 'WM1["WebSocket Manager<br/>main.py version<br/>List + Lock"]',
        },
        {
            "old": r'MET\[metrics\.py\\nGET summary\\nGET trends\\nPUT update\]',
            "new": 'MET["metrics.py<br/>GET summary<br/>GET trends<br/>PUT update"]',
        },
        {
            "old": r'PIP\[pipeline\.py\\nPOST start\\nPOST stop\\nGET status\]',
            "new": 'PIP["pipeline.py<br/>POST start<br/>POST stop<br/>GET status"]',
        },
        {
            "old": r'REG\[regions\.py\\nGET all\\nGET by id\\nPOST optimize\]',
            "new": 'REG["regions.py<br/>GET all<br/>GET by id<br/>POST optimize"]',
        },
        {
            "old": r'OS\[optimization_service\.py\\nMock results\]',
            "new": 'OS["optimization_service.py<br/>Mock results"]',
        },
        {
            "old": r'PS\[pipeline_service\.py\\nOrchestrator wrapper\]',
            "new": 'PS["pipeline_service.py<br/>Orchestrator wrapper"]',
        },
        {
            "old": r'PS2\[pipeline_streamer\.py\\nEvent generator\]',
            "new": 'PS2["pipeline_streamer.py<br/>Event generator"]',
        },
        {
            "old": r'OI\[real_orchestrator_integration\.py\\nrun_optimization\(\)\\n_process_region\(\)\\n_broadcast_event\(\)\]',
            "new": 'OI["real_orchestrator_integration.py<br/>run_optimization()<br/>_process_region()<br/>_broadcast_event()"]',
        },
        {
            "old": r'OC\[OrchestratorCallbacks\\non_pipeline_start\\non_region_update\\non_iteration_complete\]',
            "new": 'OC["OrchestratorCallbacks<br/>on_pipeline_start<br/>on_region_update<br/>on_iteration_complete"]',
        },
        {
            "old": r'DB\[\(optimization_results\.db\\nSQLite\)\]',
            "new": 'DB[("optimization_results.db<br/>SQLite")]',
        },
        # Fix #8: deployment flowchart
        {
            "old": r'UV\[Uvicorn\\nPort 8000\]',
            "new": 'UV["Uvicorn<br/>Port 8000"]',
        },
        {
            "old": r'FA\[FastAPI App\\nmain\.py\]',
            "new": 'FA["FastAPI App<br/>main.py"]',
        },
        {
            "old": r'AI_AGENTS\[LLM Agent Layer\]',
            "new": 'AI_AGENTS["LLM Agent Layer"]',
        },
        {
            "old": r'DB\[\(SQLite\\noptimization_results\.db\)\]',
            "new": 'DB[("SQLite<br/>optimization_results.db")]',
        },
        {
            "old": r'DATA\[\(CSV/JSON\\nData Files\)\]',
            "new": 'DATA[("CSV/JSON<br/>Data Files")]',
        },
        {
            "old": r'PO\[pipeline_output\.json\]',
            "new": 'PO["pipeline_output.json"]',
        },
        {
            "old": r'FE_BUILD\[React Build\\nfrontend/dist/\]',
            "new": 'FE_BUILD["React Build<br/>frontend/dist/"]',
        },
        {
            "old": r'LLM\[LLM Provider\\nOpenRouter/OpenCode\]',
            "new": 'LLM["LLM Provider<br/>OpenRouter/OpenCode"]',
        },
        {
            "old": r'BROWSER\[Client Browser\\nDashboard UI\]',
            "new": 'BROWSER["Client Browser<br/>Dashboard UI"]',
        },
        # Fix the <--WebSocket--> edge syntax in ARCH #8
        {
            "old": r'WS_MGR <--WebSocket--> BROWSER',
            "new": 'WS_MGR <-.->|WebSocket| BROWSER',
        },
        {
            "old": r'FA <--HTTP/WS--> BROWSER',
            "new": 'FA <.->|HTTP/WS| BROWSER',
        },
        # Fix #10: flowchart LR final state
        {
            "old": r'VALIDATING --> COMPLETED\[completed\]',
            "new": 'VALIDATING --> COMPLETED["completed"]',
        },
        # Fix #12: sequenceDiagram (looks correct but mark as valid with minor fix)
        # Fix #13: graph TB with \n in labels and special chars
        {
            "old": r'OA\[Orchestrator Agent\\nRole: Problem Analysis\\nModel: DeepSeek-v4\\nTemp: 0\.3\\nCalled: 1x per run\]',
            "new": 'OA["Orchestrator Agent<br/>Role: Problem Analysis<br/>Model: DeepSeek-v4<br/>Temp: 0.3<br/>Called: 1x per run"]',
        },
        {
            "old": r'CA\[Coordinator Agent\\nRole: Global Evaluation\\nModel: DeepSeek-v4\\nTemp: 0\.3\\nCalled: <=3x per run\]',
            "new": 'CA["Coordinator Agent<br/>Role: Global Evaluation<br/>Model: DeepSeek-v4<br/>Temp: 0.3<br/>Called: up to 3x per run"]',
        },
        {
            "old": r'RA1\[Regional Agent: Asia\\nRole: Strategy Generation\\nModel: DeepSeek-v4\\nTemp: 0\.5\\nCalled: <=3x per run\]',
            "new": 'RA1["Regional Agent: Asia<br/>Role: Strategy Generation<br/>Model: DeepSeek-v4<br/>Temp: 0.5<br/>Called: up to 3x per run"]',
        },
        {
            "old": r'RA2\[Regional Agent: Europe\\nRole: Strategy Generation\]',
            "new": 'RA2["Regional Agent: Europe<br/>Role: Strategy Generation"]',
        },
        {
            "old": r'RA3\[Regional Agent: Americas\\nRole: Strategy Generation\]',
            "new": 'RA3["Regional Agent: Americas<br/>Role: Strategy Generation"]',
        },
        {
            "old": r'RA4\[Regional Agent: Middle East\\nRole: Strategy Generation\]',
            "new": 'RA4["Regional Agent: Middle East<br/>Role: Strategy Generation"]',
        },
        {
            "old": r'RA5\[Regional Agent: Africa\\nRole: Strategy Generation\]',
            "new": 'RA5["Regional Agent: Africa<br/>Role: Strategy Generation"]',
        },
        {
            "old": r'CE\[Consensus Engine\\nRole: Agreement Scoring\\nModel: Rule-based\\nCalled: 1x per run\]',
            "new": 'CE["Consensus Engine<br/>Role: Agreement Scoring<br/>Model: Rule-based<br/>Called: 1x per run"]',
        },
        {
            "old": r'GA\[Genetic Algorithm\\n80 pop, 120 gen\\nTournament selection\]',
            "new": 'GA["Genetic Algorithm<br/>80 pop, 120 gen<br/>Tournament selection"]',
        },
        {
            "old": r'MILP\[MILP Solver\\nGurobi/OR-Tools\\n120s time limit\]',
            "new": 'MILP["MILP Solver<br/>PuLP/CBC<br/>120s time limit"]',
        },
    ],
}


def apply_fixes():
    for filename, fixes in FIXES.items():
        filepath = ROOT / filename
        if not filepath.exists():
            print(f"  SKIP: {filename} not found")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        changes = 0
        for fix in fixes:
            old_expr = fix["old"]
            new_text = fix["new"]
            count = re.subn(old_expr, new_text, content)
            if count[1] > 0:
                content = count[0]
                changes += count[1]

        if changes > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  FIXED: {filename} — {changes} changes applied")
        else:
            print(f"  NO CHANGE: {filename} — no patterns matched")

    print("\nDone. Re-run preprocessing to regenerate with fixed diagrams.")


if __name__ == "__main__":
    apply_fixes()
