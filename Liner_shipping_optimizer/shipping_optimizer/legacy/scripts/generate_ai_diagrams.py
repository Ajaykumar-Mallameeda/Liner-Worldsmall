#!/usr/bin/env python3
"""
AI Layer Diagram Generator — AI Vessel Routing System
Generates Graphviz DOT diagrams for the AI subsystem.
"""
import os, subprocess, sys
from pathlib import Path

GRAPHVIZ_DIR = Path("docs/generated/ai")
SVG_DIR = GRAPHVIZ_DIR / "svg"
PNG_DIR = GRAPHVIZ_DIR / "png"
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"

COLORS = {
    "bg": "#ffffff", "text": "#1a1a2e",
    "primary": "#00d4ff", "secondary": "#7c3aed", "tertiary": "#10b981",
    "warning": "#f59e0b", "danger": "#ef4444",
    "node_bg": "#f5f3ff", "node_border": "#8b5cf6",
    "agent_bg": "#ede9fe", "agent_border": "#6366f1",
    "llm_bg": "#fce7f3", "llm_border": "#ec4899",
    "data_bg": "#f0fdf4", "data_border": "#22c55e",
    "val_bg": "#fff7ed", "val_border": "#f97316",
}

def ensure_dirs():
    for d in [SVG_DIR, PNG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def render(dot_source, name):
    dot_file = GRAPHVIZ_DIR / f"{name}.dot"
    svg_file = SVG_DIR / f"{name}.svg"
    png_file = PNG_DIR / f"{name}.png"

    full = f"""digraph "{name}" {{
    rankdir=TB; layout=dot;
    bgcolor="{COLORS['bg']}"; fontname="Arial"; fontsize="16";
    labeljust="l"; compound=true; newrank=true;
    splines=ortho; overlap=false;
    nodesep="0.6"; ranksep="0.8"; margin="0"; pad="0.3";
    edge [fontname="Arial", fontsize="12", color="#555555", penwidth="1.5", arrowsize="1"];
    node [fontname="Arial", fontsize="12", shape="box", style="filled,rounded",
          fillcolor="{COLORS['node_bg']}", color="{COLORS['node_border']}", penwidth="1.5",
          margin="0.12,0.08"];

{dot_source}
}}"""
    dot_file.write_text(full, encoding="utf-8")
    ok = True
    for fmt, ext in [("svg", svg_file), ("png", png_file)]:
        r = subprocess.run(["dot", f"-T{fmt}", str(dot_file), "-o", str(ext)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"  ERR {name}->{fmt}: {r.stderr[:100]}")
            ok = False
        else:
            print(f"  {fmt.upper()}: {ext.name} ({ext.stat().st_size//1024}KB)")
    return ok


# ── Diagram 1: AI System Overview ──
def d1_overview():
    return """
    label="AI System Architecture: LLM Integration Points and Data Flow";
    fontsize="16"; fontname="Arial Bold";

    subgraph cluster_prompt {
        label="Prompt Engineering Layer";
        style="filled"; fillcolor="#f5f3ff"; color="#8b5cf6";
        fontsize="13"; fontname="Arial Bold";

        orch_sys[label="Orchestrator System Prompt\n(Master Controller)", shape="box3d"];
        coord_sys[label="Coordinator System Prompt\n(Decision Agent)", shape="box3d"];
        reg_sys[label="Regional System Prompt\n(Strategy Generator)", shape="box3d"];
        svc_sys[label="ServiceGen System Prompt\n(Archetype Designer)", shape="box3d"];
    }

    subgraph cluster_context {
        label="Context Engineering";
        style="filled"; fillcolor="#f5f3ff"; color="#8b5cf6";
        fontsize="13"; fontname="Arial Bold";

        analytics[label="Analysis Prompt\n(Metrics Injection)\nPorts, Demand, Density", shape="box3d"];
        strategy[label="Strategy Prompt\n(Regional Classification)\nA/B/C Types", shape="box3d"];
        decision[label="Decision Prompt\n(Weight JSON)\nProfit/Coverage/Cost", shape="box3d"];
        summary[label="Summary Prompt\n(Executive Report)\nGlobal Results", shape="box3d"];
    }

    subgraph cluster_llm {
        label="LLM Provider Layer";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899";
        fontsize="13"; fontname="Arial Bold";

        client[label="LLMClient\nSingleton Wrapper", shape="box3d"];
        cache[label="MD5 Response Cache\nmodel|system|message", shape="cylinder"];
        circuit[label="Circuit Breaker\n5 failures = 60s timeout", shape="box3d"];
        fallback[label="Fallback Chain\n5 model providers", shape="box3d"];
        api[label="OpenAI-Compatible API\nopencode.ai/zen/v1", shape="box3d"];
    }

    subgraph cluster_eval {
        label="Evaluation Layer";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899";
        fontsize="13"; fontname="Arial Bold";

        eval_mod[label="LLMEvaluator\nStructure 40% + Completeness 30%\n+ Relevance 30%", shape="box3d"];
        threshold[label="Threshold < 0.5\n-> Hardcoded Fallback", shape="box3d"];
        metrics[label="LLMMetrics\nCalls, Success, Failures\nPer Agent", shape="box3d"];
    }

    subgraph cluster_val {
        label="Validation Layer";
        style="filled"; fillcolor="#fff7ed"; color="#f97316";
        fontsize="13"; fontname="Arial Bold";

        weight_val[label="WeightValidator\nClamp + Normalize", shape="box3d"];
        arch_val[label="ArchetypeValidator\nMix Ratios, Sum=1.0", shape="box3d"];
        policy_val[label="PolicyValidator V2\nAnti-Neutral, Drift", shape="box3d"];
        consensus[label="ConsensusEngine\nWeighted Voting 0.4/0.4/0.2", shape="box3d"];
    }

    # Flow
    orch_sys -> analytics;
    coord_sys -> decision;
    reg_sys -> strategy;
    svc_sys -> strategy;
    analytics -> client;
    strategy -> client;
    decision -> client;
    summary -> client;
    client -> cache [style="dashed"];
    client -> api;
    api -> fallback [style="dashed"];
    api -> circuit [style="dashed"];
    client -> eval_mod [style="dashed"];
    eval_mod -> threshold;
    eval_mod -> metrics;
    client -> weight_val [style="dashed", label="weight output"];
    client -> arch_val [style="dashed", label="archetype output"];
    client -> policy_val [style="dashed", label="strategy output"];
    weight_val -> consensus;
    arch_val -> consensus;
    policy_val -> consensus;
    threshold -> metrics;
"""

# ── Diagram 2: Agent Architecture ──
def d2_agents():
    return """
    label="Multi-Agent Architecture: Roles, Responsibilities, and Communication Flow";
    fontsize="16"; fontname="Arial Bold";

    orchestrator[label="OrchestratorAgent\nMaster Controller\nModel: DeepSeek-v4-flash-free\nTemp: 0.1-0.3\nCalls: 2 per run\nFunctions: analyze, summarize, iterate",
                  shape="box3d", fillcolor="#c4b5fd", color="#7c3aed", fontsize="13"];

    coordinator[label="CoordinatorAgent\nGlobal Decision Agent\nModel: DeepSeek-v4-flash-free\nTemp: 0.3\nCalls: <=3 per run\nskip_evaluator: True\nFunctions: decide, evaluate, feedback",
                 shape="box3d", fillcolor="#c4b5fd", color="#7c3aed", fontsize="13"];

    regional[label="RegionalAgent x5\nAsia, Europe, Americas, ME, Africa\nModel: DeepSeek-v4-flash-free\nTemp: 0.2\nCalls: <=3 per region per run\nFunctions: strategize, explain",
              shape="box3d", fillcolor="#c4b5fd", color="#7c3aed", fontsize="13"];

    svcgen[label="ServiceGeneratorAgent\nService Archetype Designer\nModel: DeepSeek-v4-flash-free\nTemp: 0.2\nskip_evaluator: True\nFunctions: generate archetype params",
             shape="box3d", fillcolor="#c4b5fd", color="#7c3aed", fontsize="13"];

    subgraph cluster_prompts {
        label="Prompt Templates";
        style="filled"; fillcolor="#f5f3ff"; color="#a78bfa"; fontsize="12";
        fontname="Arial Bold";

        p_orch[label="System: 'Master Orchestrator...'\nAnalysis: Network stats, Top-5 corridors\nSummary: Global results, Verdict/Strengths\nValidation: Size, Complexity, Demand patterns", shape="box3d"];
        p_coord[label="System: 'Shipping network decision...'\nDecision: JSON actions/weights/adjustments\nFeedback: Gradient signals per weight\nValidation: Structured JSON, weight ranges", shape="box3d"];
        p_reg[label="System: 'Shipping analyst for {region}...'\nStrategy: Type A/B/C based on dispersion\nExplanation: Verdict/Strengths/Weaknesses\nValidation: Strategy keywords + citations", shape="box3d"];
        p_svc[label="System: 'Service design specialist...'\nOutput: Archetype mix JSON\ndirect_ratio, hub_loop_ratio, etc.\nValidation: Ratios sum=1.0", shape="box3d"];
    }

    subgraph cluster_llm_agents {
        label="LLM Infrastructure";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899"; fontsize="12";
        fontname="Arial Bold";

        client[label="LLMClient\nchat(model, system, user, temp)", shape="box3d"];
        cache[label="Response Cache\nMD5 hash lookup", shape="cylinder"];
        breaker[label="Circuit Breaker\n5 fail -> 60s cooldown", shape="box3d"];
        fallback[label="Provider Fallback Chain\n1. deepseek 2. mimo\n3. nemotron 4. qwen 5. minimax", shape="box3d"];
        evaluator[label="LLMEvaluator\n3-axis scoring\nFallback if <0.5", shape="box3d"];
    }

    subgraph cluster_output {
        label="AI Outputs Received By";
        style="filled"; fillcolor="#f0fdf4"; color="#22c55e"; fontsize="12";
        fontname="Arial Bold";

        ga[label="HierarchicalGA\nService selection weights", shape="box3d"];
        milp[label="HubMILP\nFlow optimization params", shape="box3d"];
        consensus[label="ConsensusEngine\nReconciled decisions", shape="box3d"];
        dashboard[label="Dashboard UI\nRuntime display", shape="box3d"];
    }

    # Agent hierarchy
    orchestrator -> coordinator [label="aggregate_resuts()\nregional_results\n"];
    orchestrator -> regional [label="dispatch()\nsub_problems"];
    regional -> svcgen [label="generate_services()"];

    # LLM calls
    orchestrator -> client [label="LLM: analysis + summary", color="#ec4899"];
    coordinator -> client [label="LLM: decisions JSON", color="#ec4899"];
    regional -> client [label="LLM: strategy + explanation", color="#ec4899"];
    svcgen -> client [label="LLM: archetype params", color="#ec4899"];

    # Prompt source
    orchestrator -> p_orch [style="dotted", color="#8b5cf6"];
    coordinator -> p_coord [style="dotted", color="#8b5cf6"];
    regional -> p_reg [style="dotted", color="#8b5cf6"];
    svcgen -> p_svc [style="dotted", color="#8b5cf6"];

    # LLM internals
    client -> cache [style="dashed"];
    client -> fallback [style="dashed"];
    client -> breaker [style="dashed"];
    client -> evaluator [style="dashed", label="if not\nskip_evaluator"];

    # Output destinations
    coordinator -> consensus [label="decision JSON"];
    regional -> ga [label="strategy"];
    svcgen -> ga [label="archetype\nparams"];
    ga -> milp;
    milp -> dashboard;
    consensus -> dashboard;
"""

# ── Diagram 3: Prompt Flow ──
def d3_prompt_flow():
    return """
    label="LLM Prompt Execution Flow: From User Request to Validated Response";
    fontsize="16"; fontname="Arial Bold";
    ranksep="0.6";

    subgraph cluster_orch {
        label="Agent Layer";
        style="filled"; fillcolor="#f5f3ff"; color="#8b5cf6"; fontsize="12";
        fontname="Arial Bold";

        request[label="Agent Method Called\n(e.g. analyze_problem)", shape="box3d"];
        context[label="Context Collection\nMetrics, Stats, Region Data\nInjected as prompt variables", shape="box3d"];
        prompt[label="Prompt Assembly\nSystem Prompt + User Message\n+ 'Think step by step' (if not JSON)", shape="box3d"];
        json_check [label="JSON Target?\n(Return ONLY valid JSON\nin user_message?)", shape="diamond"];
    }

    subgraph cluster_llm_flow {
        label="LLMClient";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899"; fontsize="12";
        fontname="Arial Bold";

        cache_check [label="MD5 Cache Hit?\nmodel|system|message", shape="diamond"};
        circuit_check [label="Circuit Breaker\nOpen?", shape="diamond"};
        api_call[label="API Call\nOpenAI-compatible\nchat() method", shape="box3d"];
        model_chain[label="Model Attempt\n1. Primary model\n2-5. Fallback chain", shape="box3d"];
    }

    subgraph cluster_response {
        label="Response Processing";
        style="filled"; fillcolor="#fff7ed"; color="#f97316"; fontsize="12";
        fontname="Arial Bold";

        evaluator_check [label="skip_evaluator?", shape="diamond"};
        score[label="LLMEvaluator Score\nStructure 40%\nCompleteness 30%\nRelevance 30%", shape="box3d"];
        threshold_check [label="Score >= 0.5?", shape="diamond"};
        fallback_label[label="Hardcoded Fallback\n'Strategy: C\nReason 1: ...'", shape="box3d"];
        downstream_val[label="Downstream Validator\nWeight / Archetype / Policy", shape="box3d"];
        acceptance{label="Valid?", shape="diamond"};
        final[label="Accepted Output\nUsed by Optimizer", shape="box3d"];
    }

    # Flow
    request -> context;
    context -> prompt;
    prompt -> json_check;
    json_check -> cache_check [label="No"];
    json_check -> cache_check [label="Yes", style="dashed"];

    cache_check -> circuit_check [label="Miss"];
    cache_check -> final [label="Hit (cached response)"];

    circuit_check -> api_call [label="Closed"];
    circuit_check -> fallback_label [label="Open (60s cooldown)"];

    api_call -> model_chain;
    model_chain -> evaluator_check;

    evaluator_check -> score [label="False"];
    evaluator_check -> downstream_val [label="True"];

    score -> threshold_check;
    threshold_check -> final [label="Yes"];
    threshold_check -> fallback_label [label="No"];

    fallback_label -> final;
    downstream_val -> acceptance;
    acceptance -> final [label="Yes"];
    acceptance -> fallback_label [label="No"];

    # Retry loop
    model_chain -> api_call [style="dashed", label="retry\nif failed", color="#ec4899"];
"""

# ── Diagram 4: AI + Optimization Interaction ──
def d4_ai_optimization():
    return """
    label="AI-Optimizer Interaction: How LLM Outputs Influence the Optimization Pipeline";
    fontsize="16"; fontname="Arial Bold";

    subgraph cluster_ai_outputs {
        label="AI Generated Outputs";
        style="filled"; fillcolor="#f5f3ff"; color="#8b5cf6"; fontsize="12";
        fontname="Arial Bold";

        strategy[label="Regional Strategy\nType A/B/C\nDrives service filter", shape="box3d"];
        archetype[label="Archetype Params\ndirect: 0.60\nhub_loop: 0.15\nfeeder: 0.20\ntrunk: 0.05", shape="box3d"];
        weights[label="Decision Weights\nprofit: 0.4244\ncoverage: 0.4656\ncost: 0.11", shape="box3d"];
        hub_strat[label="Hub Strategy\nPort selection\nfrom demand analysis", shape="box3d"];
    }

    subgraph cluster_optimizer {
        label="Optimization Pipeline";
        style="filled"; fillcolor="#e0f2fe"; color="#0284c7"; fontsize="12";
        fontname="Arial Bold";

        cand_gen[label="Candidate Service\nGeneration\n800-2000 candidates\nGuided by archetype params", shape="box3d"];
        filter[label="Profitability Gate\nRevenue - Cost > 0\nStrategic filter disabled", shape="box3d"];
        svc_ga[label="ServiceGA\nBinary chromosome\nFitness: w_p*profit + w_c*cov - w_k*cost\nWeights from AI decisions", shape="box3d"];
        freq_ga[label="FrequencyGA\nInteger frequencies\nMax 300 vessels\nInformed by strategy type", shape="box3d"];
        milp[label="HubMILP\nPuLP/CBC solver\nFlow optimization\nTime limit: 120s", shape="box3d"];
        results[label="Regional Results\nServices, Metrics\nPolicy, Explanation", shape="box3d"];
    }

    subgraph cluster_validation {
        label="AI Validation";
        style="filled"; fillcolor="#fff7ed"; color="#f97316"; fontsize="12";
        fontname="Arial Bold";

        weight_val[label="WeightValidator\nClamp [0,1]\nNormalize to sum=1", shape="box3d"];
        consensus[label="ConsensusEngine\nCoord 0.4 + Reg 0.4 + Svc 0.2\nConfidence score", shape="box3d"];
        policy_val[label="PolicyValidator V2\nAnti-neutral check\nMetric citation\nVessel sanity\nDrift detection", shape="box3d"];
    }

    # AI -> Optimizer flow
    archetype -> cand_gen [label="Service mix ratios"];
    strategy -> filter [label="Aggressive (A)\nBalanced (B)\nConservative (C)"];
    weights -> svc_ga [label="Fitness weights"];
    strategy -> freq_ga [style="dashed", label="Demand\ndispersion"];
    hub_strat -> milp [label="Hub selection"];

    # Optimizer flow
    cand_gen -> filter;
    filter -> svc_ga;
    svc_ga -> freq_ga;
    freq_ga -> milp;
    milp -> results;

    # Validation flow
    weights -> weight_val;
    strategy -> policy_val;
    weight_val -> consensus;
    policy_val -> consensus;
    consensus -> svc_ga [label="Adjusted\nweights"];
"""

# ── Diagram 5: Validation Pipeline ──
def d5_validation():
    return """
    label="AI Output Validation Pipeline: Multi-Layer Verification with Confidence Scoring";
    fontsize="16"; fontname="Arial Bold";

    subgraph cluster_inputs {
        label="AI Outputs to Validate";
        style="filled"; fillcolor="#f5f3ff"; color="#8b5cf6";

        coord_output[label="Coordinator Decision\nprofit: 0.60\ncoverage: 0.25\ncost: 0.15", shape="box3d"];
        reg_output[label="Regional Strategy\nType: Balanced\nCoverage priority: 0.6", shape="box3d"];
        svc_output[label="SvcGen Archetype\ndirect: 0.60\nhub_loop: 0.15\nfeeder: 0.20", shape="box3d"];
    }

    subgraph cluster_pass1 {
        label="Pass 1: Weight Validation";
        style="filled"; fillcolor="#fff7ed"; color="#f97316";

        weight_clamp[label="Clamp to [0, 1]\nProfit, Coverage, Cost", shape="box3d"];
        weight_normalize[label="Normalize\nSum to 1.0", shape="box3d"];
        weight_tags[label="AI_GENERATED?\nAI_VALIDATED / AI_REJECTED", shape="box3d"];
        weight_clamp -> weight_normalize -> weight_tags;
    }

    subgraph cluster_pass2 {
        label="Pass 2: Archetype Validation";
        style="filled"; fillcolor="#fff7ed"; color="#f97316";

        arch_check[label="Each ratio in [0.05, 0.90]\nSum to 1.0\nvessel_bias valid", shape="box3d"];
        arch_default[label="Default Fallback\ndirect: 0.60, hub_loop: 0.15\nfeeder: 0.20, trunk: 0.05", shape="box3d"];
        arch_check -> arch_default [style="dashed"];
    }

    subgraph cluster_pass3 {
        label="Pass 3: Policy Validation V2";
        style="filled"; fillcolor="#fff7ed"; color="#ea580c";

        anti_neutral[label="Anti-Neutrality\nPolicy must NOT be 0.5/0.5", shape="box3d"];
        metric_cite[label="Metric Citation\nEvery decision references\ncomputed metric", shape="box3d"];
        vessel_sanity[label="Vessel Sanity\nFleet <= 300 vessels", shape="box3d"];
        drift[label="Drift Detection\nChange <= 0.3 from\nprior iteration", shape="box3d"];
        anti_neutral -> metric_cite -> vessel_sanity -> drift;
    }

    subgraph cluster_consensus {
        label="ConsensusEngine";
        style="filled"; fillcolor="#fff7ed"; color="#ea580c";

        weight_vote[label="Weight Reconciliation\nCoord 0.4 + Reg 0.4 + Svc 0.2", shape="box3d"];
        arch_reconcile[label="Archetype Reconciliation\nMajority voting", shape="box3d"];
        hub_reconcile[label="Hub Reconciliation\nIntersection + union", shape="box3d"];
        confidence[label="Confidence Scoring\n>0.7: ACCEPTED\n0.3-0.7: MODIFIED\n<0.3: REJECTED", shape="box3d"];
        tags[label="CONSENSUS_ACCEPTED\nCONSENSUS_MODIFIED\nCONSENSUS_REJECTED", shape="box3d"];

        weight_vote -> confidence;
        arch_reconcile -> confidence;
        hub_reconcile -> confidence;
        confidence -> tags;
    }

    coord_output -> weight_clamp;
    reg_output -> anti_neutral;
    svc_output -> arch_check;
    weight_tags -> weight_vote;
    drift -> weight_vote;
    arch_check -> arch_reconcile;
"""

# ── Diagram 6: LLM Client Internals ──
def d6_llm_client():
    return """
    label="LLMClient Architecture: Caching, Fallback Chain, and Circuit Breaker";
    fontsize="16"; fontname="Arial Bold";

    subgraph cluster_client {
        label="LLMClient (src/llm/client.py)";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899";

        entry[label="chat(model, system,\nuser_message, temperature)", shape="box3d"];
        hash_key[label="Cache Key Generation\nMD5(model|system|message)", shape="box3d"];
        cache_check[label="Cache Lookup", shape="diamond"];
    }

    cache_storage[label="Response Cache\nDict[str, str]\nIn-memory", shape="cylinder"];

    subgraph cluster_fallback {
        label="Provider Fallback Chain";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899";

        primary[label="Attempt 1: opencode/deepseek-v4-flash-free\nTemp: 0.1-0.3, Max tokens: 4096", shape="box3d", fillcolor="#fbcfe8"];
        fallback1[label="Attempt 2: mimo-v2.5-free", shape="box3d"];
        fallback2[label="Attempt 3: nemotron-3-ultra-free", shape="box3d"];
        fallback3[label="Attempt 4: qwen3.6-plus-free (expired)", shape="box3d"];
        fallback4[label="Attempt 5: minimax-m3-free (expired)", shape="box3d"];
        primary -> fallback1 -> fallback2 -> fallback3 -> fallback4;
    }

    subgraph cluster_breaker {
        label="Circuit Breaker Pattern";
        style="filled"; fillcolor="#fce7f3"; color="#ec4899";

        normal[label="Closed (Normal)\nCounting consecutive failures", shape="box3d"];
        open_state[label="Open (Tripped)\n5 failures -> 60s timeout\nAll requests rejected immediately", shape="box3d"];
        half_open[label="Half-Open\nAfter 60s, allow 1 test\nSuccess -> close, Fail -> reopen", shape="box3d"];
        counter[label="Failure Counter\nResets on success", shape="box3d"];

        normal -> open_state [label="5 failures"];
        open_state -> half_open [label="60s elapsed"];
        half_open -> normal [label="1 success"];
        half_open -> open_state [label="1 failure"];
        counter -> open_state [style="dashed"];
    }

    subgraph cluster_request {
        label="Request Lifecycle";
        style="filled"; fillcolor="#fdf2f8"; color="#ec4899";

        format_req[label="Format Request\nOpenAI SDK format", shape="box3d"];
        send_req[label="POST /v1/chat/completions\nBase URL from LLM_BASE_URL", shape="box3d"];
        parse_resp[label="Parse Response\nExtract content text", shape="box3d"];
        strip[label="Strip whitespace\nReturn string", shape="box3d"];

        format_req -> send_req -> parse_resp -> strip;
    }

    entry -> hash_key;
    hash_key -> cache_check;
    cache_check -> cache_storage [label="Look up"];
    cache_check -> format_req [label="Miss"];
    send_req -> primary;
    strip -> cache_storage [style="dashed", label="Cache\nresponse"];
"""


def main():
    ensure_dirs()

    diagrams = [
        ("ai_01_overview", d1_overview()),
        ("ai_02_agents", d2_agents()),
        ("ai_03_prompt_flow", d3_prompt_flow()),
        ("ai_04_optimization_interaction", d4_ai_optimization()),
        ("ai_05_validation", d5_validation()),
        ("ai_06_llm_client", d6_llm_client()),
    ]

    print("=" * 60)
    print("AI Layer Diagram Generator")
    print("=" * 60)
    ok = 0
    for name, dot in diagrams:
        print(f"\n  [{name}]")
        if render(dot, name):
            ok += 1
    print(f"\nGenerated {ok}/{len(diagrams)} AI diagrams")
    return 0 if ok == len(diagrams) else 1

if __name__ == "__main__":
    sys.exit(main())
