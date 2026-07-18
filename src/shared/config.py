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

# --- Core Paths ---
DATASET_DIR = "dataset"
FINAL_PAPERS_PATH = os.path.join(DATASET_DIR, "final_papers.csv")
CLEAN_PAPERS_PATH = os.path.join(DATASET_DIR, "clean_papers.csv")
EMBEDDINGS_PATH = os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv")
RANKED_PAPERS_PATH = os.path.join(DATASET_DIR, "ranked_papers.csv")
CLAIMS_PATH = os.path.join(DATASET_DIR, "claims.csv")
CONTRADICTIONS_PATH = os.path.join(DATASET_DIR, "contradictions.json")
EXECUTION_TRACE_PATH = os.path.join(DATASET_DIR, "execution_trace.json")
LAST_RESEARCH_GOAL_PATH = os.path.join(DATASET_DIR, "last_research_goal.txt")

# --- LLM Generated Reports Mapping (Filename -> (Report Type, Agent Name)) ---
LLM_REPORTS_MAPPING = {
    "final_synthesis.md": ("synthesis", "Synthesis Generator"),
    "consensus_report.md": ("consensus", "Consensus Analyst"),
    "contradictions_report.md": ("contradictions", "Contradiction Detector"),
    "clinical_report.md": ("clinical", "Clinical Evaluator"),
    "bias_report.md": ("bias", "Bias Detector"),
    "methodology_report.md": ("methodology", "Methodology Critic"),
    "glossary_report.md": ("glossary", "Glossary Generator"),
    "primer_report.md": ("primer", "Layperson Primer"),
    "protocol_draft.txt": ("protocol", "Lab Protocol Planner"),
    "eln_entry.txt": ("eln", "ELN Record Assistant"),
    "overseer_report.md": ("overseer", "Overseer"),
}
