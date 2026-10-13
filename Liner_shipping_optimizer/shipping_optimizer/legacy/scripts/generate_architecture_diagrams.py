#!/usr/bin/env python3
"""
Architecture Diagram Generator — AI Vessel Routing System
Generates publication-quality architecture diagrams using Graphviz DOT.
Produces SVG output that embeds native text elements (no foreignObject issues).
"""

import os
import subprocess
import sys
from pathlib import Path

GRAPHVIZ_DIR = Path("docs/generated/assets/diagrams")
GRAPHVIZ_SVG_DIR = GRAPHVIZ_DIR / "svg"
GRAPHVIZ_PNG_DIR = GRAPHVIZ_DIR / "png"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure Graphviz is in PATH
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"

# Color palette matching project theme
COLORS = {
    "bg": "#ffffff",
    "text": "#1a1a2e",
    "primary": "#00d4ff",      # cyan accent
    "secondary": "#7c3aed",    # purple
    "tertiary": "#10b981",     # green
    "warning": "#f59e0b",      # amber
    "danger": "#ef4444",       # red
    "node_bg": "#f0f4ff",
    "node_border": "#3b82f6",
    "agent_bg": "#eef2ff",
    "agent_border": "#6366f1",
    "data_bg": "#f0fdf4",
    "data_border": "#22c55e",
    "frontend_bg": "#fefce8",
    "frontend_border": "#eab308",
    "backend_bg": "#fef2f2",
    "backend_border": "#ef4444",
    "ai_bg": "#f5f3ff",
    "ai_border": "#8b5cf6",
    "validation_bg": "#fff7ed",
    "validation_border": "#f97316",
}

def ensure_dirs():
    for d in [GRAPHVIZ_SVG_DIR, GRAPHVIZ_PNG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def render_dot(dot_source, name, rankdir="TB", layout="dot", dpi=300, high_dpi=600):
    """Render a DOT diagram to SVG and publication-quality PNGs.

    Args:
        dot_source: Raw DOT subgraph content
        name: Diagram identifier
        rankdir: Graphviz rank direction (TB/LR)
        layout: Graphviz layout engine (dot/neato/fdp/sfdp)
        dpi: Standard DPI for default PNG output
        high_dpi: High-quality DPI for large-format PNG output
    """
    dot_file = GRAPHVIZ_DIR / f"{name}.dot"
    svg_file = GRAPHVIZ_SVG_DIR / f"{name}.svg"
    png_file = GRAPHVIZ_PNG_DIR / f"{name}.png"
    png_hires_file = GRAPHVIZ_PNG_DIR / f"{name}_hires.png"

    # Publication-quality defaults
    full_dot = f"""digraph "{name}" {{
    rankdir={rankdir};
    layout="{layout}";
    bgcolor="{COLORS['bg']}";
    fontname="Arial";
    fontsize="18";
    labeljust="l";
    compound=true;
    newrank=true;
    style="solid";
    splines="ortho";
    overlap=false;
    sep="+15";
    nodesep="0.7";
    ranksep="0.9";
    margin="0";
    pad="0.3";
    edge [fontname="Arial", fontsize="14", color="#444444",
          penwidth="2", arrowsize="1.2", fontcolor="#333333"];
    node [fontname="Arial", fontsize="14", shape="box", style="filled,rounded",
          fillcolor="{COLORS['node_bg']}", color="{COLORS['node_border']}", penwidth="2",
          margin="0.15,0.1"];
    // Cluster defaults are set inside each subgraph block

{dot_source}
}}"""

    # Write DOT
    dot_file.write_text(full_dot, encoding="utf-8")

    # Render SVG (vector, always best quality)
    result = subprocess.run(
        ["dot", f"-Tsvg", str(dot_file), "-o", str(svg_file)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f"  ERROR rendering {name}: {result.stderr}")
        return False
    svg_kb = svg_file.stat().st_size / 1024
    print(f"  SVG: {svg_file.name} ({svg_kb:.0f} KB)")

    # Auto-crop SVG (remove excess viewBox padding)
    _crop_svg(str(svg_file))

    # Render standard PNG (300 DPI)
    result = subprocess.run(
        ["dot", f"-Tpng", f"-Gdpi={dpi}", str(dot_file), "-o", str(png_file)],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        png_kb = png_file.stat().st_size / 1024
        print(f"  PNG (300dpi): {png_file.name} ({png_kb:.0f} KB)")
    else:
        print(f"  WARN: PNG 300dpi failed: {result.stderr}")

    # Render high-resolution PNG (600 DPI for print/publication)
    result = subprocess.run(
        ["dot", f"-Tpng", f"-Gdpi={high_dpi}", str(dot_file), "-o", str(png_hires_file)],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        hires_kb = png_hires_file.stat().st_size / 1024
        print(f"  PNG (600dpi): {png_hires_file.name} ({hires_kb:.0f} KB)")
    else:
        print(f"  WARN: PNG 600dpi failed: {result.stderr}")

    return True


def _crop_svg(svg_path):
    """Auto-crop an SVG by adjusting the viewBox to content bounds.

    Removes excess white margins around the diagram content.
    """
    try:
        import re
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg = f.read()

        # Find viewBox
        vb_match = re.search(r'viewBox="([^"]*)"', svg)
        if not vb_match:
            return

        # Parse viewBox values: "min_x min_y width height"
        parts = vb_match.group(1).split()
        if len(parts) != 4:
            return

        min_x, min_y, width, height = map(float, parts)

        # Find all content bounding boxes
        content_x_min = float('inf')
        content_x_max = float('-inf')
        content_y_min = float('inf')
        content_y_max = float('-inf')

        # Check polygon/ellipse/rect/path bounds
        for tag_pattern in [r'<polygon[^>]*>', r'<ellipse[^>]*>', r'<rect[^>]*>',
                            r'<path[^>]*>', r'<text[^>]*>.*?</text>']:
            for match in re.finditer(tag_pattern, svg, re.DOTALL):
                elem = match.group()
                # Check transform
                tx, ty = 0, 0
                t_match = re.search(r'transform="[^"]*translate\(([^)]+)\)', elem)
                if t_match:
                    t_parts = t_match.group(1).replace(',', ' ').split()
                    if len(t_parts) >= 2:
                        tx, ty = float(t_parts[0]), float(t_parts[1])

                # Check for points attribute (polygon)
                pts_match = re.search(r'points="([^"]*)"', elem)
                if pts_match:
                    pts = pts_match.group(1).strip()
                    pairs = pts.split()
                    for p in pairs:
                        if ',' in p:
                            px, py = map(float, p.split(','))
                            content_x_min = min(content_x_min, px + tx)
                            content_x_max = max(content_x_max, px + tx)
                            content_y_min = min(content_y_min, py + ty)
                            content_y_max = max(content_y_max, py + ty)

                # Check for x/y attributes
                x_match = re.search(r'\bx="([^"]*)"', elem)
                y_match = re.search(r'\by="([^"]*)"', elem)
                w_match = re.search(r'\bwidth="([^"]*)"', elem)
                h_match = re.search(r'\bheight="([^"]*)"', elem)

                if x_match and y_match:
                    ex = float(x_match.group(1)) + tx
                    ey = float(y_match.group(1)) + ty
                    content_x_min = min(content_x_min, ex)
                    content_y_min = min(content_y_min, ey)

                    if w_match and h_match:
                        ew = float(w_match.group(1))
                        eh = float(h_match.group(1))
                        content_x_max = max(content_x_max, ex + ew)
                        content_y_max = max(content_y_max, ey + eh)
                    else:
                        # Estimate text element width
                        text_match = re.search(r'>([^<]*)</text>', elem)
                        if text_match:
                            text_len = len(text_match.group(1))
                            est_width = text_len * 7
                            est_height = 14
                            content_x_max = max(content_x_max, ex + est_width)
                            content_y_max = max(content_y_max, ey + est_height)

        if (content_x_min == float('inf') or content_y_min == float('inf')):
            return  # No content found, skip cropping

        # Add small padding (5% of content size, minimum 20px)
        pad_x = max(20, (content_x_max - content_x_min) * 0.05)
        pad_y = max(20, (content_y_max - content_y_min) * 0.05)

        new_min_x = content_x_min - pad_x
        new_min_y = content_y_min - pad_y
        new_width = content_x_max - content_x_min + 2 * pad_x
        new_height = content_y_max - content_y_min + 2 * pad_y

        # Update viewBox
        new_vb = f'viewBox="{new_min_x:.1f} {new_min_y:.1f} {new_width:.1f} {new_height:.1f}"'
        svg = svg.replace(vb_match.group(0), new_vb)

        # Also update width/height attributes if present
        w_attr = re.search(r'width="([^"]*)"', svg)
        h_attr = re.search(r'height="([^"]*)"', svg)
        if w_attr and h_attr:
            svg = svg.replace(w_attr.group(0), f'width="{new_width:.0f}pt"')
            svg = svg.replace(h_attr.group(0), f'height="{new_height:.0f}pt"')

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg)

    except Exception as e:
        print(f"    Note: SVG crop skipped ({e})")


# ── Diagram Definitions ─────────────────────────────────────────

def diagram_overall_system():
    """Overall System Architecture — high-level view."""
    return """
    label="Figure 1 — Overall System Architecture: End-to-End AI Vessel Routing System";
    fontsize="14";
    fontname="Arial Bold";

    subgraph "cluster_frontend" {
        label="Frontend (React + Vite)";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        ui_layout[label="UI Layout\n(MaritimeDashboard)", shape="box3d"];
        ws_client[label="WebSocket Client\n(websocketManager.js)", shape="box3d"];
        state[label="State Management\n(useOptimizationState)", shape="box3d"];
        api_client[label="API Client\n(apiClient.js)", shape="box3d"];
        runtime[label="Runtime Adapter\n(runtimeAdapter.js)", shape="box3d"];

        ui_layout -> ws_client [style="dashed", label="subscribe"];
        ui_layout -> state;
        state -> api_client [label="fetch"];
        state -> runtime;
        api_client -> runtime [label="normalize"];
        ws_client -> state [style="dashed", label="events"];
    }

    subgraph "cluster_backend" {
        label="Backend (FastAPI + WebSockets)";
        style="filled";
        fillcolor="#fef2f2";
        color="#ef4444";
        fontname="Arial Bold";
        fontsize="11";

        fastapi[label="FastAPI Server\n(main.py / server.py)", shape="box3d"];
        ws_manager[label="WebSocket Manager", shape="box3d"];
        routes[label="REST API Routes\n/metrics /pipeline /regions", shape="box3d"];
        services[label="Backend Services\nOptimization / Pipeline", shape="box3d"];
        api_models[label="Pydantic API Models", shape="box3d"];

        fastapi -> routes;
        fastapi -> ws_manager;
        fastapi -> services;
        routes -> api_models;
        services -> api_models;
    }

    subgraph "cluster_agents" {
        label="Multi-Agent AI Layer";
        style="filled";
        fillcolor="#f5f3ff";
        color="#8b5cf6";
        fontname="Arial Bold";
        fontsize="11";

        orchestrator[label="OrchestratorAgent\n(Master Controller)", shape="box3d",
                      fillcolor="#ede9fe", color="#7c3aed"];
        coordinator[label="CoordinatorAgent\n(Global Decisions)", shape="box3d",
                     fillcolor="#ede9fe", color="#7c3aed"];
        regional[label="RegionalAgent ×5\n(Asia, Europe, Americas, ME, Africa)", shape="box3d",
                  fillcolor="#ede9fe", color="#7c3aed"];
        svcgen[label="ServiceGeneratorAgent\n(Service Design)", shape="box3d",
                fillcolor="#ede9fe", color="#7c3aed"];

        orchestrator -> coordinator [label="aggregate\nresults"];
        orchestrator -> regional [label="dispatch\nper region"];
        regional -> svcgen [label="generate\nservices"];
        coordinator -> orchestrator [label="decisions\n+ feedback"];
    }

    subgraph "cluster_optimization" {
        label="Optimization Engine";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        ga[label="Hierarchical GA\nServiceGA + FrequencyGA\n(PyGAD/pynsga2)", shape="box3d"];
        milp[label="HubMILP Solver\n(PuLP + CBC)", shape="box3d"];
        flow_opt[label="FlowOptimizer\nMetrics Calculator", shape="box3d"];

        ga -> milp [label="optimal\nfrequencies"];
        milp -> flow_opt [label="results"];
    }

    subgraph "cluster_data" {
        label="Data Layer";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        csv[label="CSV Data Sources\nPorts, Demand, Fleet, Distance", shape="folder"];
        network_loader[label="NetworkLoader\n(CSV → Dataclasses)", shape="box3d"];
        problem[label="Problem\n(Port, Service, Demand, Distance)", shape="box3d"];
        clustering[label="Decomposition\nPortClustering + RegionalSplitter", shape="box3d"];
        output[label="pipeline_output.json\n(Runtime Results)", shape="note"];

        csv -> network_loader;
        network_loader -> problem;
        problem -> clustering;
        clustering -> output [style="dashed"];

        problem -> orchestrator [style="dashed", label="loads"];
        output -> fastapi [style="dashed", label="serves"];
    }

    subgraph "cluster_validation" {
        label="Validation Layer";
        style="filled";
        fillcolor="#fff7ed";
        color="#f97316";
        fontname="Arial Bold";
        fontsize="11";

        weights[label="Weight Validator", shape="box3d"];
        archetype[label="Archetype Validator", shape="box3d"];
        policy[label="Regional Policy Validator", shape="box3d"];
        consensus[label="ConsensusEngine\n(Weighted Voting)", shape="box3d"];

        weights -> consensus [style="dashed"];
        archetype -> consensus [style="dashed"];
        policy -> consensus [style="dashed"];
    }

    subgraph "cluster_llm" {
        label="LLM Integration";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        llm_client[label="LLMClient\n(OpenAI-compatible API)", shape="box3d"];
        llm_eval[label="LLMEvaluator\n(Scoring + Fallback)", shape="box3d"];
        llm_metrics[label="LLMMetrics\n(Runtime Stats)", shape="box3d"];

        llm_client -> llm_eval [label="evaluate"];
        llm_eval -> llm_metrics [label="record"];
    }

    # Cross-cluster edges
    ws_client -> fastapi [style="dashed", label="WS /ws"];
    api_client -> fastapi [label="HTTP"];
    orchestrator -> ga [style="dashed", label="dispatch", color="#22c55e"];
    orchestrator -> milp [style="dashed", label="dispatch", color="#22c55e"];
    regional -> coordinator [style="dashed", color="#8b5cf6"];
    orchestrator -> llm_client [style="dashed", label="LLM calls", color="#ec4899"];
    regional -> llm_client [style="dashed", label="LLM calls", color="#ec4899"];

    # File interaction
    output -> ui_layout [style="dashed", label="HTTP GET", color="#eab308"];
    problem -> consensus [style="dashed"];
    consensus -> coordinator [style="dashed", label="reconciled\nweights"];
"""


def diagram_multi_agent():
    """Multi-Agent AI Architecture — detailed agent interactions."""
    return """
    label="Figure 2 — Multi-Agent AI Architecture: Agent Responsibilities and Communication Flow";
    fontsize="14";
    fontname="Arial Bold";
    ranksep="0.7";

    subgraph "cluster_input" {
        label="Input";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        input_problem[label="Problem Object\nPorts, Demands, Fleet", fillcolor="#dbeafe"];
    }

    subgraph "cluster_orch" {
        label="OrchestratorAgent (Master Controller)";
        style="filled";
        fillcolor="#ede9fe";
        color="#7c3aed";
        fontname="Arial Bold";
        fontsize="11";

        analyze[label="analyze_problem()\nLLM: Problem Analysis", shape="box3d"];
        decompose[label="PortClustering (K=5)\n+ RegionalSplitter", shape="box3d"];
        iterate[label="Iteration Loop\n(max×3 iterations)", shape="box3d",
                fillcolor="#f5f3ff"];
        aggregate[label="aggregate_results()\nSum regional outputs", shape="box3d"];
        feedback[label="_apply_feedback()\nWeight adjustments", shape="box3d"];

        analyze -> decompose;
        decompose -> iterate;
        iterate -> aggregate;
        aggregate -> feedback;
        feedback -> iterate [style="dashed", label="next\niteration"];
    }

    subgraph "cluster_regional" {
        label="RegionalAgent ×5 (Asia, Europe, Americas, ME, Africa)";
        style="filled";
        fillcolor="#f5f3ff";
        color="#a78bfa";
        fontname="Arial Bold";
        fontsize="11";

        strategy[label="LLM: Generate Strategy\n(A/B/C based on demand)", shape="box3d"];
        svcgen_inner[label="ServiceGeneratorAgent\nLLM: Archetype params", shape="box3d"];
        ga_opt[label="HierarchicalGA\nServiceGA + FrequencyGA", shape="box3d"];
        milp_opt[label="HubMILP\n(Aggregate ↔ Hub clusters)", shape="box3d"];
        explain[label="LLM: Generate Explanation\n(Verdict/Actions)", shape="box3d"];
        policy_gen[label="Derive Regional Policy\nDeterministic metrics → policy", shape="box3d"];

        strategy -> svcgen_inner;
        svcgen_inner -> ga_opt;
        ga_opt -> milp_opt;
        milp_opt -> explain;
        explain -> policy_gen;
    }

    subgraph "cluster_coord" {
        label="CoordinatorAgent (Global Coordination)";
        style="filled";
        fillcolor="#eef2ff";
        color="#6366f1";
        fontname="Arial Bold";
        fontsize="11";

        conflicts[label="identify_conflicts()\nService overlap detection", shape="box3d"];
        resolve[label="resolve_conflicts()\nDrop lower-profit services", shape="box3d"];
        global_metrics[label="calculate_global_metrics()\nAggregate metrics", shape="box3d"];
        eval[label="evaluate_system()\nScore 0-5", shape="box3d"];
        decisions[label="generate_decisions()\nLLM + fallback\nWeight adjustments", shape="box3d"];
        feedback_sig[label="generate_feedback_signals()\nGradient feedback", shape="box3d"];

        conflicts -> resolve;
        resolve -> global_metrics;
        global_metrics -> eval;
        eval -> decisions;
        decisions -> feedback_sig;
    }

    subgraph "cluster_consensus" {
        label="ConsensusEngine (Weighted Reconciliation)";
        style="filled";
        fillcolor="#fff7ed";
        color="#f97316";
        fontname="Arial Bold";
        fontsize="11";

        weight_conflict[label="detect_weight_disparity()\nProfit vs Coverage", shape="box3d"];
        archetype_conflict[label="detect_archetype_mismatch()\nFeeder vs Direct", shape="box3d"];
        hub_conflict[label="detect_hub_conflict()\nHub set mismatch", shape="box3d"];
        reconcile_weights[label="reconcile_weights()\nCoord 0.4 + Regional 0.4 + SvcGen 0.2", shape="box3d"];
        confidence[label="compute_confidence()\nScore 0.0 - 1.0", shape="box3d"];

        weight_conflict -> reconcile_weights;
        archetype_conflict -> reconcile_weights;
        hub_conflict -> reconcile_weights;
        reconcile_weights -> confidence;
    }

    subgraph "cluster_output" {
        label="Output";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        pipeline_output[label="pipeline_output.json\nRegional results\nGlobal metrics\nConsensus result\nLLM metrics", shape="note",
                        fillcolor="#d1fae5"];
    }

    # Cross-graph edges
    input_problem -> analyze;
    decompose -> strategy [label="sub-problem\nper region"];
    iterate -> conflicts;
    svcgen_inner -> strategy [style="dashed", label="feeds back"];
    milp_opt -> aggregate;
    feedback_sig -> feedback;
    decisions -> reconcile_weights [label="conflicts"];
    policy_gen -> reconcile_weights [style="dashed"];
    aggregate -> pipeline_output;
    confidence -> pipeline_output;
    milp_opt -> pipeline_output [style="dashed"];

    # LLM connections
    analyze -> llm [style="dashed", label="LLM call", color="#ec4899"];
    strategy -> llm [style="dashed", label="LLM call", color="#ec4899"];
    svcgen_inner -> llm [style="dashed", label="LLM call", color="#ec4899"];
    explain -> llm [style="dashed", label="LLM call", color="#ec4899"];
    decisions -> llm [style="dashed", label="LLM call", color="#ec4899"];

    llm[label="LLMClient", shape="cylinder",
        fillcolor="#fce7f3", color="#ec4899", style="filled"];
"""


def diagram_backend_architecture():
    """Backend FastAPI architecture with routes and services."""
    return """
    label="Figure 3 — Backend Service Architecture: FastAPI Routes, Services, and WebSocket Communication";
    fontsize="14";
    fontname="Arial Bold";

    subgraph "cluster_apps" {
        label="Application Entry Points";
        style="filled";
        fillcolor="#fef2f2";
        color="#ef4444";
        fontname="Arial Bold";
        fontsize="11";

        main_app[label="main.py\n(FastAPI app v1, 597 lines)", shape="box3d",
                  fillcolor="#fecaca"];
        unified_app[label="unified_main.py\n(FastAPI app v2, 1280 lines)", shape="box3d",
                    fillcolor="#fecaca"];
        server_app[label="server.py\n(FastAPI app v3, 618 lines)", shape="box3d",
                   fillcolor="#fecaca"];
    }

    subgraph "cluster_routes" {
        label="API Routes (APIRouter modules)";
        style="filled";
        fillcolor="#ffe4e6";
        color="#f43f5e";
        fontname="Arial Bold";
        fontsize="11";

        metrics_routes[label="routes/metrics.py\nSummary, Profit, Coverage, Service", shape="box3d"];
        pipeline_routes[label="routes/pipeline.py\nStatus, Start/Stop, Iterations", shape="box3d"];
        regions_routes[label="routes/regions.py\nRegion details, Hubs, Optimize", shape="box3d"];
        ws_routes[label="routes/websocket.py\nSubscribe, Ping, StartPipeline", shape="box3d"];
    }

    subgraph "cluster_services" {
        label="Backend Services";
        style="filled";
        fillcolor="#ffe4e6";
        color="#f43f5e";
        fontname="Arial Bold";
        fontsize="11";

        opt_service[label="optimization_service.py", shape="box3d"];
        pipe_service[label="pipeline_service.py", shape="box3d"];
        pipe_streamer[label="pipeline_streamer.py\nService-level streaming", shape="box3d"];
    }

    subgraph "cluster_core" {
        label="Core Backend Modules";
        style="filled";
        fillcolor="#fecaca";
        color="#dc2626";
        fontname="Arial Bold";
        fontsize="11";

        ws_manager[label="websocket_manager.py\nConnection manager", shape="box3d"];
        event_schemas[label="event_schemas.py\n19 typed events", shape="box3d"];
        event_validator[label="event_validator.py\nValidation logic", shape="box3d"];
        api_models_back[label="api_models.py\nPydantic models", shape="box3d"];
        integration[label="real_orchestrator_integration.py\nBackend ↔ src bridge", shape="box3d"];
    }

    subgraph "cluster_external" {
        label="External / File Output";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        pipeline_json[label="pipeline_output.json\nRuntime truth data", shape="note"];
        frontend_client[label="Frontend React App\n(fetch + WebSocket)", shape="box3d"];
    }

    # Connections
    main_app -> metrics_routes [style="dashed", label="NOT\nregistered"];
    main_app -> ws_manager;
    unified_app -> ws_manager;
    server_app -> opt_service;
    server_app -> pipe_service;

    opt_service -> integration;
    pipe_service -> integration;
    pipe_streamer -> pipe_service;

    ws_manager -> event_schemas;
    ws_manager -> event_validator;
    integration -> pipeline_json;

    pipeline_json -> frontend_client [label="GET"];
    ws_manager -> frontend_client [label="WS /ws"];
    pipe_service -> ws_manager;

    # Labels for inactive routes
    metrics_routes -> pipeline_routes [style="dotted", label="(router code exists,\nnot connected)", color="#999"];
    pipeline_routes -> regions_routes [style="dotted", color="#999"];
    ws_routes -> ws_manager [style="dotted", color="#999"];
"""


def diagram_frontend_architecture():
    """Frontend React component hierarchy."""
    return """
    label="Figure 4 — Frontend Component Architecture: React Dashboard Hierarchy and State Flow";
    fontsize="14";
    fontname="Arial Bold";
    ranksep="0.3";
    nodesep="0.3";

    subgraph "cluster_entry" {
        label="Entry";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        entry[label="main.jsx → MaritimeDashboard.jsx", shape="box3d"];
        error_boundary[label="ErrorBoundary.jsx\nReact.Component (class)", shape="box3d"];
    }

    subgraph "cluster_hooks" {
        label="State Management";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        state_hook[label="useOptimizationState.js\nCentral state hook\n(useState + useCallback)", shape="box3d",
                   fillcolor="#fef08a"];
        runtime_adapter[label="runtimeAdapter.js\nData normalization\nCamelCase converter", shape="box3d"];
        local_state[label="14 views managed via\nsingle optimizationState prop", shape="box3d"];
    }

    subgraph "cluster_services_front" {
        label="Services";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        api_client[label="apiClient.js\nFetch-based REST client\n7 endpoints", shape="box3d"];
        ws_client[label="websocketManager.js\nEvent-driven pub/sub\n12 event types", shape="box3d"];
    }

    subgraph "cluster_components" {
        label="UI Components (14 Navigation Views)";
        style="filled";
        fillcolor="#fffbeb";
        color="#f59e0b";
        fontname="Arial Bold";
        fontsize="11";
        rank="same";

        overview[label="LandingView\nKpiCard ×6\nWorldMap", shape="box3d",
                 fillcolor="#fef3c7"];
        fleet[label="FleetDashboard\nFleetPanel", shape="box3d",
              fillcolor="#fef3c7"];
        routes[label="RouteTable", shape="box3d",
               fillcolor="#fef3c7"];
        ports[label="PortPanel", shape="box3d",
              fillcolor="#fef3c7"];
        pipeline[label="PipelineView\nFunnelView\nRegionPipelineNode", shape="box3d",
                 fillcolor="#fef3c7"];
        regional[label="RegionDetails\nRegionalIntelligence\nRegionCard", shape="box3d",
                 fillcolor="#fef3c7"];
        feedback[label="FeedbackView\nDecisionTrace\nDecisionExplanation", shape="box3d",
                 fillcolor="#fef3c7"];
        conflict[label="ConflictView", shape="box3d",
                 fillcolor="#fef3c7"];
        map[label="WorldMap\n(react-simple-maps)", shape="box3d",
            fillcolor="#fef3c7"];
        scenarios[label="ScenarioWorkspace", shape="box3d",
                  fillcolor="#fef3c7"];
        summary[label="SummaryView\nBackendCertification", shape="box3d",
                fillcolor="#fef3c7"];
        common[label="Common Components:\nSparkline, Counter\nProgressBar, PulseDot", shape="box3d",
               fillcolor="#fef3c7"];
    }

    subgraph "cluster_layout" {
        label="Layout";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        header[label="Header", shape="box3d", width="1.2"];
        sidebar[label="Sidebar\n(14 nav items)", shape="box3d", width="1.2"];
        footer[label="Footer", shape="box3d", width="1.2"];
    }

    # Connections
    entry -> error_boundary;
    error_boundary -> header;
    header -> sidebar;
    sidebar -> overview [label="renderMain()\nswitch case"];
    overview -> fleet [style="dashed"];
    fleet -> routes [style="dashed"];
    routes -> ports [style="dashed"];
    ports -> pipeline [style="dashed"];
    pipeline -> regional [style="dashed"];
    regional -> feedback [style="dashed"];
    feedback -> conflict [style="dashed"];
    conflict -> map [style="dashed"];
    map -> scenarios [style="dashed"];
    scenarios -> summary [style="dashed"];

    entry -> state_hook [style="dotted", label="passes", color="#999"];
    state_hook -> api_client;
    state_hook -> ws_client;
    state_hook -> runtime_adapter;
    state_hook -> local_state;

    local_state -> overview [style="dashed", label="optimization\nState"];
    local_state -> fleet [style="dashed"];
    local_state -> pipeline [style="dashed"];
    local_state -> regional [style="dashed"];

    header -> footer [style="dotted", color="#ccc"];
"""


def diagram_optimization_pipeline():
    """Optimization pipeline — GA + MILP + Aggregation flow."""
    return """
    label="Figure 5 — Optimization Pipeline: Genetic Algorithm and MILP Solver Workflow";
    fontsize="14";
    fontname="Arial Bold";

    subgraph "cluster_input" {
        label="Input";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        input_svc[label="Candidate Services\n(ServiceGeneratorAgent)\n800-2000 candidates", fillcolor="#dbeafe"];
        input_demand[label="Regional Demand\nFiltered to region ports", fillcolor="#dbeafe"];
        input_fleet[label="Fleet Specification\n6 classes, 501 vessels", fillcolor="#dbeafe"];
    }

    subgraph "cluster_filter" {
        label="Service Filtering";
        style="filled";
        fillcolor="#e0e7ff";
        color="#6366f1";
        fontname="Arial Bold";
        fontsize="11";

        profitability[label="Profitability Gate\nRevenue - Cost > 0\nRemove negative-margin", shape="box3d"];
    }

    subgraph "cluster_ga" {
        label="Hierarchical Genetic Algorithm";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        svc_ga[label="ServiceGA\nChromosome: Binary [0,1,0,1,...]\nPopulation: 80\nSelection: Elite 10 (heapq)\nCrossover: Single-point\nMutation: Demand-biased\nEarly stop: 8 gens / 90s",
               shape="box3d", fillcolor="#bbf7d0"];
        freq_ga[label="FrequencyGA\nChromosome: Integer [0,1,2,3,...]\nFleet constraint: ≤300 vessels\nAnalytical initialization\nEarly stop: 8 gens / 90s",
                shape="box3d", fillcolor="#bbf7d0"];
        fitness[label="Fitness Function\nwₚ·profit + w_c·coverage - wₖ·cost\n- Penalties: overcap, unserved",
                shape="box3d", fillcolor="#bbf7d0"];

        svc_ga -> freq_ga [label="selected\nservices"];
        svc_ga -> fitness [style="dashed"];
        freq_ga -> fitness [style="dashed"];
    }

    subgraph "cluster_milp" {
        label="MILP Optimization";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        hub_detect[label="HubDetector\nDemand-based hub scoring", shape="box3d"];
        hub_milp[label="HubMILP\n(PuLP + CBC Solver)\nDecision: flow, transfer_flow, unserved\nObjective: profit + coverage_reward\nTime limit: 120s",
                 shape="box3d", fillcolor="#86efac"];
        transship[label="Transshipment Pairs\nPrioritized by hub demand",
                  shape="box3d"];
        constraints[label="Constraints:\n- Demand satisfaction\n- Service capacity\n- Port capacity\n- Fleet size ≤300",
                    shape="box3d"];

        hub_detect -> hub_milp;
        hub_milp -> transship [style="dashed"];
        hub_milp -> constraints [style="dashed"];
    }

    subgraph "cluster_post" {
        label="Post-Processing";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        flow_opt[label="FlowOptimizer\nRevenue, costs, coverage", shape="box3d"];
        regional_metrics[label="RegionalMetrics\n10 deterministic metrics", shape="box3d"];
        coverage_est[label="Coverage Estimation\n70% target threshold", shape="box3d"];
    }

    subgraph "cluster_output" {
        label="Output";
        style="filled";
        fillcolor="#f0fdf4";
        color="#16a34a";
        fontname="Arial Bold";
        fontsize="11";

        regional_result[label="Regional Result\nSelected services\nFrequencies\nMetrics\nPolicy\nExplanation", shape="note"];
    }

    # Connections
    input_svc -> profitability;
    input_demand -> profitability;
    input_fleet -> profitability;
    profitability -> svc_ga;
    freq_ga -> hub_detect;
    hub_milp -> flow_opt;
    flow_opt -> regional_metrics;
    flow_opt -> coverage_est;
    regional_metrics -> regional_result;
    coverage_est -> regional_result;
"""


def diagram_data_flow():
    """End-to-end data flow from CSV to dashboard."""
    return """
    label="Figure 6 — End-to-End Data Processing Flow: From Raw CSV to Dashboard Visualization";
    fontsize="14";
    fontname="Arial Bold";
    ranksep="0.5";

    subgraph "cluster_sources" {
        label="Data Sources";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        ports[label="ports.csv\n333 ports, 11 columns\nUNLocode, Coords, Costs", shape="folder"];
        demand[label="demand.csv\n40K+ entries\nOrigin, Dest, Volume, Revenue", shape="folder"];
        fleet[label="fleet.csv\n6 classes, 501 vessels\nCapacity, Speed, Cost", shape="folder"];
        distance[label="distance.csv\nPort-to-port matrix", shape="folder"];
    }

    subgraph "cluster_loading" {
        label="Data Loading";
        style="filled";
        fillcolor="#dbeafe";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        network_loader[label="NetworkLoader\nnetwork_loader.py\nTAB-separated CSV parsing", shape="box3d"];
        port_mapping[label="Port Mapping\nport_mapping.csv\nInteger ID ↔ UNLocode", shape="box3d"];
    }

    subgraph "cluster_model" {
        label="Data Model";
        style="filled";
        fillcolor="#dbeafe";
        color="#2563eb";
        fontname="Arial Bold";
        fontsize="11";

        port_obj[label="Port dataclass\nUNLocode, Name, Country\nRegion, Coords, Cost", shape="box3d"];
        demand_obj[label="Demand dataclass\nOrigin, Dest, FFEPerWeek, Revenue, Transit", shape="box3d"];
        service_obj[label="Service dataclass\nPorts, TT, Capacity, Frequency, Cost", shape="box3d"];
        problem[label="Problem dataclass\nports, services, demands\ndistance_matrix", shape="box3d",
                fillcolor="#93c5fd"];
    }

    subgraph "cluster_processing" {
        label="Processing Pipeline";
        style="filled";
        fillcolor="#e0e7ff";
        color="#6366f1";
        fontname="Arial Bold";
        fontsize="11";

        clustering[label="PortClustering.py\nKMeans (k=5)", shape="box3d"];
        splitter[label="RegionalSplitter.py\nPer-cluster sub-problems", shape="box3d"];
        preprocess[label="preprocess.py\nPandas transformations", shape="box3d"];
        graph_builder[label="graph_builder.py\nNumPy distance utilities", shape="box3d"];
    }

    subgraph "cluster_runtime" {
        label="Runtime Execution";
        style="filled";
        fillcolor="#f0fdf4";
        color="#22c55e";
        fontname="Arial Bold";
        fontsize="11";

        agent_opt[label="Multi-Agent Optimization\nOrchestrator → Regional → Coordinator", shape="box3d"];
        health_tracker[label="HealthTracker\nSingleton runtime monitor", shape="box3d"];
    }

    subgraph "cluster_output" {
        label="Output Generation";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        pipeline_json[label="pipeline_output.json\nComplete runtime state", shape="note"];
    }

    subgraph "cluster_dashboard" {
        label="Dashboard Rendering";
        style="filled";
        fillcolor="#fefce8";
        color="#eab308";
        fontname="Arial Bold";
        fontsize="11";

        rest_api[label="REST API\n/status, /metrics, /regions", shape="box3d"];
        ws_events[label="WebSocket Events\n12 event types\nReal-time streaming", shape="box3d"];
        react_dash[label="React Dashboard\nMaritimeDashboard.jsx\n240 lines", shape="box3d"];
    }

    # Flow
    ports -> network_loader;
    demand -> network_loader;
    fleet -> network_loader;
    distance -> network_loader;
    port_mapping -> network_loader [style="dashed"];

    network_loader -> port_obj;
    network_loader -> demand_obj;
    port_obj -> problem;
    demand_obj -> problem;
    service_obj -> problem;

    problem -> clustering;
    clustering -> splitter;
    splitter -> agent_opt;
    agent_opt -> health_tracker;
    agent_opt -> pipeline_json;
    preprocess -> problem [style="dashed"];
    graph_builder -> clustering [style="dashed"];

    pipeline_json -> rest_api;
    pipeline_json -> ws_events;
    rest_api -> react_dash;
    ws_events -> react_dash;
"""


def diagram_validation_pipeline():
    """Validation layer architecture."""
    return """
    label="Figure 7 — Validation Pipeline: Multi-Layer Validation with AI Tagging";
    fontsize="14";
    fontname="Arial Bold";
    ranksep="0.6";

    subgraph "cluster_weights" {
        label="Weight Validation";
        style="filled";
        fillcolor="#fff7ed";
        color="#f97316";
        fontname="Arial Bold";
        fontsize="11";

        weight_validator[label="weight_validator.py\nvalidate_weight_adjustments()\nClamp, normalize\nProfit/Coverage/Cost", shape="box3d"];
        weight_tags[label="Tags: AI_GENERATED\nAI_VALIDATED / AI_REJECTED", shape="box3d"];
    }

    subgraph "cluster_archetype" {
        label="Archetype Validation";
        style="filled";
        fillcolor="#fff7ed";
        color="#f97316";
        fontname="Arial Bold";
        fontsize="11";

        archetype_validator[label="archetype_validator.py\nvalidate_archetype_params()\nMix ratios, vessel_bias, hub_focus", shape="box3d"];
        default_archetype[label="DEFAULT_ARCHETYPE_PARAMS\ndirect: 0.60, hub_loop: 0.15\nfeeder: 0.20, trunk: 0.05", shape="box3d"];
    }

    subgraph "cluster_policy" {
        label="Regional Policy Validation";
        style="filled";
        fillcolor="#fff7ed";
        color="#f97316";
        fontname="Arial Bold";
        fontsize="11";

        policy_v1[label="regional_policy_validator.py\nValidate policy keys + ranges", shape="box3d"];
        policy_v2[label="regional_policy_validator_v2.py\nAnti-neutral, metric citation\nVessel sanity, drift check", shape="box3d"];
        default_policy[label="DEFAULT_REGIONAL_POLICY\ncoverage: 0.6, profit: 0.4", shape="box3d"];
    }

    subgraph "cluster_consensus" {
        label="Consensus Engine";
        style="filled";
        fillcolor="#fff7ed";
        color="#ea580c";
        fontname="Arial Bold";
        fontsize="11";

        consensus[label="ConsensusEngine (975 lines)\nWeighted voting reconciliation", shape="box3d",
                 fillcolor="#fed7aa"];
        voting[label="Voting Weights:\nCoordinator: 0.4\nRegional: 0.4\nServiceGenerator: 0.2", shape="box3d"];
        confidence[label="Confidence Scoring:\n>0.7: ACCEPTED\n0.3-0.7: MODIFIED\n<0.3: REJECTED", shape="box3d"];
    }

    subgraph "cluster_ai_tags" {
        label="AI Log Tags";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        tags[label="AI_GENERATED | AI_VALIDATED | AI_REJECTED\nAI_FALLBACK | AI_APPLIED\nCONSENSUS_ACCEPTED | CONSENSUS_MODIFIED\nCONSENSUS_REJECTED", shape="box3d"];
    }

    # Connections
    weight_validator -> consensus;
    archetype_validator -> consensus;
    policy_v1 -> consensus;
    policy_v2 -> consensus;
    consensus -> confidence;
    confidence -> tags;
    weight_validator -> weight_tags;
    archetype_validator -> default_archetype [style="dashed"];
    policy_v1 -> default_policy [style="dashed"];
    consensus -> voting [style="dashed"];
"""


def diagram_llm_integration():
    """LLM client architecture with fallback chain."""
    return """
    label="Figure 8 — LLM Integration Architecture: Client, Evaluator, Metrics, and Fallback Chain";
    fontsize="14";
    fontname="Arial Bold";

    subgraph "cluster_client" {
        label="LLMClient";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        api_call[label="OpenAI-compatible API\nchat() method\nSystem + User messages", shape="box3d"];
        cache[label="MD5 Hash Cache\nmodel|system|message", shape="cylinder"];
        circuit_breaker[label="Circuit Breaker\n5 failures → 60s timeout", shape="box3d"];
        fallback[label="Fallback Chain:\n1. opencode/deepseek-v4-flash-free\n2. mimo-v2.5-free\n3. nemotron-3-ultra-free\n4. qwen3.6-plus-free\n5. minimax-m3-free",
                shape="box3d", fillcolor="#fbcfe8"];

        api_call -> fallback [label="retry\non failure"];
        api_call -> cache [style="dashed", label="check\nbefore call"];
        fallback -> circuit_breaker [style="dashed"];
    }

    subgraph "cluster_evaluator" {
        label="LLMEvaluator";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        structure[label="Structure Score (40%)\nContains 'Strategy' + 'Reason'", shape="box3d"];
        completeness[label="Completeness Score (30%)\nLine count threshold", shape="box3d"];
        relevance[label="Relevance Score (30%)\nDomain keywords\n(demand, port, hub, capacity)", shape="box3d"];
        threshold[label="Total < 0.5 → Hardcoded fallback", shape="box3d"];

        structure -> threshold;
        completeness -> threshold;
        relevance -> threshold;
    }

    subgraph "cluster_eval_manager" {
        label="EvaluatorManager";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        manager[label="Singleton wrapper\nLLMEvaluator proxy", shape="box3d"];
    }

    subgraph "cluster_metrics" {
        label="LLMMetrics";
        style="filled";
        fillcolor="#fce7f3";
        color="#ec4899";
        fontname="Arial Bold";
        fontsize="11";

        metrics[label="Runtime metrics:\nLLM calls per agent\nJSON parse success rate\nValidator execution count\nFallback count\nAI_GENERATED counters", shape="box3d"];
    }

    subgraph "cluster_agents_use" {
        label="Agent LLM Usage";
        style="filled";
        fillcolor="#f5f3ff";
        color="#8b5cf6";
        fontname="Arial Bold";
        fontsize="11";

        orchestrator_llm[label="Orchestrator: Problem Analysis\n+ Executive Summary\n(skip_evaluator=False)", shape="box3d"];
        coordinator_llm[label="Coordinator: Decision JSON\n(skip_evaluator=True → JSON fallback)", shape="box3d"];
        regional_llm[label="Regional: Strategy (A/B/C)\n+ Explanation (Verdict/Actions)", shape="box3d"];
        svcgen_llm[label="ServiceGenerator: Archetype Params\n(skip_evaluator=True → JSON fallback)", shape="box3d"];

        orchestrator_llm -> api_call;
        coordinator_llm -> api_call;
        regional_llm -> api_call;
        svcgen_llm -> api_call;
    }

    api_call -> manager [style="dashed"];
    manager -> threshold [style="dashed"];
    api_call -> metrics;
    threshold -> metrics;
"""


def diagram_configuration():
    """Configuration management and environment variables."""
    return """
    label="Figure 9 — Configuration Architecture: Environment Variables and Module Configuration";
    fontsize="14";
    fontname="Arial Bold";

    subgraph "cluster_env" {
        label="Environment Variables (.env)";
        style="filled";
        fillcolor="#f0f4ff";
        color="#3b82f6";
        fontname="Arial Bold";
        fontsize="11";

        api_key[label="OPENCODE_API_KEY\nOPENROUTER_API_KEY", shape="box3d"];
        llm_url[label="LLM_BASE_URL\n(opencode.ai/zen/v1)", shape="box3d"];
        models[label="ORCHESTRATOR_MODEL\nREGIONAL_MODEL", shape="box3d"];
        params[label="GA_POPULATION_SIZE (80)\nGA_GENERATIONS (120)\nMILP_TIME_LIMIT (120s)", shape="box3d"];
    }

    subgraph "cluster_config" {
        label="Config Module";
        style="filled";
        fillcolor="#dbeafe";
        color="#2563eb";
        fontname="Arial Bold";
        fontsize="11";

        config_util[label="utils/config.py\nConfig static class\nEnvironment variables\nDataclass-based", shape="box3d"];
        optimizer_config[label="config/optimizer_config.py\nObjectiveConfig dataclass\nCONFIG singleton", shape="box3d"];
    }

    subgraph "cluster_consumers" {
        label="Configuration Consumers";
        style="filled";
        fillcolor="#e0e7ff";
        color="#6366f1";
        fontname="Arial Bold";
        fontsize="11";

        llm_client_conf[label="LLMClient\nBase URL, API key\nModels, Temperature", shape="box3d"];
        ga_conf[label="HierarchicalGA / ServiceGA\nPopulation size, Generations\nStop criteria", shape="box3d"];
        milp_conf[label="HubMILP\nTime limit, Solver params", shape="box3d"];
        agent_conf[label="Agents\nModel selection\nTemperature (0.2)", shape="box3d"];
    }

    # Flow
    api_key -> config_util;
    llm_url -> config_util;
    models -> config_util [style="dashed"];
    params -> config_util;

    config_util -> optimizer_config;
    optimizer_config -> llm_client_conf;
    optimizer_config -> ga_conf;
    optimizer_config -> milp_conf;
    optimizer_config -> agent_conf;
    config_util -> agent_conf [style="dashed"];
"""


def diagram_repository_structure():
    """Repository directory structure."""
    return """
    label="Figure 10 — Repository Structure: Complete Project Organization";
    fontsize="14";
    fontname="Arial Bold";
    ranksep="0.3";
    nodesep="0.3";

    subgraph "cluster_root" {
        label="Project Root";
        style="filled";
        fillcolor="#f8fafc";
        color="#64748b";
        fontname="Arial Bold";
        fontsize="11";

        src[label="src/\n(Core Application)
    └── agents/        (Multi-agent system)
    ├── config/        (Optimizer config)
    ├── data/          (Data loading)
    ├── decomposition/ (Clustering)
    ├── llm/           (LLM integration)
    ├── optimization/  (GA + MILP solvers)
    ├── pipeline/      (empty - reserved)
    ├── services/      (Hub detection)
    ├── utils/         (Shared utilities)
    └── validation/    (All validators)", shape="box3d", fillcolor="#f1f5f9", width="2.5"];

        backend[label="backend/\n(FastAPI Server)
    ├── routes/        (4 API routers)
    ├── services/      (3 service modules)
    ├── main.py        (v1 server)
    ├── unified_main.py(v2 server)
    ├── server.py      (v3 server)
    ├── websocket_manager.py
    └── event_schemas.py", shape="box3d", fillcolor="#f1f5f9", width="2.5"];

        frontend[label="frontend/\n(React Dashboard)
    ├── src/components/
    ├── src/services/
    ├── src/hooks/
    ├── src/views/
    └── src/utils/", shape="box3d", fillcolor="#f1f5f9", width="2.5"];

        tests[label="tests/\n(14 test files)
    ├── test_orchestrator.py    (3947 lines)
    ├── test_multi_agent...     (1118 lines)
    ├── test_milp.py
    ├── test_ga.py
    ├── test_llm.py
    └── 9 more test files", shape="box3d", fillcolor="#f1f5f9", width="2.5"];

        data[label="data/
    ├── datasets/  (JSON problem files)
    └── raw/       (CSV source data)", shape="box3d", fillcolor="#f1f5f9", width="2.5"];

        scripts[label="scripts/\n(17 diagnostic scripts)", shape="box3d", fillcolor="#f1f5f9"];

        docs[label="docs/\n(Documentation)", shape="box3d", fillcolor="#f1f5f9"];

        docker[label="Dockerfile\nMulti-stage build\npython:3.10-slim", shape="box3d", fillcolor="#f1f5f9"];
    }

    src -> backend [style="dotted", label="imports", color="#6366f1"];
    backend -> frontend [style="dashed", label="REST/WS"];
    src -> tests [style="dotted", color="#22c55e"];
"""


# ── Render ──

def main():
    ensure_dirs()

    diagrams = [
        ("00_overall_system",     diagram_overall_system(),        "TB"),
        ("01_multi_agent",         diagram_multi_agent(),           "TB"),
        ("02_backend_architecture", diagram_backend_architecture(), "TB"),
        ("03_frontend_architecture", diagram_frontend_architecture(), "TB"),
        ("04_optimization_pipeline", diagram_optimization_pipeline(), "TB"),
        ("05_data_flow",           diagram_data_flow(),             "TB"),
        ("06_validation_pipeline", diagram_validation_pipeline(),   "TB"),
        ("07_llm_integration",     diagram_llm_integration(),       "TB"),
        ("08_configuration",       diagram_configuration(),         "TB"),
        ("09_repository_structure", diagram_repository_structure(), "TB"),
    ]

    print("=" * 60)
    print("Generating Architecture Diagrams (Graphviz DOT)")
    print("=" * 60)

    success = 0
    for name, dot, rankdir in diagrams:
        print(f"\n  [{name}]")
        if render_dot(dot, name, rankdir=rankdir):
            success += 1

    print(f"\n{'=' * 60}")
    print(f"Generated {success}/{len(diagrams)} architecture diagrams")
    print(f"  SVGs: {GRAPHVIZ_SVG_DIR}")
    print(f"  PNGs: {GRAPHVIZ_PNG_DIR}")
    print(f"{'=' * 60}")
    return 0 if success == len(diagrams) else 1


if __name__ == "__main__":
    sys.exit(main())
