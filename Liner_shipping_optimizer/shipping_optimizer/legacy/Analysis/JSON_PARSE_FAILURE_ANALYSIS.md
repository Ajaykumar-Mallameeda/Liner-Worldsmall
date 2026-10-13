# JSON Parse Failure Analysis

## Pipeline-Wide Analysis of Every JSON Parse Attempt, Failure Modes, and Root Causes

---

### 1. Parse Points in the Pipeline

Two independent JSON parse sites exist in the agent pipeline. Both share the same structural assumptions and therefore the same failure modes.

#### 1.1 Coordinator Agent — `_parse_json_safe()` (coordinator_agent.py:518-537)

```python
@staticmethod
def _parse_json_safe(raw: str) -> Dict:
    if not raw:
        return {}
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)   # strip ```json / ``` fence open
    text = re.sub(r"\n?```$", "", text)             # strip ``` fence close
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}
```

#### 1.2 Service Generator Agent — inline extraction (service_generator_agent.py:327-336)

```python
raw_json = self.call_llm(json_prompt, temperature=0.1)
import json as _json
import re as _re
text = raw_json.strip()
text = _re.sub(r"^```[a-zA-Z]*\n?", "", text)
text = _re.sub(r"\n?```$", "", text)
try:
    parsed = _json.loads(text.strip())
except _json.JSONDecodeError:
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    parsed = _json.loads(m.group()) if m else {}
```

The logic is identical: strip fences, try direct parse, fall back to regex `{...}` extraction, and if all else fails return `{}`.

---

### 2. What the Parsers Receive

The input string originates from `client.py:162-169`:

```python
if hasattr(message, "content") and message.content:
    result = message.content
elif hasattr(message, "tool_calls") and message.tool_calls:
    result = str(message.tool_calls)
else:
    result = str(message)
```

**The triggering condition:** `message.content` is `''` (empty string). Python evaluates `''` as falsy, so `message.content` is skipped. Since there are no `tool_calls` either, execution falls to the `else` branch.

**Line 169** — `result = str(message)` — serializes the entire `ChatCompletionMessage` object. The input to the JSON parsers therefore looks like:

```
ChatCompletionMessage(
    content='',
    refusal=None,
    role='assistant',
    function_call=None,
    tool_calls=None,
    reasoning_content='Thinking. 1. **Analyze the Request...'
)
```

This is a `repr()` output, not JSON. It is a Python object string literal that happens to resemble JSON in surface form only.

---

### 3. Why `json.loads()` Fails

The `ChatCompletionMessage` string fails on every JSON requirement:

| Requirement | Violation | Example in Input |
|---|---|---|
| Double-quoted strings | Single quotes | `content=''`, `role='assistant'` |
| No trailing commas | Not applicable (fails before reaching this) | — |
| No bare unquoted text | Raw text without quotes | `Thinking. 1. **Analyze...` inside `reasoning_content=` |
| No embedded newlines | `reasoning_content` may span multiple lines | `\n` breaks parser |
| Key-value delimiter `:` | Uses `=` assignment syntax | `content=''`, `refusal=None` |

The `json.JSONDecodeError` is raised immediately. No amount of fence-stripping can recover valid JSON from this input because the input was never JSON to begin with.

---

### 4. Why the Regex Fallback Fails

```python
m = re.search(r"\{.*\}", text, re.DOTALL)
```

The regex searches for the first `{` through the last `}` with `re.DOTALL` (`.` matches newlines).

**Coordinator case:** The serialized `ChatCompletionMessage` object does contain curly braces from nested dictionary representations (e.g., `function_call=None`, which internally is `None`, not a dict — but `reasoning_content` can contain `{`/`}` characters from chain-of-thought formatting). The extracted substring is NOT a valid JSON object matching the expected schema. For example, extracting `{'key': 'value'}` yields a Python-dict-looking string with single quotes. `json.loads()` rejects this.

**Service generator case:** Same outcome. Even if a `{...}` block is found, it is either a Python repr dict (single quotes) or an LLM reasoning fragment, not the expected archetype schema.

Both sites raise `json.JSONDecodeError` on the extraction attempt, and the function returns `{}`.

---

### 5. The Hard Fallback Path (client.py:177-179)

Before the parser ever sees the input, `client.py` has its own fallback:

```python
if not result or result.lower() == "none":
    logger.warning("empty_llm_response")
    result = self._get_hard_fallback_response()
```

`_get_hard_fallback_response()` returns:

```python
"Service temporarily unavailable. Using default optimization parameters."
```

This is a plain-English sentence. It contains **no JSON structure at all** (`{` is absent). Both parsers will:
1. Strip fences (no-op — no fences present)
2. `json.loads()` fails
3. Regex search for `{...}` fails (no `{` present)
4. Return `{}`

---

### 6. What Valid JSON Looks Like

The parsers are designed around these expected schemas:

**Coordinator decisions:**
```json
{
    "actions": [
        {"region": "Asia", "action": "increase coverage_weight in GA", "expected_gain": "+1.1% coverage"}
    ],
    "priorities": ["Raise coverage to 70%"],
    "weight_adjustments": {"profit_weight": 0.45, "coverage_weight": 0.45, "cost_weight": 0.1},
    "notes": "..."
}
```

**Service generator archetype:**
```json
{
    "direct_ratio": 0.60,
    "hub_loop_ratio": 0.15,
    "feeder_ratio": 0.20,
    "trunk_ratio": 0.05,
    "vessel_bias": "balanced",
    "hub_focus": [],
    "notes": ""
}
```

Neither schema resembles a Python `repr()` string. The delta between what the parser expects and what it receives is total.

---

### 7. Failure Mode Summary Table

| Parse Point | Input Type | `json.loads()` | Regex `{...}` Extraction | Final Result |
|---|---|---|---|---|
| Coordinator decisions (`_parse_json_safe`) | `repr(ChatCompletionMessage)` with empty `content=''` | FAILED — single quotes, `=` syntax, bare text | FAILED — extracted block is Python repr, not valid JSON | `{}` (empty dict) |
| Coordinator decisions (after hard fallback) | `"Service temporarily unavailable..."` | FAILED — plain text, no JSON structure | FAILED — no `{` present in string | `{}` (empty dict) |
| ServiceGen archetype (inline parse) | `repr(ChatCompletionMessage)` with empty `content=''` | FAILED — same structural violations | FAILED — same root cause | `{}` or invalid → defaults |
| ServiceGen archetype (after hard fallback) | `"Service temporarily unavailable..."` | FAILED — plain text | FAILED — no `{` present | `{}` → defaults applied |

Downstream effects: ServiceGen has an `except Exception` wrapper (line 339) that catches the `AttributeError` from `_json.loads(m.group())` when `m is None` and falls back to `DEFAULT_ARCHETYPE_PARAMS`. Coordinator has no such outer wrapper — `_parse_json_safe` silently returns `{}` and the caller must handle missing keys.

---

### 8. Root Cause

The root cause is a **type mismatch** at the LLM client boundary (`client.py:162-169`):

1. The LLM returns a response where `message.content` is `''` (empty string).
2. Python's truthiness check (`message.content`) rejects `''` as falsy.
3. No `tool_calls` branch activates either.
4. The `else` branch on line 169 converts the whole message object to a string.
5. This string is never JSON and never will be.
6. Both downstream parsers assume their input IS a JSON response that merely needs cleansing (fence stripping, regex extraction). They do not validate the fundamental nature of the input before attempting to parse.

The chain is: **empty LLM response** → **repr fallback** → **non-JSON string** → **parsers try anyway** → **silent `{}`**.

---

### 9. Downstream Impact

**Coordinator agent** — `_parse_json_safe` returns `{}`. Downstream consumers receive an empty dict instead of the expected schema keys (`actions`, `priorities`, `weight_adjustments`, `notes`). If callers use `.get("actions", [])` this is survivable (empty action list, no strategic decisions made). If callers access keys directly (`result["actions"]`), a `KeyError` is raised.

**Service generator agent** — the inline parse returns `{}`. The `except Exception` wrapper on line 339 catches this and substitutes `DEFAULT_ARCHETYPE_PARAMS`. This is survivable but the archetype generation is entirely bypassed — the system silently uses defaults with no indication that the LLM call failed at the JSON level rather than at the LLM level.

---

### 10. Recommended Fix

Before attempting JSON parsing, both sites should perform a pre-check for JSON-like structure. If the input contains no `{` character, the parser should short-circuit immediately — no regex extraction, no `json.loads()` attempt — and return `{}` with an appropriate log tag.

```python
# Early exit guard: input must contain JSON object structure
if "{" not in text:
    logger.warning("ai_rejected", tag="AI_REJECTED",
                   reason="Response contains no JSON structure")
    return {}
```

This would:
- Eliminate the cost of running `json.loads()` and the regex engine on inputs that can never be JSON.
- Produce a clear `AI_REJECTED` log event that distinguishes "LLM returned non-JSON text" from "LLM returned valid JSON that failed validation."
- Not change the final return value (`{}`) — the behavior is identical, only the path and observability improve.

A secondary improvement: in `client.py:162-169`, replace the truthiness check with an explicit empty-string check and log an `AI_REJECTED` event at the earliest point:

```python
if hasattr(message, "content") and isinstance(message.content, str) and len(message.content) > 0:
    result = message.content
else:
    logger.warning("ai_rejected", tag="AI_REJECTED",
                   reason=f"Empty content (type={type(message.content).__name__})")
    result = self._get_hard_fallback_response()
```

This catches the empty response at the source and routes directly to the hard fallback, preventing the poisoned `repr()` string from entering the pipeline at all.
