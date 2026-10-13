import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    load_dotenv(PROJECT_ROOT / ".env")
    DATA_DIR = PROJECT_ROOT / "data"
    LOGS_DIR = PROJECT_ROOT / "logs"

    # ----------------------------------------------------------------
    # Backward-compatible fields (kept so legacy imports don't break).
    # The new code uses src.llm.providers directly and ignores these.
    # ----------------------------------------------------------------
    # Per-provider API keys.
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    # Legacy alias — falls back to whichever provider key is present.
    LLM_API_KEY = GROQ_API_KEY or CEREBRAS_API_KEY or GOOGLE_API_KEY
    LLM_BASE_URL = os.getenv(
        "LLM_BASE_URL", "https://api.groq.com/openai/v1"
    )

    # Model names — read from the new provider-specific env, with sane
    # legacy defaults so the old test_llm.py still works against Groq.
    ORCHESTRATOR_MODEL = os.getenv(
        "GROQ_ORCHESTRATOR_MODEL",
        os.getenv("ORCHESTRATOR_MODEL", "llama-3.3-70b-versatile"),
    )
    REGIONAL_MODEL = os.getenv(
        "GROQ_REGIONAL_MODEL",
        os.getenv("REGIONAL_MODEL", "llama-3.3-70b-versatile"),
    )

    # New routing / cache / fallback knobs.
    LLM_PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "groq,cerebras,google")
    LLM_CACHE_ENABLED = os.getenv("LLM_CACHE_ENABLED", "true").lower() not in (
        "0", "false", "no"
    )
    LLM_429_COOLDOWN_SEC = float(os.getenv("LLM_429_COOLDOWN_SEC", "60"))
    LLM_PROVIDER_FAILURE_THRESHOLD = int(
        os.getenv("LLM_PROVIDER_FAILURE_THRESHOLD", "2")
    )
    LLM_ENABLE_PROVIDER_FAILOVER = os.getenv(
        "LLM_ENABLE_PROVIDER_FAILOVER", "true"
    ).lower() in ("1", "true", "yes")
    LLM_ENABLE_DETERMINISTIC_FALLBACK = os.getenv(
        "LLM_ENABLE_DETERMINISTIC_FALLBACK", "true"
    ).lower() in ("1", "true", "yes")
    LLM_REQUEST_TIMEOUT_SEC = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "30"))

    GA_POPULATION_SIZE = int(os.getenv("GA_POPULATION_SIZE", "80"))
    GA_GENERATIONS = int(os.getenv("GA_GENERATIONS", "120"))
    MILP_TIME_LIMIT = int(os.getenv("MILP_TIME_LIMIT", "120"))

    @classmethod
    def validate(cls):

        # We do NOT require a key here — a provider-less config (where every
        # agent will end up in fallback) is a valid development setup, and the
        # pipeline must boot so the operator can see the health report.
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)

        if not (cls.GROQ_API_KEY or cls.CEREBRAS_API_KEY or cls.GOOGLE_API_KEY):
            print("! No provider API keys configured.")
            print("  Set GROQ_API_KEY, CEREBRAS_API_KEY, or GOOGLE_API_KEY in your .env")
            print("  The pipeline will run, but every LLM call will fall back to rule-based logic.")
        else:
            print("+ Configuration validated")
            print(f"  Provider order: {cls.LLM_PROVIDER_ORDER}")


Config.validate()
