"""Project configuration and secrets loader.

Reads API keys from environment variables. Do NOT commit secrets to source control.
"""
import os

SEMANTIC_SCHOLAR_API_KEY_ENV = "SEMANTIC_SCHOLAR_API_KEY"
SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"


def get_semantic_scholar_api_key() -> str | None:
    """Return the Semantic Scholar API key from the environment or None if unset."""
    return os.environ.get(SEMANTIC_SCHOLAR_API_KEY_ENV)


def require_semantic_scholar_api_key() -> str:
    """Return the API key or raise a clear error if it's missing."""
    key = get_semantic_scholar_api_key()
    if not key:
        raise RuntimeError(
            f"Semantic Scholar API key not found. Set the environment variable {SEMANTIC_SCHOLAR_API_KEY_ENV}."
        )
    return key


MODEL_ROUTING = {
    "planner": "llama3.1:8b",
    "claim_extractor": "llama3.1:8b",
    "contradiction_detector": "qwen3.5:9b",
    "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
    "synthesis": "llama3.1:8b",
    "experiment_planner": "llama3.1:8b",
}
