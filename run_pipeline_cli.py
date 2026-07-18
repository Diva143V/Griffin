import sys
import os
import json
import pandas as pd
from sentence_transformers import SentenceTransformer
from src.agents.query_planner import build_query_plan, execute_query_plan, get_valid_model


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_json(name: str, default):
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline_cli.py <query>")
        print("  Secrets are read from environment variables:")
        print("    ENTREZ_EMAIL, GEMINI_API_KEY, SEMANTIC_SCHOLAR_API_KEY")
        sys.exit(1)

    query = sys.argv[1]
    
    # Read secrets exclusively from environment variables (never from CLI args).
    email = os.environ.get("ENTREZ_EMAIL", "")
    api_key = os.environ.get("GEMINI_API_KEY", "")
    sc_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

    # Optional refinement from Reflex UI (appended to the research question)
    refinement = os.environ.get("GRIFFIN_REFINEMENT", "").strip()
    if refinement:
        query = f"{query} (Refinement: {refinement})"

    # UI pipeline controls (defaults preserve previous CLI behaviour only when unset)
    force_fresh = _env_bool("GRIFFIN_FORCE_FRESH", default=True)
    forced_agents_raw = os.environ.get("GRIFFIN_FORCED_AGENTS", "").strip()
    forced_agents = (
        [a.strip() for a in forced_agents_raw.split(",") if a.strip()]
        if forced_agents_raw
        else None
    )
    collector_limits = _env_json("GRIFFIN_COLLECTOR_LIMITS", None)
    if collector_limits is not None and not isinstance(collector_limits, dict):
        collector_limits = None

    run_dir = os.environ.get("GRIFFIN_RUN_DIR", "dataset")

    # Initialize terminal.log to empty
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "terminal.log"), "w", encoding="utf-8") as f:
        f.write(f"--- Starting CLI Ingestion for query: '{query}' ---\n")
        f.write(
            f"Controls: force_fresh={force_fresh}, "
            f"forced_agents={forced_agents}, "
            f"collector_limits={collector_limits}\n"
        )

    # Disable ChromaDB telemetry to suppress capture() warnings
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    
    try:
        # Read model routing from environment (set by Reflex UI) or use defaults
        default_routing = {
            "planner": "llama3.1:8b",
            "claim_extractor": "llama3.1:8b",
            "contradiction_detector": "qwen3.5:9b",
            "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
            "synthesis": "llama3.1:8b",
            "experiment_planner": "llama3.1:8b",
            "primer": "llama3.1:8b",
            "glossary": "llama3.1:8b",
            "methodology": "llama3.1:8b",
            "clinical": "llama3.1:8b",
            "bias": "llama3.1:8b",
        }

        env_routing = os.environ.get("GRIFFIN_ROUTING", "")
        if env_routing:
            try:
                model_routing = json.loads(env_routing)
            except json.JSONDecodeError:
                model_routing = default_routing
        else:
            model_routing = default_routing

        # Read LLM options from environment or use defaults
        default_llm_opts = {"temperature": 0.7, "num_ctx": 8192, "num_predict": 4096}
        env_llm_opts = os.environ.get("GRIFFIN_LLM_OPTS", "")
        if env_llm_opts:
            try:
                llm_options = json.loads(env_llm_opts)
            except json.JSONDecodeError:
                llm_options = default_llm_opts
        else:
            llm_options = default_llm_opts

        # Resolve planner model with fallback
        planner_model = model_routing.get("planner", "llama3.1:8b")
        resolved, _ = get_valid_model(planner_model)
        plan = build_query_plan(query, resolved, default_top_k=10)

        ranked_df = pd.DataFrame()
        claims_df = pd.DataFrame()
        contradictions = {}

        encoder_model = SentenceTransformer("BAAI/bge-small-en-v1.5")

        # Pass Semantic Scholar API key via environment if provided
        if sc_api_key:
            os.environ["SEMANTIC_SCHOLAR_API_KEY"] = sc_api_key

        result = execute_query_plan(
            plan=plan,
            encoder_model=encoder_model,
            ranked_df=ranked_df,
            claims_df=claims_df,
            contradictions=contradictions,
            email=email,
            api_key=sc_api_key or api_key,
            force_fresh=force_fresh,
            forced_agents=forced_agents,
            collector_limits=collector_limits,
            model_routing=model_routing,
            llm_options=llm_options,
            status_callback=lambda msg: print(msg, flush=True),
        )

        # Persist full execution trace for the Reflex UI
        try:
            os.makedirs(run_dir, exist_ok=True)
            # Ensure JSON-serializable (sources may contain non-JSON types)
            def _sanitize(obj):
                if isinstance(obj, dict):
                    return {str(k): _sanitize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_sanitize(v) for v in obj]
                if isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                return str(obj)

            with open(os.path.join(run_dir, "execution_trace.json"), "w", encoding="utf-8") as f:
                json.dump(_sanitize(result), f, indent=2, ensure_ascii=False)
            with open(os.path.join(run_dir, "terminal.log"), "a", encoding="utf-8") as f:
                f.write(f"\nExecution trace written to {os.path.join(run_dir, 'execution_trace.json')}\n")
        except Exception as te:
            with open(os.path.join(run_dir, "terminal.log"), "a", encoding="utf-8") as f:
                f.write(f"\nWarning: failed to write execution_trace.json: {te}\n")

    except Exception as e:
        with open(os.path.join(run_dir, "terminal.log"), "a", encoding="utf-8") as f:
            f.write(f"\nPipeline Error: {str(e)}\n")
        raise
