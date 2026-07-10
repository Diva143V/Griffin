import sys
import os
import pandas as pd
from sentence_transformers import SentenceTransformer
from src.agents.query_planner import build_query_plan, execute_query_plan, get_valid_model

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_pipeline_cli.py <query> <email> <api_key>")
        sys.exit(1)
        
    query = sys.argv[1]
    email = sys.argv[2]
    api_key = sys.argv[3]
    
    # Initialize terminal.log to empty
    os.makedirs("dataset", exist_ok=True)
    with open("dataset/terminal.log", "w", encoding="utf-8") as f:
        f.write(f"--- Starting CLI Ingestion for query: '{query}' ---\n")
    
    try:
        resolved, _ = get_valid_model("llama3.1:8b")
        plan = build_query_plan(query, resolved, default_top_k=10)
        
        ranked_df = pd.DataFrame()
        claims_df = pd.DataFrame()
        contradictions = {}
        
        encoder_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        model_routing = {
            "overseer": "gemini-2.5-flash",
            "validation": "gemini-2.5-flash",
            "refinement": "gemini-2.5-flash",
            "peer_review": "gemini-2.5-flash",
            "consensus": "gemini-2.5-flash",
            "graph": "gemini-2.5-flash",
            "planner": "gemini-2.5-flash",
            "claim_extractor": "gemini-2.5-flash",
            "contradiction_detector": "gemini-2.5-flash",
            "consensus_analyst": "gemini-2.5-flash",
            "synthesis": "gemini-2.5-flash",
            "experiment_planner": "gemini-2.5-flash"
        }
        
        execute_query_plan(
            plan=plan,
            encoder_model=encoder_model,
            ranked_df=ranked_df,
            claims_df=claims_df,
            contradictions=contradictions,
            email=email,
            api_key=api_key,
            force_fresh=True,
            model_routing=model_routing
        )
    except Exception as e:
        with open("dataset/terminal.log", "a", encoding="utf-8") as f:
            f.write(f"\nPipeline Error: {str(e)}\n")
