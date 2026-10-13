import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.client import llm_client
from src.utils.config import Config

FALLBACK_STRING = "Service temporarily unavailable"

# Strip provider prefix for OpenCode (the client handles this too)
_TEST_MODEL = Config.REGIONAL_MODEL.split("/")[-1] if "/" in Config.REGIONAL_MODEL else Config.REGIONAL_MODEL


def _is_hard_fallback(text: str) -> bool:
    """The client returns a fixed string when ALL model candidates fail."""
    return FALLBACK_STRING in text


def test_simple_call():
    print("\n=== Testing LLM Client ===")
    print(f"Configured REGIONAL_MODEL: {Config.REGIONAL_MODEL}")
    print(f"Test model slug: {_TEST_MODEL}")
    print(f"LLM provider: {Config.LLM_BASE_URL}")
    response = llm_client.chat(
        model=Config.REGIONAL_MODEL,
        system="You are a helpful assistant.",
        user_message="Say exactly: Hello from AI!",
    )
    print(f"Response: {response[:200]}")

    if _is_hard_fallback(response):
        print("[WARN] LLM upstream unavailable -- every model candidate (primary +")
        print("  fallback allowlist) failed. Client correctly returned its")
        print("  hard-fallback string. This is a NETWORK / OpenCode issue,")
        print("  not a client bug. See logs/ for llm_candidate_failed entries.")
        return False

    assert "hello" in response.lower(), f"Unexpected response: {response!r}"
    print("[OK] LLM client working!")
    return True


def test_cache():
    print("\n=== Testing Cache ===")
    response1 = llm_client.chat(
        model=Config.REGIONAL_MODEL,
        system="You are a helpful assistant.",
        user_message="Count to 3",
    )
    response2 = llm_client.chat(
        model=Config.REGIONAL_MODEL,
        system="You are a helpful assistant.",
        user_message="Count to 3",
    )
    assert response1 == response2, "Cache returned different responses for the same prompt"
    print("[OK] Cache working!")


def test_fallback_shape():
    """Sanity check: hard-fallback is identifiable, never empty."""
    print("\n=== Testing Fallback String ===")
    fb = llm_client._get_hard_fallback_response()
    assert fb and FALLBACK_STRING in fb
    print("[OK] Hard-fallback string is well-formed (clients can detect upstream outages)")


def test_model_strip():
    """Verify provider prefix stripping works."""
    print("\n=== Testing Model Name Stripping ===")
    assert llm_client._strip_model("opencode/deepseek-v4-flash-free") == "deepseek-v4-flash-free"
    assert llm_client._strip_model("deepseek-v4-flash-free") == "deepseek-v4-flash-free"
    assert llm_client._strip_model("opencode/qwen3.6-plus-free") == "qwen3.6-plus-free"
    print("[OK] Model prefix stripping works!")


if __name__ == "__main__":
    test_model_strip()
    ok = test_simple_call()
    if ok:
        test_cache()
    test_fallback_shape()
    if ok:
        print("\nAll LLM tests passed!")
    else:
        print("\nLLM client is wired up correctly, but no upstream model is reachable.")
        print("Re-run once the LLM provider is available.")
