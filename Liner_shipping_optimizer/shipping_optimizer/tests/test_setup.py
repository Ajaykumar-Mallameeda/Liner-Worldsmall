import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.utils.config import Config
from src.utils.logger import logger

def test_config ():
    """Test configuration loads correctly"""
    print("\n=== Testing Configuration ===")
    # The OpenRouter provider was retired (providers: groq, cerebras, google); ``LLM_API_KEY`` is the
    # backward-compatible alias of whichever provider key is present (src/utils/config.py).
    print(f"API Key present: {'Yes' if Config.LLM_API_KEY else 'No'}")
    print(f"Orchestrator model: {Config.ORCHESTRATOR_MODEL}")
    print(f"Regional model: {Config.REGIONAL_MODEL}")
    print(f"GA Population: {Config.GA_POPULATION_SIZE}")
    print(f"GA Generations: {Config.GA_GENERATIONS}")
    assert isinstance(Config.ORCHESTRATOR_MODEL, str) and Config.ORCHESTRATOR_MODEL
    assert isinstance(Config.REGIONAL_MODEL, str) and Config.REGIONAL_MODEL
    assert Config.GA_POPULATION_SIZE > 0 and Config.GA_GENERATIONS > 0
    print("✓ Configuration working!")
    
def test_logger():
    """Test logger works"""
    print("\n=== Testing Logger ===")
    logger.info("test_log_entry", test_key="test_value", number=42)
    print("✓ Logger working! (Check logs/ folder)")
    
if __name__ == "__main__":
    test_config()
    test_logger()
    print("\n All tests passed!")
    
    