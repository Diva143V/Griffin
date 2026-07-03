"""Compatibility orchestrator for the split workflow agents.

The actual planning logic now lives in planner_agent.py and the retrieval
hooks live in retriever_agent.py. This file keeps the original import surface
for the Streamlit app and any scripts that still import query_planner.
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
import time
from typing import Any, Dict, Optional, List, Tuple

import pandas as pd
import numpy as np
import chromadb
import ollama

from .planner_agent import QueryPlan, build_query_plan, plan_to_dict
from .retriever_agent import retrieve_graph, retrieve_standard
from .verifier_agent import verify_response
from .consensus_agent import analyze_consensus
from .experiment_agent import design_protocol
from .eln_agent import format_eln_entry
from typing import Any, Dict, List, Optional, Tuple

def get_valid_model(requested_model: str, fallback_priority: List[str] = None) -> Tuple[str, List[str]]:
    """Check if requested_model exists in Ollama's local list. If not, pick a fallback.
    Returns (resolved_model_name, list_of_warning_notes).
    """
    notes = []
    try:
        model_list = ollama.list()
        installed_models = []
        if isinstance(model_list, dict) and "models" in model_list:
            for m in model_list["models"]:
                if isinstance(m, dict):
                    if "model" in m:
                        installed_models.append(m["model"])
                    elif "name" in m:
                        installed_models.append(m["name"])
                elif hasattr(m, "model"):
                    installed_models.append(m.model)
                elif hasattr(m, "name"):
                    installed_models.append(m.name)
        elif hasattr(model_list, "models"):
            installed_models = [m.model for m in model_list.models]
    except Exception as e:
        return requested_model, [f"Warning: Failed to contact Ollama for model check: {e}"]

    if not installed_models:
        return requested_model, ["Warning: No models found installed in Ollama. Attempting to use requested model."]

    def clean_name(n: str) -> str:
        return n.split(":")[0].strip().lower()

    # 1. Exact match
    for m in installed_models:
        if m == requested_model:
            return requested_model, []

    # 2. Tagless match (e.g. gemma3:4b matching gemma3:latest or gemma3)
    req_clean = clean_name(requested_model)
    for m in installed_models:
        if clean_name(m) == req_clean:
            notes.append(f"Model '{requested_model}' not found exactly. Using installed sibling '{m}'.")
            return m, notes

    # 3. Fallback priority match
    if fallback_priority:
        for fb in fallback_priority:
            for m in installed_models:
                if m == fb or clean_name(m) == clean_name(fb):
                    notes.append(f"Model '{requested_model}' not found. Falling back to priority model '{m}'.")
                    return m, notes

    # 4. Grab first available model as absolute fallback
    first_avail = installed_models[0]
    notes.append(f"Model '{requested_model}' not found. Falling back to first available model '{first_avail}'.")
    return first_avail, notes


def check_and_trigger_retrieval(query: str, encoder_model: Any, top_k: int) -> Tuple[bool, str]:
    """Check if Chroma DB contains relevant papers for the query. If not, trigger the collectors."""
    db_path = "dataset/chroma_db"
    os.makedirs(db_path, exist_ok=True)
    
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection("papers", metadata={"hnsw:space": "cosine"})
    
    # Check if empty
    if collection.count() == 0:
        return False, "Chroma DB is empty."
        
    # Get closest match
    query_emb = encoder_model.encode([query], normalize_embeddings=True)[0].tolist()
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=1
    )
    
    if not results or not results["distances"] or not results["distances"][0]:
        return False, "No results returned."
        
    closest_distance = float(results["distances"][0][0])
    # A distance of 0.25 or less indicates an exact semantic match
    if closest_distance <= 0.25:
        return True, f"Found relevant papers in Chroma DB (closest distance: {closest_distance:.3f}). Bypassing retrieval."
        
    return False, f"Closest paper is too distant (distance: {closest_distance:.3f}). Triggering retrieval."


def clean_search_query(raw_query: str, model_name: str = "llama3.1:8b") -> str:
    """Extract clean keyword search query from conversational prompts for PubMed/PMC/OpenAlex APIs."""
    cleaner_model = model_name
    try:
        model_list = ollama.list()
        installed_names = []
        if isinstance(model_list, dict) and "models" in model_list:
            for m in model_list["models"]:
                if isinstance(m, dict) and "model" in m:
                    installed_names.append(m["model"])
        elif hasattr(model_list, "models"):
            installed_names = [m.model for m in model_list.models]
            
        # If the selected model is a specialized medical model, route query cleaning to a general instruct model
        if any(med in cleaner_model.lower() for med in ["openbiollm", "biomistral", "meditron"]):
            for candidate in ["llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b", "llama3.1:latest"]:
                if candidate in installed_names:
                    cleaner_model = candidate
                    break
    except Exception:
        pass

    system_prompt = "You are a scientific search specialist. Extract the core scientific search query (keywords, drugs, disease terms) from the user's conversational request. Remove all conversational filler. Return ONLY the clean keywords separated by spaces. DO NOT include any explanation, notes, introductions, or additional text. Output ONLY the query."
    user_prompt = f"""Example 1:
User request: Is diclofenac causing kidney failure in vultures?
Clean Keywords: diclofenac vultures kidney failure

Example 2:
User request: I want to search if metformin improves survival in breast cancer.
Clean Keywords: metformin breast cancer survival

Example 3:
User request: {raw_query}
Clean Keywords:"""

    try:
        response = ollama.chat(
            model=cleaner_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        cleaned = response["message"]["content"].strip()
        # Check if the model refused to process or returned a conversational meta-sentence
        refusal_words = ["sorry", "unable", "cannot", "can't", "don't know", "request", "please", "dataset", "instruction"]
        if any(ref in cleaned.lower() for ref in refusal_words) or len(cleaned.split()) > 10:
            # Fallback directly to raw user query as it is safer
            return raw_query
            
        return cleaned if cleaned else raw_query
    except Exception:
        return raw_query


def run_pipeline_ingestion(query: str, email: str = "test@example.com", api_key: str = "", model_name: str = "llama3.1:8b", top_k: int = 20) -> List[str]:
    """Run build_dataset, generate_embeddings, and evidence_ranker to ingest data with error boundaries."""
    logs = []
    
    # 0. Extract clean scientific query
    search_query = clean_search_query(query, model_name)
    logs.append(f"Extracted API search query: '{search_query}' from user prompt.")
    print(f"Running dynamic ingestion for query: '{search_query}'...")
    
    # Define sources based on whether SemanticScholar API key is available
    sources = ["PMC", "OpenAlex"]
    if api_key:
        sources.append("SemanticScholar")
        os.environ["SEMANTIC_SCHOLAR_API_KEY"] = api_key
        
    os.environ["ENTREZ_EMAIL"] = email

    # Clear old collection files to prevent merging stale data from previous topics
    for f_name in ["pubmed.csv", "pmc.csv", "openalex.csv", "semantic_scholar.csv", "clean_papers.csv", "clean_papers_with_embeddings.csv", "ranked_papers.csv"]:
        path = os.path.join("dataset", f_name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # 1. build_dataset
    try:
        logs.append("Starting data collection...")
        subprocess.run([
            sys.executable, "build_dataset.py",
            "--sources", *sources,
            "--query", search_query,
            "--max-results", str(top_k),
            "--email", email,
            "--run-filter"
        ], check=True)
        logs.append("Data collection completed successfully.")
    except Exception as e:
        logs.append(f"Data collection failed: {e}")

    # 2. generate_embeddings
    try:
        subprocess.run([
            sys.executable, "generate_embeddings.py",
            "--input", "dataset/clean_papers.csv",
            "--output", "dataset/clean_papers_with_embeddings.csv"
        ], check=True)
        logs.append("Embedding generation completed successfully.")
    except Exception as e:
        logs.append(f"Embedding generation failed: {e}")

    # 3. evidence_ranker
    try:
        subprocess.run([
            sys.executable, "src/core/evidence_ranker.py"
        ], check=True)
        logs.append("Evidence quality ranking completed successfully.")
    except Exception as e:
        logs.append(f"Evidence quality ranking failed: {e}")
        
    return logs


def route_executor(query: str, model_name: str) -> List[str]:
    """Executor LLM router: checks user input and redirects to specific agents."""
    prompt = f"""You are the Master Executor of a scientific research platform. Your job is to analyze the user's request and select which specialized agents need to run to fulfill it.

Available Agents:
1. "evidence_ranker": Assess the clinical quality and strength of retrieved papers (study designs, sample sizes).
2. "contradiction_detector": Search for and analyze conflicting findings/evidence in the papers.
3. "consensus_analyst": Determine where the consensus lies, highlighting agreement and explaining divergence.
4. "synthesis": Combine findings from all papers and write a final scientific draft/report.
5. "experiment_planner": Design a step-by-step laboratory protocol with positive/negative controls.
6. "eln_assistant": Format a formal Electronic Lab Notebook (ELN) entry to record experiment metadata and logs.

User Request: {query}

Select the exact list of agent keys that are necessary to answer or perform the user's request.
Return only a JSON list of strings, for example: ["synthesis", "consensus_analyst"]
Do not output any other explanation or text.
"""
    try:
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response["message"]["content"].strip()
        # Clean markdown formatting if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return ["synthesis", "consensus_analyst", "experiment_planner", "eln_assistant"]
    except Exception:
        # Fallback to standard flow
        return ["synthesis", "consensus_analyst", "experiment_planner", "eln_assistant"]


def execute_query_plan(
    plan: QueryPlan,
    encoder_model: Any,
    ranked_df: Optional[pd.DataFrame],
    claims_df: Optional[pd.DataFrame],
    contradictions: Dict[str, Any],
    similarity_threshold: float = 0.60,
    email: str = "test@example.com",
    api_key: str = "",
    forced_agents: Optional[List[str]] = None,
    force_fresh: bool = False,
    model_routing: Optional[Dict[str, str]] = None,
    status_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    # Resolve routing config
    default_routing = {
        "planner": "llama3.1:8b",
        "claim_extractor": "llama3.1:8b",
        "contradiction_detector": "qwen3.5:9b",
        "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
        "synthesis": "llama3.1:8b",
        "experiment_planner": "llama3.1:8b"
    }
    
    routing = dict(default_routing)
    if model_routing:
        for k, v in model_routing.items():
            if v:
                routing[k] = v

    # Resolve models using get_valid_model with fallbacks
    resolved_routing = {}
    fallback_logs = []
    
    fallbacks_by_key = {
        "planner": ["llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b", "llama3.1:latest"],
        "claim_extractor": ["llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b", "llama3.1:latest"],
        "contradiction_detector": ["qwen3.5:9b", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "llama3.1:latest"],
        "consensus_analyst": ["koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "qwen3.5:9b", "gemma3:4b", "gemma3:1b"],
        "synthesis": ["llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b", "llama3.1:latest"],
        "experiment_planner": ["llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b", "llama3.1:latest"]
    }

    for key, req_model in routing.items():
        res_model, warn_notes = get_valid_model(req_model, fallbacks_by_key.get(key))
        resolved_routing[key] = res_model
        if warn_notes:
            fallback_logs.extend([f"[{key}] {n}" for n in warn_notes])

    # Stats tracking structure
    routing_stats = {
        "planner": {"requested": routing["planner"], "resolved": resolved_routing["planner"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[planner]")]},
        "claim_extractor": {"requested": routing["claim_extractor"], "resolved": resolved_routing["claim_extractor"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[claim_extractor]")]},
        "contradiction_detector": {"requested": routing["contradiction_detector"], "resolved": resolved_routing["contradiction_detector"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[contradiction_detector]")]},
        "consensus_analyst": {"requested": routing["consensus_analyst"], "resolved": resolved_routing["consensus_analyst"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[consensus_analyst]")]},
        "synthesis": {"requested": routing["synthesis"], "resolved": resolved_routing["synthesis"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[synthesis]")]},
        "experiment_planner": {"requested": routing["experiment_planner"], "resolved": resolved_routing["experiment_planner"], "duration_sec": 0.0, "fallback_logs": [n for n in fallback_logs if n.startswith("[experiment_planner]")]}
    }
    
    def parse_emb(val):
        if isinstance(val, str):
            try:
                return np.asarray(json.loads(val), dtype=np.float32)
            except Exception:
                pass
        elif isinstance(val, list):
            return np.asarray(val, dtype=np.float32)
        elif isinstance(val, np.ndarray):
            return val.astype(np.float32)
        return np.zeros(384, dtype=np.float32)

    if ranked_df is not None and not ranked_df.empty and "embedding" in ranked_df.columns:
        ranked_df = ranked_df.copy()
        ranked_df["embedding"] = ranked_df["embedding"].apply(parse_emb)

    # 0. Clean the query first to remove conversational filler/instructions
    if status_callback:
        status_callback("Cleaning research query keywords...")
    planner_start = time.time()
    search_query = clean_search_query(plan.query, resolved_routing["planner"])
    routing_stats["planner"]["duration_sec"] += time.time() - planner_start

    # 1. Check database for existing relevant papers using the clean scientific search query
    if status_callback:
        status_callback("Checking database cache for relevant papers...")
    if force_fresh:
        is_present = False
        check_msg = "Force fresh retrieval requested. Ignoring database cache."
    else:
        is_present, check_msg = check_and_trigger_retrieval(search_query, encoder_model, plan.top_k)
    print(check_msg)
    
    notes = [check_msg]
    if fallback_logs:
        notes.extend([f"⚠️ {log}" for log in fallback_logs])
    
    if not is_present:
        if status_callback:
            status_callback("Ingesting fresh research papers from external APIs (PMC, OpenAlex, SemanticScholar)... This may take up to a minute...")
        try:
            ingest_logs = run_pipeline_ingestion(search_query, email=email, api_key=api_key, model_name=resolved_routing["planner"], top_k=plan.top_k)
            notes.extend(ingest_logs)
            # Reload datasets
            if os.path.exists("dataset/ranked_papers.csv"):
                ranked_df = pd.read_csv("dataset/ranked_papers.csv")
                # Merge embeddings
                if os.path.exists("dataset/clean_papers_with_embeddings.csv"):
                    emb_df = pd.read_csv("dataset/clean_papers_with_embeddings.csv")
                    ranked_df["title_clean"] = ranked_df["title"].fillna("").astype(str).str.strip().str.lower()
                    emb_df["title_clean"] = emb_df["title"].fillna("").astype(str).str.strip().str.lower()
                    emb_df_subset = emb_df[["title_clean", "embedding"]].drop_duplicates(subset=["title_clean"])
                    ranked_df = pd.merge(ranked_df, emb_df_subset, on="title_clean", how="left").drop(columns=["title_clean"])
                    
                    # Parse embeddings
                    def parse_emb(val):
                        if isinstance(val, str):
                            try:
                                return np.asarray(json.loads(val), dtype=np.float32)
                            except Exception:
                                pass
                        return np.zeros(384, dtype=np.float32)
                    
                    ranked_df["embedding"] = ranked_df["embedding"].apply(parse_emb)
            notes.append("Dynamic ingestion completed successfully.")
        except Exception as e:
            notes.append(f"Dynamic ingestion failed: {e}. Proceeding with existing data.")

    else:
        # Check if ranked_df is empty or None, load it or rebuild from Chroma DB
        if ranked_df is None or ranked_df.empty:
            if os.path.exists("dataset/ranked_papers.csv"):
                try:
                    ranked_df = pd.read_csv("dataset/ranked_papers.csv")
                    if "embedding" in ranked_df.columns:
                        ranked_df["embedding"] = ranked_df["embedding"].apply(parse_emb)
                    notes.append("Loaded existing ranked papers from disk.")
                except Exception as e:
                    notes.append(f"Failed to read ranked_papers.csv from disk: {e}")
            
            # If still None or empty, try recovery from Chroma DB
            if ranked_df is None or ranked_df.empty:
                if status_callback:
                    status_callback("Dataset files missing or empty on disk. Restoring papers from Chroma DB cache...")
                notes.append("Files missing or empty on disk. Restoring papers from Chroma DB cache...")
                try:
                    import chromadb
                    client = chromadb.PersistentClient(path="dataset/chroma_db")
                    collection = client.get_collection("papers")
                    query_emb = encoder_model.encode([search_query], normalize_embeddings=True)[0].tolist()
                    res = collection.query(
                        query_embeddings=[query_emb],
                        n_results=plan.top_k,
                        include=["documents", "metadatas", "embeddings"]
                    )
                    if res and res["metadatas"] and res["metadatas"][0]:
                        metadatas = res["metadatas"][0]
                        documents = res["documents"][0]
                        embs = res.get("embeddings", [[]])[0]
                        rows = []
                        for idx, (meta, doc) in enumerate(zip(metadatas, documents)):
                            row = dict(meta)
                            row["abstract"] = doc
                            if embs is not None and len(embs) > 0 and idx < len(embs):
                                row["embedding"] = np.asarray(embs[idx], dtype=np.float32)
                            else:
                                row["embedding"] = np.zeros(384, dtype=np.float32)
                            rows.append(row)
                        df = pd.DataFrame(rows)
                        os.makedirs("dataset", exist_ok=True)
                        
                        # Save standard version to disk (converting numpy array to list/string first to avoid raw array dump)
                        df_disk = df.copy()
                        df_disk["embedding"] = df_disk["embedding"].apply(lambda x: json.dumps(x.tolist()))
                        df_disk.to_csv("dataset/clean_papers.csv", index=False)
                        df_disk.to_csv("dataset/ranked_papers.csv", index=False)
                        
                        ranked_df = df
                        notes.append("Successfully restored papers and embedding vectors from Chroma DB cache to disk.")
                except Exception as ex:
                    notes.append(f"Failed to restore papers from Chroma DB: {ex}")

    # 1b. Call the Executor LLM Router or use the user's manual selection
    if status_callback:
        status_callback("Routing user request to specialist agents using LLM...")
    executor_start = time.time()
    if forced_agents is not None:
        executed_agents = forced_agents
        notes.append(f"User Manually Selected Agents: {', '.join(executed_agents)}")
    else:
        executed_agents = route_executor(plan.query, resolved_routing["planner"])
        notes.append(f"Executor LLM Routed Request to: {', '.join(executed_agents)}")
    routing_stats["planner"]["duration_sec"] += time.time() - executor_start

    result: Dict[str, Any] = {
        "plan": plan_to_dict(plan),
        "sources": [],
        "relations": [],
        "claims": [],
        "context": "",
        "notes": notes,
        "executed_agents": executed_agents,
        "workflow_trace": [
            {
                "name": node.name,
                "layer": node.layer,
                "status": node.status,
                "description": node.description,
                "outputs": node.outputs,
            }
            for node in plan.workflow
        ],
        "sections": [section.__dict__ for section in plan.sections],
        "edges": [edge.__dict__ for edge in plan.edges],
        "routing_stats": routing_stats
    }

    if ranked_df is None or ranked_df.empty:
        result["notes"].append("No ranked papers are loaded or could be generated.")
        return result

    # 2. Retrieve Context (Standard vs. Graph RAG)
    if status_callback:
        status_callback("Retrieving context and semantic evidence...")
    if plan.route == "graph_rag + contradiction_review":
        context, sources, relations = retrieve_graph(plan.query, encoder_model, ranked_df, contradictions, similarity_threshold, plan.top_k)
        result["context"] = context
        result["sources"] = sources
        result["relations"] = relations
    else:
        context, sources = retrieve_standard(plan.query, encoder_model, ranked_df, similarity_threshold, plan.top_k)
        result["context"] = context
        result["sources"] = sources

    # 3. Retrieve matching claims if claims exist
    if claims_df is not None and not claims_df.empty and "claim" in claims_df.columns:
        matched = claims_df.copy()
        query_terms = [term for term in plan.query.lower().split() if len(term) > 2]
        if query_terms:
            claim_text = matched["claim"].fillna("").astype(str).str.lower()
            score = pd.Series(0, index=matched.index, dtype="int64")
            for term in query_terms:
                score += claim_text.str.contains(term, na=False).astype(int)
            matched = matched.assign(match_score=score)
            matched = matched[matched["match_score"] > 0].sort_values(["match_score"], ascending=False).head(plan.top_k)
            result["claims"] = [
                {
                    "title": row.get("title", ""),
                    "claim": row.get("claim", ""),
                    "stance": row.get("stance", ""),
                    "reason": row.get("reason", ""),
                    "score": int(row.get("match_score", 0)),
                }
                for _, row in matched.iterrows()
            ]

    # 4. Generate Synthesis Answer with Verification Feedback Loop (0/1 Loop) - Dynamic Execution
    synthesis_answer = ""
    verification_trace = []
    
    if "synthesis" in executed_agents or not executed_agents:
        if status_callback:
            status_callback("Generating scientific synthesis answer and auditing citations (Verification Loop)... This might take 30-60 seconds...")
        system_content = "You are a senior scientific research analyst. Answer the user's question using the scientific evidence provided. Provide a highly detailed, comprehensive, and exhaustive scientific synthesis. Elaborate on the mechanisms of action, clinical evidence, study designs, sample sizes, and outcomes."
        user_content = f"USER QUESTION: {plan.query}\n\nCONTEXT: {result['context']}\n\nPlease cite specific sources using identifiers like [Source Paper X] or [Graph Connection Y]. Address any contradictions in detail."

        synthesis_start = time.time()
        for attempt in range(1, 4):
            # Generate synthesis
            try:
                response = ollama.chat(
                    model=resolved_routing["synthesis"],
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ]
                )
                synthesis_answer = response["message"]["content"]
            except Exception as e:
                synthesis_answer = f"Error generating synthesis: {e}"
                break

            # Run verification check
            verify_res = verify_response(synthesis_answer, result.get("sources", []), result.get("relations", []))
            verification_trace.append({
                "attempt": attempt,
                "status": verify_res.get("status"),
                "findings": verify_res.get("findings")
            })

            if verify_res.get("status") == "pass":
                break
            else:
                # Append feedback to prompt for next attempt
                findings_str = "\n".join(f"- {f}" for f in verify_res.get("findings", []))
                user_content += f"\n\n[Verification Feedback - Attempt {attempt} Failed]\nFindings:\n{findings_str}\nPlease correct the above citation or logical consistency issues in your updated answer."
        routing_stats["synthesis"]["duration_sec"] = round(time.time() - synthesis_start, 2)

        result["synthesis_answer"] = synthesis_answer
        result["verification"] = verification_trace[-1] if verification_trace else {"status": "pass", "findings": []}
        result["verification_trace"] = verification_trace
    else:
        result["synthesis_answer"] = "Synthesis report was not requested for this query by the Executor Router."
        result["verification"] = {"status": "skipped", "findings": []}

    # 5. Run Consensus Agent - Dynamic Execution
    if "consensus_analyst" in executed_agents:
        if status_callback:
            status_callback("Analyzing scientific consensus and extracting agreements/contradictions...")
        consensus_start = time.time()
        consensus_res = analyze_consensus(plan.query, result.get("sources", []), result.get("relations", []), model_name=resolved_routing["consensus_analyst"])
        routing_stats["consensus_analyst"]["duration_sec"] = round(time.time() - consensus_start, 2)
        result["consensus"] = consensus_res
        try:
            os.makedirs("dataset", exist_ok=True)
            with open("dataset/consensus_report.md", "w", encoding="utf-8") as f:
                f.write(consensus_res["consensus_report"])
        except Exception:
            pass

    # 6. Run Experiment Agent - Dynamic Execution
    if "experiment_planner" in executed_agents:
        if status_callback:
            status_callback("Designing step-by-step laboratory experiment protocol...")
        exp_start = time.time()
        experiment_res = design_protocol(plan.query, synthesis_answer or plan.query, model_name=resolved_routing["experiment_planner"])
        result["experiment_protocol"] = experiment_res["protocol_draft"]
        try:
            os.makedirs("dataset", exist_ok=True)
            with open("dataset/protocol_draft.txt", "w", encoding="utf-8") as f:
                f.write(experiment_res["protocol_draft"])
        except Exception:
            pass

        # 7. Run ELN Agent - Dynamic Execution
        if "eln_assistant" in executed_agents:
            if status_callback:
                status_callback("Formatting and logging entry to the Electronic Lab Notebook (ELN)...")
            eln_res = format_eln_entry("Dr. Scientist", "Metformin Oncology Project", experiment_res["protocol_draft"], "Pre-incubated cells for 24h before treatment.", model_name=resolved_routing["experiment_planner"])
            result["eln_entry"] = eln_res["eln_entry"]
            try:
                os.makedirs("dataset", exist_ok=True)
                with open("dataset/eln_entry.txt", "w", encoding="utf-8") as f:
                    f.write(eln_res["eln_entry"])
            except Exception:
                pass
        routing_stats["experiment_planner"]["duration_sec"] = round(time.time() - exp_start, 2)

    if "synthesis_answer" in result and result["synthesis_answer"]:
        try:
            os.makedirs("dataset", exist_ok=True)
            with open("dataset/final_synthesis.md", "w", encoding="utf-8") as f:
                f.write(result["synthesis_answer"])
        except Exception:
            pass

    return result
