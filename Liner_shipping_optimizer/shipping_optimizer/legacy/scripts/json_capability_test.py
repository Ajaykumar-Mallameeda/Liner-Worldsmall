#!/usr/bin/env python3
"""
Phase P+1D — JSON Capability Verification & AI Path Recovery
=============================================================
Isolated diagnostic tests to determine why JSON prompts fail at 100%.

Tests:
  D1 — Raw model JSON capability
  D2 — Coordinator prompt forensics
  D3 — Service generator prompt forensics
  D4 — Prompt constraint variants
  D5 — API response_format capability
  D6 — Client extraction audit

Usage:
  python scripts/json_capability_test.py

Output:
  Prints all results to stdout. Also saves raw_responses/ directory.
"""

import sys
import os
import json
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.makedirs("raw_responses", exist_ok=True)

from openai import OpenAI
from src.utils.config import Config
from src.utils.logger import logger
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent


# =========================================================================
# Setup
# =========================================================================

client = OpenAI(base_url=Config.LLM_BASE_URL, api_key=Config.LLM_API_KEY)
RESULTS = []


def save_raw(name: str, data: dict):
    """Save raw response data to file."""
    path = f"raw_responses/{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def inspect_message(message) -> dict:
    """Extract every interesting field from a ChatCompletionMessage."""
    fields = {
        "content": message.content if hasattr(message, "content") else "NO_CONTENT_ATTR",
        "content_type": type(message.content).__name__ if hasattr(message, "content") else "N/A",
        "content_len": len(message.content) if hasattr(message, "content") and message.content else 0,
        "reasoning_content": None,
        "reasoning_content_len": 0,
        "tool_calls": str(message.tool_calls) if hasattr(message, "tool_calls") and message.tool_calls else None,
        "role": message.role if hasattr(message, "role") else None,
        "refusal": str(message.refusal) if hasattr(message, "refusal") and message.refusal else None,
    }
    # Check reasoning_content (different models name it differently)
    for attr in ["reasoning_content", "reasoning", "reasoning_text", "thinking"]:
        if hasattr(message, attr):
            val = getattr(message, attr)
            if val:
                fields["reasoning_content"] = str(val)[:500]
                fields["reasoning_content_len"] = len(str(val))
                fields["reasoning_content_attr"] = attr
                break

    # Show all attributes
    all_attrs = [a for a in dir(message) if not a.startswith("_")]
    fields["available_attrs"] = all_attrs

    return fields


def call_model_direct(
    model: str,
    system: str,
    user_message: str,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    response_format=None,
) -> dict:
    """Direct API call, bypassing our client entirely."""
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": 30,
    }
    if response_format:
        kwargs["response_format"] = response_format

    t0 = time.time()
    try:
        response = client.chat.completions.create(**kwargs)
        elapsed = time.time() - t0
        message = response.choices[0].message
        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            "total_tokens": getattr(response.usage, "total_tokens", 0),
        }
        msg_inspected = inspect_message(message)

        return {
            "model": model,
            "system_len": len(system),
            "user_message_len": len(user_message),
            "latency_seconds": round(elapsed, 2),
            "response_format": str(response_format),
            "message": msg_inspected,
            "usage": usage,
            "had_response": True,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "model": model,
            "system_len": len(system),
            "user_message_len": len(user_message),
            "latency_seconds": round(elapsed, 2),
            "response_format": str(response_format),
            "had_response": False,
            "error": str(e)[:500],
            "message": None,
        }


def print_result(r: dict, label: str = ""):
    """Pretty-print a test result."""
    if label:
        print(f"\n{'='*70}")
        print(f"  {label}")
        print(f"{'='*70}")

    m = r.get("message", {}) or {}
    content = m.get("content", "N/A")
    reasoning = m.get("reasoning_content", "N/A")
    had_content = bool(content and content.strip())
    had_reasoning = bool(reasoning and m.get("reasoning_content_len", 0) > 0)

    print(f"  Model:          {r['model']}")
    print(f"  Latency:        {r['latency_seconds']}s")
    print(f"  Response format: {r['response_format']}")
    if r.get("error"):
        print(f"  ERROR:          {r['error']}")
        return
    print(f"  Content:         {repr(content[:200]) if content else 'EMPTY/None'}")
    print(f"  Content len:     {m.get('content_len', 0)}")
    print(f"  Has reasoning:   {'YES' if had_reasoning else 'NO'}")
    if had_reasoning:
        print(f"  Reasoning attr:  {m.get('reasoning_content_attr', '?')}")
        print(f"  Reasoning start: {reasoning[:300]}")
    print(f"  Usage:           {json.dumps(r.get('usage', {}))}")
    print(f"  Available attrs: {m.get('available_attrs', [])[:15]}...")

    # Check if content is valid JSON
    if had_content:
        try:
            parsed = json.loads(content)
            print(f"  VALID JSON:      YES -> {json.dumps(parsed)}")
        except json.JSONDecodeError:
            # Maybe there's JSON embedded?
            m2 = re.search(r"\{.*\}", content, re.DOTALL)
            if m2:
                try:
                    parsed = json.loads(m2.group())
                    print(f"  EMBEDDED JSON:   YES -> {json.dumps(parsed)}")
                except json.JSONDecodeError:
                    print(f"  VALID JSON:      NO (regex found braces but not valid)")
            else:
                print(f"  VALID JSON:      NO (no braces in content)")


# =========================================================================
# D1 — RAW MODEL CAPABILITY TEST
# =========================================================================

def run_d1():
    """Test each configured model with a trivial JSON prompt."""
    print(f"\n{'#'*70}")
    print(f"#  D1 — RAW MODEL JSON CAPABILITY TEST")
    print(f"{'#'*70}")

    models = [
        "deepseek-v4-flash-free",
        "qwen3.6-plus-free",
        "minimax-m3-free",
        "mimo-v2.5-free",
        "nemotron-3-ultra-free",
    ]

    simple_json_prompt = 'Return exactly:\n\n{\n"hello": "world"\n}'
    empty_system = "You are a helpful assistant."

    results = []
    for model in models:
        print(f"\n{'─'*70}")
        print(f"  Testing model: {model}")
        print(f"{'─'*70}")

        r = call_model_direct(
            model=model,
            system=empty_system,
            user_message=simple_json_prompt,
            temperature=0.1,
        )
        print_result(r, f"D1 — {model}: simple JSON")
        path = save_raw(f"d1_{model}", r)
        print(f"  Saved to: {path}")
        results.append(r)

        # Test with JSON-focused system prompt
        if model == models[0]:  # Only primary model gets extra tests
            json_system = "You are a JSON generator. Always output valid JSON."
            r2 = call_model_direct(
                model=model,
                system=json_system,
                user_message=simple_json_prompt,
                temperature=0.1,
            )
            print_result(r2, f"D1 — {model}: JSON system prompt")
            path = save_raw(f"d1_{model}_json_sys", r2)
            print(f"  Saved to: {path}")
            results.append(r2)

        # Check if reasoning_content contains JSON
        m = r.get("message", {})
        reasoning = m.get("reasoning_content", "")
        if reasoning:
            # Try to find JSON in reasoning
            json_match = re.search(r"\{.*\}", reasoning, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    print(f"  >>> Reasoning CONTAINS valid JSON: {json.dumps(parsed)}")
                except json.JSONDecodeError:
                    print(f"  >>> Reasoning contains braces but NOT valid JSON")

    return results


# =========================================================================
# D4 — PROMPT CONSTRAINT VARIANTS
# =========================================================================

def run_d4():
    """Test 4 prompt constraint variants for JSON success."""
    print(f"\n{'#'*70}")
    print(f"#  D4 — PROMPT CONSTRAINT VARIANT TESTS")
    print(f"{'#'*70}")

    model = "deepseek-v4-flash-free"
    system = "You are a shipping network optimization analyst."

    # The actual coordinator prompt content (simplified with real metrics)
    metric_context = (
        "Global shipping network decision — iteration results:\n\n"
        "Metrics:\n"
        "  Total profit   : $896,953,334/week\n"
        "  Annual profit  : $46,641,573,368\n"
        "  Avg coverage   : 66.0%\n"
        "  Min coverage   : 32.2%\n"
        "  Coverage variance: 51.4%\n"
        "  Total cost     : $1,982,113,428/week\n"
        "  Profit margin  : 31.1%\n"
        "  Evaluation     : moderate (score 3/5)\n\n"
        "Conflicts detected: 0\n"
        "Weak regions (coverage < 70%): Europe coverage=55.8%; Americas coverage=36.3%; Middle East coverage=80.0%; Africa coverage=83.7%\n\n"
    )

    variants = {
        "A — Current (ONLY JSON)": metric_context + (
            'Return ONLY valid JSON (no markdown, no preamble):\n'
            '{"actions": [{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}], '
            '"priorities": ["<priority 1>", "<priority 2>"], '
            '"weight_adjustments": {"profit_weight": <0.0-1.0>, "coverage_weight": <0.0-1.0>, "cost_weight": <0.0-1.0>}, '
            '"notes": "<one sentence with specific numbers>"}'
        ),
        "B — JSON, no explanations": metric_context + (
            'Return JSON.\n'
            'Do not include explanations.\n'
            '{"actions": [{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}], '
            '"priorities": ["<priority 1>", "<priority 2>"], '
            '"weight_adjustments": {"profit_weight": <0.0-1.0>, "coverage_weight": <0.0-1.0>, "cost_weight": <0.0-1.0>}, '
            '"notes": "<one sentence with specific numbers>"}'
        ),
        "C — Explain then JSON": metric_context + (
            'Explain your reasoning step by step, then provide the JSON.\n'
            '{"actions": [{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}], '
            '"priorities": ["<priority 1>", "<priority 2>"], '
            '"weight_adjustments": {"profit_weight": <0.0-1.0>, "coverage_weight": <0.0-1.0>, "cost_weight": <0.0-1.0>}, '
            '"notes": "<one sentence with specific numbers>"}'
        ),
        "D — Natural with JSON block": metric_context + (
            'Respond naturally. Include a JSON block with your recommendations.\n'
            'The JSON should have: actions, priorities, weight_adjustments, notes.'
        ),
    }

    results = {}
    for label, prompt in variants.items():
        print(f"\n{'─'*70}")
        print(f"  Variant: {label}")
        print(f"{'─'*70}")

        r = call_model_direct(
            model=model,
            system=system,
            user_message=prompt,
            temperature=0.1,
        )
        print_result(r, f"D4 — {label}")

        path = save_raw(f"d4_{label.replace(' — ','_').replace(' ','_')}", r)
        print(f"  Saved to: {path}")
        results[label] = r

    return results


# =========================================================================
# D5 — API RESPONSE_FORMAT CAPABILITY
# =========================================================================

def run_d5():
    """Test if API supports response_format={'type':'json_object'}."""
    print(f"\n{'#'*70}")
    print(f"#  D5 — API RESPONSE_FORMAT CAPABILITY TEST")
    print(f"{'#'*70}")

    model = "deepseek-v4-flash-free"
    system = "You are a JSON generator. Always output valid JSON."
    prompt = 'Generate this JSON: {"hello": "world", "name": "test", "value": 42}'

    # Test 1: response_format=json_object
    print(f"\n{'─'*70}")
    print(f"  Test 1: response_format={{'type':'json_object'}}")
    print(f"{'─'*70}")
    r1 = call_model_direct(
        model=model,
        system=system,
        user_message=prompt,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    print_result(r1, "D5 — response_format=json_object")
    save_raw("d5_response_format_json_object", r1)

    # Test 2: Without response_format (control)
    print(f"\n{'─'*70}")
    print(f"  Test 2: No response_format (control)")
    print(f"{'─'*70}")
    r2 = call_model_direct(
        model=model,
        system=system,
        user_message=prompt,
        temperature=0.1,
    )
    print_result(r2, "D5 — no response_format")
    save_raw("d5_no_response_format", r2)

    return {"json_object": r1, "control": r2}


# =========================================================================
# D6 — CLIENT EXTRACTION AUDIT
# =========================================================================

def run_d6():
    """Verify _extract_response_content() against actual responses."""
    print(f"\n{'#'*70}")
    print(f"#  D6 — CLIENT EXTRACTION AUDIT")
    print(f"{'#'*70}")

    from src.llm.client import LLMClient
    lc = LLMClient()

    model = "deepseek-v4-flash-free"
    system = "You are a helpful assistant."

    # Test extraction on 3 types of prompts
    test_prompts = [
        ("Free-text (simple)", "Say hello in one sentence."),
        ("JSON (simple)", 'Return exactly:\n{"test": "value", "number": 42}'),
        ("JSON (strict)", 'Return ONLY valid JSON (no markdown, no preamble):\n{"profit_weight": 0.5, "coverage_weight": 0.4, "cost_weight": 0.1}'),
    ]

    results = {}
    for label, prompt in test_prompts:
        print(f"\n{'─'*70}")
        print(f"  Prompt: {label}")
        print(f"{'─'*70}")

        # Raw API call
        r = call_model_direct(
            model=model,
            system=system,
            user_message=prompt,
            temperature=0.1,
        )
        print(f"\n  Raw API response:")
        print_result(r, f"D6 — {label}")

        # Now test extraction
        m = r.get("message", {})
        resp = r  # We'll create a mock response object

        # Actually call the real extraction
        if r.get("had_response") and not r.get("error"):
            # Recreate the response for extraction testing
            raw = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
                timeout=30,
            )
            extracted = lc._extract_response_content(raw)
            msg = raw.choices[0].message

            print(f"\n  Real extraction result:")
            print(f"    Content attr present: {hasattr(msg, 'content')}")
            print(f"    Content value:        {repr(msg.content)[:200]}")
            print(f"    Content is not None:  {msg.content is not None}")
            print(f"    Reasoning present:    {hasattr(msg, 'reasoning_content') and bool(msg.reasoning_content)}")
            print(f"    Extracted result:     {repr(extracted)[:200]}")
            print(f"    Extracted is None:    {extracted is None}")
            print(f"    Extracted is JSON:    {bool(extracted and json.loads(extracted)) if extracted and extracted.strip() else 'N/A'}")

            # Save extraction trace
            save_raw(f"d6_extraction_{label.replace(' ','_').replace('(','').replace(')','')}", {
                "prompt_type": label,
                "prompt": prompt,
                "has_content_attr": hasattr(msg, "content"),
                "content_value": msg.content,
                "content_is_not_none": msg.content is not None,
                "has_reasoning": hasattr(msg, "reasoning_content") and bool(msg.reasoning_content),
                "reasoning_preview": str(getattr(msg, "reasoning_content", ""))[:300] if hasattr(msg, "reasoning_content") else None,
                "extracted_result": extracted,
                "extracted_is_none": extracted is None,
            })

        results[label] = r

    return results


# =========================================================================
# D2 — COORDINATOR PROMPT FORENSICS
# =========================================================================

def run_d2():
    """Capture the exact coordinator prompt and trace it through the pipeline."""
    print(f"\n{'#'*70}")
    print(f"#  D2 — COORDINATOR PROMPT FORENSICS")
    print(f"{'#'*70}")

    from src.llm.client import llm_client

    # Build a coordinator agent and construct its prompt
    coord = CoordinatorAgent()

    # Use the latest pipeline data if available
    try:
        with open("pipeline_output.json") as f:
            prev = json.load(f)
        rr = prev.get("regional_results", [])
    except:
        rr = []

    # Create realistic test input data
    if rr:
        test_regional = rr
    else:
        # Fallback: create synthetic data
        test_regional = [
            {"region": "Asia", "coverage_percent": 74.1, "weekly_profit": 48010846},
            {"region": "Europe", "coverage_percent": 55.8, "weekly_profit": 35000000},
            {"region": "Americas", "coverage_percent": 36.3, "weekly_profit": 42000000},
        ]

    # Replicate _generate_decisions prompt construction
    COVERAGE_TARGET = 70.0
    weak_regions = [s for s in test_regional if s.get("coverage_percent", 0) < COVERAGE_TARGET]
    weak_summary = "; ".join(
        f"{s['region']} coverage={s.get('coverage_percent', 0):.1f}%"
        for s in weak_regions
    )

    metrics = {
        "total_profit": sum(s.get("weekly_profit", 0) for s in test_regional),
        "annual_profit": sum(s.get("weekly_profit", 0) for s in test_regional) * 52,
        "average_coverage": sum(s.get("coverage_percent", 0) for s in test_regional) / len(test_regional),
        "min_coverage": min(s.get("coverage_percent", 0) for s in test_regional),
        "coverage_variance": max(s.get("coverage_percent", 0) for s in test_regional) - min(s.get("coverage_percent", 0) for s in test_regional),
        "total_cost": sum(s.get("operating_cost", 0) for s in test_regional),
        "profit_margin_pct": 31.1,
    }

    evaluation = {"status": "moderate", "score": 3, "max": 5}
    conflicts = []

    prompt = f"""
Global shipping network decision — iteration results:

Metrics:
  Total profit   : ${metrics['total_profit']:,.0f}/week
  Annual profit  : ${metrics['annual_profit']:,.0f}
  Avg coverage   : {metrics['average_coverage']:.1f}%
  Min coverage   : {metrics['min_coverage']:.1f}%
  Coverage variance: {metrics['coverage_variance']:.1f}%
  Total cost     : ${metrics['total_cost']:,.0f}/week
  Profit margin  : {metrics['profit_margin_pct']:.1f}%
  Evaluation     : {evaluation['status']} (score {evaluation['score']}/{evaluation['max']})

Conflicts detected: {len(conflicts)}
Weak regions (coverage < {COVERAGE_TARGET}%): {weak_summary or 'none'}

Return ONLY valid JSON (no markdown, no preamble):
{{
  "actions": [
    {{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}}
  ],
  "priorities": ["<priority 1>", "<priority 2>"],
  "weight_adjustments": {{
    "profit_weight":   <0.0-1.0>,
    "coverage_weight": <0.0-1.0>,
    "cost_weight":     <0.0-1.0>
  }},
  "notes": "<one sentence with specific numbers>"
}}
"""

    print(f"\n  PROMPT LENGTH: {len(prompt)} chars")
    print(f"  PROMPT PREVIEW:")
    for line in prompt.strip().split("\n")[:10]:
        print(f"    {line}")
    print("    ...")

    # Now trace through the actual pipeline
    print(f"\n  {'─'*70}")
    print(f"  TRACING THROUGH LLM CHAIN")
    print(f"  {'─'*70}")

    # Step 1: LLM call
    enhanced = prompt + "\n\nThink step by step. Follow the output format strictly."
    system = coord.get_system_prompt()

    print(f"\n  Step 1: LLM call to {coord.model}")
    print(f"  System prompt ({len(system)} chars): {system[:100]}...")
    print(f"  Enhanced user message ({len(enhanced)} chars)")

    t0 = time.time()
    raw_response = llm_client.chat(
        model=coord.model,
        system=system,
        user_message=enhanced,
        temperature=0.1,
    )
    elapsed = time.time() - t0

    print(f"\n  Step 2: Raw response received ({elapsed:.1f}s)")
    print(f"  Response length: {len(raw_response)} chars")
    print(f"  Response preview: {raw_response[:300]}")

    # Step 3: JSON parse
    decisions = coord._parse_json_safe(raw_response)
    print(f"\n  Step 3: _parse_json_safe() result")
    print(f"  Decisions is empty: {not decisions}")
    print(f"  Decisions keys: {list(decisions.keys()) if decisions else 'N/A (empty)'}")

    # Step 4: Validate
    has_weights = decisions and "weight_adjustments" in decisions
    print(f"\n  Step 4: Validator check")
    print(f"  decisions is not None: {decisions is not None}")
    print(f"  'weight_adjustments' in decisions: {has_weights}")
    if has_weights:
        print(f"  Weights: {decisions['weight_adjustments']}")

    # Step 5: Fallback check
    needs_fallback = not decisions or "actions" not in decisions
    print(f"\n  Step 5: Fallback check")
    print(f"  needs_fallback: {needs_fallback}")
    if needs_fallback:
        print(f"  -> FALLBACK ACTIVATED (would use rule-based)")

    # Save full trace
    path = save_raw("d2_coordinator_forensics", {
        "prompt": prompt,
        "enhanced_prompt": enhanced,
        "system_prompt": system,
        "raw_response": raw_response,
        "decisions": decisions if decisions else {"empty": True},
        "has_weight_adjustments": has_weights,
        "needs_fallback": needs_fallback,
        "response_length": len(raw_response),
        "latency": elapsed,
    })
    print(f"\n  Full trace saved: {path}")

    return prompt, raw_response, decisions


# =========================================================================
# D3 — SERVICE GENERATOR PROMPT FORENSICS
# =========================================================================

def run_d3():
    """Capture the service generator prompt and trace it."""
    print(f"\n{'#'*70}")
    print(f"#  D3 — SERVICE GENERATOR PROMPT FORENSICS")
    print(f"{'#'*70}")

    from src.llm.client import llm_client

    model = "deepseek-v4-flash-free"

    # Simplified network context (realistic)
    prompt_context = (
        "Liner shipping service design for 333-port network.\n\n"
        "NETWORK STATS:\n"
        "  Ports: 333, Lanes: 9622, Median demand/lane: 60.0 TEU\n"
        "  Total demand: 1,666,738 TEU, Avg: 173.2 TEU/lane\n"
        "  Top-3 share: 2.5%, Top-500 share: 51.3%\n"
        "  Hub ports: [USLAX, USEWR, USILM, USCHS, USHOU] (50 detected)\n\n"
        "TOP-5 CORRIDORS:\n"
        "  1. Port CNYTN -> Port USLAX: 21,804 TEU/wk\n"
        "  2. Port CNSHA -> Port DEBRV: 10,584 TEU/wk\n"
        "  3. Port CNSHA -> Port USLAX: 9,135 TEU/wk\n"
        "  4. Port CNYTN -> Port GBFXT: 8,100 TEU/wk\n"
        "  5. Port CNYTN -> Port NLRTM: 8,088 TEU/wk\n\n"
        "ARCHETYPE: HYBRID\n"
        "RATIONALE: Median demand is only 60.0 TEU/lane across 9622 lanes — "
        "consolidation via hubs is essential. Top-500 corridors (51.3% of demand) "
        "served direct; remaining 9122 low-demand corridors served via hub transshipment.\n\n"
        "In 2 sentences: (1) confirm archetype citing median demand 60.0 TEU "
        "and total 1,666,738 TEU; "
        "(2) expected GA retention out of ~800 candidates."
    )

    # The actual JSON archetype prompt
    json_prompt = prompt_context + (
        "\n\nReturn ONLY valid JSON (no markdown, no preamble):\n"
        '{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
        '"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
        '"vessel_bias": "small"|"balanced"|"large", '
        '"hub_focus": ["PORT_ID", ...], '
        '"notes": "<brief rationale>"}'
    )

    system = "You are a liner shipping service design specialist.\n\nAdvise on service archetypes for a given port network. Ground every recommendation in the network statistics provided. Every statement must cite a specific number. Do not use vague language. Do not repeat the question."

    print(f"\n  JSON PROMPT LENGTH: {len(json_prompt)} chars")
    print(f"  JSON PROMPT (last 300 chars): {json_prompt[-300:]}")

    # Step 1: LLM call
    enhanced = json_prompt + "\n\nThink step by step. Follow the output format strictly."
    print(f"\n  Step 1: LLM call to {model}")

    t0 = time.time()
    raw_json = llm_client.chat(
        model=model,
        system=system,
        user_message=enhanced,
        temperature=0.1,
    )
    elapsed = time.time() - t0

    print(f"\n  Step 2: Raw response ({elapsed:.1f}s)")
    print(f"  Response length: {len(raw_json)} chars")
    print(f"  Response preview: {raw_json[:400]}")

    # Step 3: JSON extraction
    import json as _json
    import re as _re
    text = raw_json.strip()
    text = _re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = _re.sub(r"\n?```$", "", text)
    print(f"\n  Step 3: JSON extraction")
    print(f"  After fence removal ({len(text)} chars)")

    try:
        parsed = _json.loads(text.strip())
        parse_ok = True
        print(f"  json.loads(): SUCCESS -> {json.dumps(parsed)[:200]}")
    except _json.JSONDecodeError:
        parse_ok = False
        print(f"  json.loads(): FAILED (JSONDecodeError)")
        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        if m:
            try:
                parsed = _json.loads(m.group())
                parse_ok = True
                print(f"  regex extraction: SUCCESS -> {json.dumps(parsed)[:200]}")
            except _json.JSONDecodeError:
                parsed = {}
                print(f"  regex extraction: FAILED (found braces but invalid JSON)")
        else:
            parsed = {}
            print(f"  regex extraction: FAILED (no braces found in response)")

    print(f"\n  Step 4: Validation")
    from src.validation.archetype_validator import validate_archetype_params
    archetype_params = validate_archetype_params(parsed)
    is_default = (
        archetype_params.get("archetype_mix", {}).get("direct_ratio") == 0.60
    )
    print(f"  Archetype params: {json.dumps(archetype_params)[:200]}")
    print(f"  Is default: {is_default}")
    print(f"  -> FALLBACK {'ACTIVATED' if is_default else 'NOT NEEDED'}")

    path = save_raw("d3_servicegen_forensics", {
        "prompt": json_prompt,
        "enhanced_prompt": enhanced,
        "system": system,
        "raw_json": raw_json,
        "after_fence_removal": text,
        "parse_succeeded": parse_ok,
        "parsed": parsed if parsed else {"empty": True},
        "archetype_params": archetype_params,
        "is_default": is_default,
        "response_length": len(raw_json),
        "latency": elapsed,
    })
    print(f"\n  Full trace saved: {path}")

    return prompt_context, raw_json, parsed


# =========================================================================
# MAIN
# =========================================================================

if __name__ == "__main__":
    print(f"{'='*70}")
    print(f"  PHASE P+1D — JSON CAPABILITY VERIFICATION")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  API: {Config.LLM_BASE_URL}")
    print(f"  Primary model: {Config.ORCHESTRATOR_MODEL}")
    print(f"{'='*70}")

    all_results = {}

    # D1 — Model capability
    all_results["d1"] = run_d1()

    # D2 — Coordinator forensics
    all_results["d2"] = run_d2()

    # D3 — Service generator forensics
    all_results["d3"] = run_d3()

    # D4 — Prompt variants
    all_results["d4"] = run_d4()

    # D5 — API audit
    all_results["d5"] = run_d5()

    # D6 — Client extraction audit
    all_results["d6"] = run_d6()

    # Save all results
    master = save_raw("d_master_all_results", {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "api_url": Config.LLM_BASE_URL,
        "primary_model": Config.ORCHESTRATOR_MODEL,
        "results": all_results,
    })
    print(f"\n{'='*70}")
    print(f"  ALL RESULTS SAVED: {master}")
    print(f"{'='*70}")
