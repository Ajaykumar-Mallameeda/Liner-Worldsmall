"""Verify the P+1E fix is loaded in a fresh process."""
import sys
sys.path.insert(0, ".")

# Force fresh import
for mod in list(sys.modules.keys()):
    if mod.startswith("src"):
        del sys.modules[mod]

from src.agents.base import BaseAgent
import inspect

src = inspect.getsource(BaseAgent.call_llm)
print("has_json_instruction:", "has_json_instruction" in src)
print("skip_evaluator:", "skip_evaluator" in src)
print()
for line in src.split("\n"):
    if "has_json" in line or "skip_evaluator" in line or "enhanced_user" in line:
        print(f"  {line.strip()}")
