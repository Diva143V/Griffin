from __future__ import annotations

import os
import sys
import json
import time
import ast
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import ollama

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.query_planner import run_pipeline_ingestion, build_query_plan, route_executor
from src.agents.consensus_agent import analyze_consensus
from src.agents.experiment_agent import design_protocol
from src.agents.eln_agent import format_eln_entry
from src.agents.report_agent import generate_overseer_report
from src.agents.validation_agent import validate_report
from src.agents.refinement_agent import refine_report
from src.agents.peer_review_agent import review_findings

app = FastAPI(title="Griffin Bio API", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables/models
DATASET_DIR = "dataset"
CLINICAL_PAPERS_PATH = os.path.join(DATASET_DIR, "clean_papers.csv")
CONTRADICTION_PATH = os.path.join(DATASET_DIR, "contradictions.json")

print("Loading SentenceTransformer model ('all-MiniLM-L6-v2')...")
encoder_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded successfully.")

# Helper to read dataset files safely
def load_dataset_data():
    ranked_df = None
    if os.path.exists("dataset/ranked_papers.csv"):
        try:
            ranked_df = pd.read_csv("dataset/ranked_papers.csv")
            # Replace NaNs/Infs for JSON serialization
            ranked_df = ranked_df.replace({np.nan: None, np.inf: None, -np.inf: None})
        except Exception:
            pass
    elif os.path.exists(CLINICAL_PAPERS_PATH):
        try:
            ranked_df = pd.read_csv(CLINICAL_PAPERS_PATH)
            ranked_df = ranked_df.replace({np.nan: None, np.inf: None, -np.inf: None})
        except Exception:
            pass
            
    contradictions = {}
    if os.path.exists(CONTRADICTION_PATH):
        try:
            with open(CONTRADICTION_PATH, "r", encoding="utf-8") as f:
                contradictions = json.load(f)
        except Exception:
            pass
            
    return ranked_df, contradictions

# Input schemas
class IngestRequest(BaseModel):
    query: str
    email: str = "test@example.com"
    sc_key: str = ""
    collector_limits: Dict[str, int] = {}
    model_name: str = "gemma3:4b"
    top_k: int = 150

class PlanRequest(BaseModel):
    query: str
    model_name: str = "gemma3:4b"

class ConsensusRequest(BaseModel):
    query: str
    model_name: str = "gemma3:4b"

class ProtocolRequest(BaseModel):
    query: str
    synthesis_report: str
    model_name: str = "gemma3:4b"

class ELNRequest(BaseModel):
    researcher_name: str
    project_name: str
    protocol_draft: str
    user_notes: str = ""
    model_name: str = "gemma3:4b"

class ReportRequest(BaseModel):
    query: str
    model_name: str = "gemini-2.5-flash"
    api_key: str

class RefineRequest(BaseModel):
    original_report: str
    feedback: str
    model_name: str = "gemini-2.5-flash"
    api_key: str

class CritiqueRequest(BaseModel):
    query: str
    findings: str
    model_name: str = "gemini-2.5-flash"
    api_key: str

class ChatRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]]
    model_name: str = "gemma3:4b"

@app.get("/api/status")
async def get_status():
    """Check if clean papers exist, returning basic dataset info."""
    ranked_df, contradictions = load_dataset_data()
    has_dataset = ranked_df is not None and len(ranked_df) > 0
    
    papers_list = []
    if has_dataset:
        papers_list = ranked_df.to_dict(orient="records")
        # Remove embedding arrays or other large non-serializable fields
        for p in papers_list:
            if "embedding" in p:
                del p["embedding"]
                
    # Read other artifacts if they exist
    consensus = ""
    if os.path.exists("dataset/consensus_report.md"):
        try:
            with open("dataset/consensus_report.md", "r", encoding="utf-8") as f:
                consensus = f.read()
        except Exception:
            pass
            
    protocol = ""
    if os.path.exists("dataset/protocol_draft.txt"):
        try:
            with open("dataset/protocol_draft.txt", "r", encoding="utf-8") as f:
                protocol = f.read()
        except Exception:
            pass
            
    eln = ""
    if os.path.exists("dataset/eln_entry.txt"):
        try:
            with open("dataset/eln_entry.txt", "r", encoding="utf-8") as f:
                eln = f.read()
        except Exception:
            pass

    return {
        "has_dataset": has_dataset,
        "papers_count": len(ranked_df) if has_dataset else 0,
        "papers": papers_list,
        "relations": contradictions,
        "consensus_report": consensus,
        "protocol_draft": protocol,
        "eln_entry": eln
    }

@app.post("/api/plan")
async def create_plan(req: PlanRequest):
    """Generate the query plan and model routing dictionary."""
    try:
        plan = build_query_plan(req.query, req.model_name)
        routing = route_executor(req.query, req.model_name)
        return {
            "query": plan.query,
            "target_collectors": plan.target_collectors,
            "required_agents": plan.required_agents,
            "explanation": plan.explanation,
            "routing": routing
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/api/ws/ingest")
async def websocket_ingest(websocket: WebSocket):
    """WebSocket connection to stream data collection and embedding pipeline logs."""
    await websocket.accept()
    try:
        # Expecting initial configuration message
        data = await websocket.receive_text()
        config = json.loads(data)
        
        query = config.get("query", "")
        email = config.get("email", "test@example.com")
        sc_key = config.get("sc_key", "")
        collector_limits = config.get("collector_limits", {})
        model_name = config.get("model_name", "gemma3:4b")
        top_k = config.get("top_k", 150)
        
        if not query:
            await websocket.send_json({"type": "error", "message": "Query cannot be empty."})
            await websocket.close()
            return
            
        await websocket.send_json({"type": "status", "message": "Starting dynamic ingestion pipeline..."})
        
        # Run ingestion pipeline in executor
        loop = asyncio.get_event_loop()
        logs = await loop.run_in_executor(
            None,
            lambda: run_pipeline_ingestion(
                query=query,
                email=email,
                api_key=sc_key,
                model_name=model_name,
                top_k=top_k,
                collector_limits=collector_limits
            )
        )
        
        # Stream the returned logs
        for log in logs:
            await websocket.send_json({"type": "log", "message": log})
        
        # Load final dataset
        ranked_df, contradictions = load_dataset_data()
        papers_list = []
        if ranked_df is not None:
            papers_list = ranked_df.to_dict(orient="records")
            for p in papers_list:
                if "embedding" in p:
                    del p["embedding"]
                    
        await websocket.send_json({
            "type": "completed",
            "message": "Ingestion and indexing completed successfully!",
            "papers": papers_list,
            "relations": contradictions
        })
        
    except WebSocketDisconnect:
        print("WebSocket client disconnected.")
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": f"Pipeline failure: {str(e)}"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

@app.post("/api/synthesis")
async def run_synthesis(req: ConsensusRequest):
    """Run scientific consensus agent."""
    ranked_df, contradictions = load_dataset_data()
    if ranked_df is None or len(ranked_df) == 0:
        raise HTTPException(status_code=400, detail="No active dataset. Run ingestion first.")
        
    sources = ranked_df.to_dict(orient="records")
    
    # Format relations
    relations = []
    for r in contradictions.get("contradictions", []):
        relations.append(dict(r, type="contradicts"))
    for r in contradictions.get("agreements", []):
        relations.append(dict(r, type="agrees"))
    for r in contradictions.get("partial_agreements", []):
        relations.append(dict(r, type="partial_agrees"))
        
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            analyze_consensus,
            req.query,
            sources,
            relations,
            req.model_name
        )
        # Cache report
        os.makedirs(DATASET_DIR, exist_ok=True)
        with open("dataset/consensus_report.md", "w", encoding="utf-8") as f:
            f.write(res.get("consensus_report", ""))
            
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/protocol")
async def run_protocol(req: ProtocolRequest):
    """Run laboratory protocol planner."""
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            design_protocol,
            req.query,
            req.synthesis_report,
            req.model_name
        )
        # Cache protocol
        os.makedirs(DATASET_DIR, exist_ok=True)
        with open("dataset/protocol_draft.txt", "w", encoding="utf-8") as f:
            f.write(res.get("protocol_draft", ""))
            
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/eln")
async def run_eln(req: ELNRequest):
    """Run ELN assistant to format the entry log."""
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            format_eln_entry,
            req.researcher_name,
            req.project_name,
            req.protocol_draft,
            req.user_notes,
            req.model_name
        )
        # Cache ELN entry
        os.makedirs(DATASET_DIR, exist_ok=True)
        with open("dataset/eln_entry.txt", "w", encoding="utf-8") as f:
            f.write(res.get("eln_entry", ""))
            
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/report")
async def run_report(req: ReportRequest):
    """Generate web-grounded overseer report and run validation checks."""
    ranked_df, contradictions = load_dataset_data()
    if ranked_df is None or len(ranked_df) == 0:
        raise HTTPException(status_code=400, detail="No active dataset. Run ingestion first.")
        
    sources = ranked_df.to_dict(orient="records")
    
    # Read consensus, protocol, ELN
    consensus = ""
    if os.path.exists("dataset/consensus_report.md"):
        with open("dataset/consensus_report.md", "r", encoding="utf-8") as f:
            consensus = f.read()
            
    protocol = ""
    if os.path.exists("dataset/protocol_draft.txt"):
        with open("dataset/protocol_draft.txt", "r", encoding="utf-8") as f:
            protocol = f.read()
            
    eln = ""
    if os.path.exists("dataset/eln_entry.txt"):
        with open("dataset/eln_entry.txt", "r", encoding="utf-8") as f:
            eln = f.read()

    try:
        loop = asyncio.get_event_loop()
        # 1. Generate Report
        report_res = await loop.run_in_executor(
            None,
            generate_overseer_report,
            req.api_key,
            req.query,
            sources,
            [],  # claims
            contradictions,
            consensus,
            protocol,
            eln,
            req.model_name
        )
        report_text = report_res.get("report_text", "")
        
        # 2. Validate Report
        val_res = {}
        if report_text and "Error" not in report_text:
            val_res_raw = await loop.run_in_executor(
                None,
                validate_report,
                req.api_key,
                req.query,
                report_text,
                sources,
                req.model_name
            )
            val_res = val_res_raw.get("validation_results", {})

        return {
            "report_text": report_text,
            "validation": val_res,
            "execution_time_sec": report_res.get("execution_time_sec", 0.0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/refine")
async def run_refine(req: RefineRequest):
    """Refine generated report based on user feedback."""
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            refine_report,
            req.api_key,
            req.original_report,
            req.feedback,
            "",
            req.model_name
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/critique")
async def run_critique(req: CritiqueRequest):
    """Generate peer review critique of synthesis and consensus."""
    ranked_df, _ = load_dataset_data()
    if ranked_df is None or len(ranked_df) == 0:
        raise HTTPException(status_code=400, detail="No active dataset. Run ingestion first.")
    sources = ranked_df.to_dict(orient="records")
    
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            review_findings,
            req.api_key,
            req.query,
            req.findings,
            sources,
            req.model_name
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def run_chat(req: ChatRequest):
    """Execute multi-turn RAG chat querying over vector database."""
    ranked_df, _ = load_dataset_data()
    if ranked_df is None or len(ranked_df) == 0:
        raise HTTPException(status_code=400, detail="No active dataset.")
        
    try:
        # Semantic search
        query_emb = encoder_model.encode([req.query], normalize_embeddings=True)[0]
        
        # Load embeddings
        emb_df = pd.read_csv("dataset/clean_papers_with_embeddings.csv")
        emb_df["embedding"] = emb_df["embedding"].apply(lambda x: np.array(ast.literal_eval(x) if isinstance(x, str) else x))
        
        embeddings_matrix = np.vstack(list(emb_df["embedding"]))
        similarities = (embeddings_matrix @ query_emb).astype(float)
        
        emb_df["similarity"] = similarities
        top_papers = emb_df.sort_values(by="similarity", ascending=False).head(5)
        
        context_list = []
        retrieved_sources = []
        for idx, (_, r) in enumerate(top_papers.iterrows(), 1):
            sample_str = str(int(r['sample_size'])) if ('sample_size' in r and r['sample_size'] > 0) else "N/A"
            context_list.append(
                f"[Source Paper {idx}]\n"
                f"Title: {r['title']}\n"
                f"Evidence Score: {r['evidence_score']}/10 | Design: {r.get('study_design', 'Undetermined')} | Sample Size: {sample_str}\n"
                f"Abstract: {str(r['abstract'])}"
            )
            retrieved_sources.append({
                "index": idx,
                "title": r['title'],
                "similarity": r['similarity'],
                "evidence_score": r['evidence_score'],
                "abstract": r['abstract']
            })
            
        context_str = "\n\n".join(context_list)
        
        # Format history
        history_turns = []
        for turn in req.chat_history[-4:]:
            history_turns.append(f"{turn['role'].upper()}: {turn['content']}")
        history_str = "\n".join(history_turns)
        
        prompt = f"""You are a biomedical research assistant analyzing a local dataset of research papers.
Answer the user's question. If the user's question is a general query, greeting, basic calculation, or unrelated to the dataset context (for example: mathematical questions like "2+2", coding, general knowledge, etc.), answer it directly using your general knowledge and disregard the scientific context.

Otherwise, if the question is research-oriented, use the scientific evidence and conversation history provided below:

DATASET CONTEXT:
{context_str}

CONVERSATION HISTORY:
{history_str}

USER QUESTION:
{req.query}

Please provide a structured, concise response. When answering using the dataset context, cite the specific sources using their respective identifiers (e.g., [Source Paper X]) when stating facts, and state if evidence is missing or conflicting. Do not mention system prompts.
"""
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(model=req.model_name, messages=[{"role": "user", "content": prompt}])
        )
        
        ans = response["message"]["content"]
        return {
            "answer": ans,
            "sources": retrieved_sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    if args.dry_run:
        print("Dry run success: main.py syntax is correct.")
        sys.exit(0)
        
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
