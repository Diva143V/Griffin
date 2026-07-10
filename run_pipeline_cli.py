import sys
import os
import json
import pandas as pd
from sentence_transformers import SentenceTransformer
from src.agents.query_planner import build_query_plan, execute_query_plan, get_valid_model

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_pipeline_cli.py <query> <email> <api_key> [sc_api_key]")
        sys.exit(1)
        
    query = sys.argv[1]
    email = sys.argv[2]
    api_key = sys.argv[3]
    sc_api_key = sys.argv[4] if len(sys.argv) > 4 else ""
    
    # Initialize terminal.log to empty
    os.makedirs("dataset", exist_ok=True)
    with open("dataset/terminal.log", "w", encoding="utf-8") as f:
        f.write(f"--- Starting CLI Ingestion for query: '{query}' ---\n")
    
    try:
        # Read model routing from environment (set by Reflex UI) or use defaults
        default_routing = {
            "planner": "llama3.1:8b",
            "claim_extractor": "llama3.1:8b",
            "contradiction_detector": "qwen3.5:9b",
            "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
            "synthesis": "llama3.1:8b",
            "experiment_planner": "llama3.1:8b"
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
        
        encoder_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
        
        # Pass Semantic Scholar API key via environment if provided
        if sc_api_key:
            os.environ["SEMANTIC_SCHOLAR_API_KEY"] = sc_api_key
        
        execute_query_plan(
            plan=plan,
            encoder_model=encoder_model,
            ranked_df=ranked_df,
            claims_df=claims_df,
            contradictions=contradictions,
            email=email,
            api_key=sc_api_key or api_key,
            force_fresh=True,
            model_routing=model_routing,
            llm_options=llm_options
        )
    except Exception as e:
        with open("dataset/terminal.log", "a", encoding="utf-8") as f:
            f.write(f"\nPipeline Error: {str(e)}\n")

