"""Deep trace of LLMClient.chat() - simpler approach."""

import sys, json, time
sys.path.insert(0, ".")

# Monkey-patch at source level before import
import src.llm.client as client_mod

original_chat = client_mod.LLMClient.chat

def traced_chat(self, model, system, user_message, temperature=0.2, max_tokens=2000):
    print(f"\n  [chat] entry: model={model}, sys_len={len(system)}, msg_len={len(user_message)}")

    # Strip model
    stripped = self._strip_model(model)
    candidates = [stripped] + [m for m in self.fallback_models if m != stripped]
    print(f"  [chat] candidates: {candidates[:3]}...")

    result = ""
    for idx, candidate in enumerate(candidates):
        print(f"  [chat] candidate[{idx}]: {candidate}")
        try:
            t0 = time.time()
            response = self._try_call(candidate, system, user_message, temperature, max_tokens)
            print(f"  [chat] _try_call returned in {time.time()-t0:.1f}s")
            if response and response.choices:
                msg = response.choices[0].message
                print(f"  [chat] msg.content type: {type(msg.content).__name__}")
                print(f"  [chat] msg.content is not None: {msg.content is not None}")
                print(f"  [chat] msg.content repr: {repr(msg.content)[:200]}")

                # Check reasoning
                for attr in ["reasoning_content", "reasoning", "thinking"]:
                    if hasattr(msg, attr) and getattr(msg, attr):
                        rc = str(getattr(msg, attr))
                        print(f"  [chat] Has {attr}: YES ({len(rc)} chars)")
                        break
                else:
                    print(f"  [chat] Has reasoning: NO")
            else:
                print(f"  [chat] response or choices is None/empty")

            # Extract
            t0 = time.time()
            content = self._extract_response_content(response)
            print(f"  [chat] _extract_response_content: {time.time()-t0:.4f}s")
            print(f"  [chat] extracted type: {type(content).__name__}")
            print(f"  [chat] extracted is None: {content is None}")
            print(f"  [chat] extracted repr: {repr(content)[:200] if content else 'NONE'}")

            if content is not None:
                result = content
                if idx > 0:
                    self.fallback_uses += 1
                    print(f"  [chat] USING FALLBACK MODEL: {candidate}")
                self.failure_count = 0
                print(f"  [chat] ACCEPTED candidate[{idx}]: {candidate}")
                break
            else:
                print(f"  [chat] REJECTED candidate[{idx}] - content is None")
                raise ValueError("reasoning_only_response")

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            print(f"  [chat] EXCEPTION: {str(e)[:200]}")

    if not result:
        print(f"  [chat] ALL CANDIDATES FAILED - using hard fallback")
        result = self._get_hard_fallback_response()

    print(f"  [chat] returning ({len(result)} chars): {repr(result[:100])}...")
    return result

client_mod.LLMClient.chat = traced_chat

# Now import and use
from src.llm.client import llm_client

model = "opencode/deepseek-v4-flash-free"
system = "You are a helpful assistant."
prompt = 'Return ONLY valid JSON:\n{"test": "value", "score": 42}'
enhanced = prompt + "\n\nThink step by step. Follow the output format strictly."

print("=== DEEP TRACE ===")
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

t0 = time.time()
result = llm_client.chat(model=model, system=system, user_message=enhanced, temperature=0.1)
elapsed = time.time() - t0

print(f"\n=== RESULT ({elapsed:.1f}s) ===")
print(f"Result ({len(result)} chars): {result[:300]}")
print(f"Is hard fallback: {result == 'Service temporarily unavailable. Using default optimization parameters.'}")
