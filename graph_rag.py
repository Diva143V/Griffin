"""Core RAG engine implementing both Standard (vector similarity) and Graph (relationship traversal) RAG."""
from __future__ import annotations

import ast
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import ollama
import pandas as pd
from sentence_transformers import SentenceTransformer

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def parse_embedding(value: Any) -> np.ndarray:
    """Safely parse embedding vectors from CSV values."""
    if isinstance(value, list):
        return np.asarray(value, dtype=np.float32)
    if isinstance(value, str):
        try:
            return np.asarray(json.loads(value), dtype=np.float32)
        except Exception:
            try:
                return np.asarray(ast.literal_eval(value), dtype=np.float32)
            except Exception:
                pass
    return np.asarray(value, dtype=np.float32)


def load_data(
    ranked_path: str = "dataset/ranked_papers.csv",
    embeddings_path: str = "dataset/clean_papers_with_embeddings.csv",
    contradictions_path: str = "dataset/contradictions.json"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load ranked papers and map embeddings, and load the contradictions graph."""
    if not os.path.exists(ranked_path):
        raise FileNotFoundError(f"Ranked papers file not found: {ranked_path}")
    
    df = pd.read_csv(ranked_path)
    
    # Merge embeddings if available
    if os.path.exists(embeddings_path):
        try:
            emb_df = pd.read_csv(embeddings_path)
            df["title_clean"] = df["title"].fillna("").astype(str).str.strip().str.lower()
            emb_df["title_clean"] = emb_df["title"].fillna("").astype(str).str.strip().str.lower()
            
            emb_df_subset = emb_df[["title_clean", "embedding"]].drop_duplicates(subset=["title_clean"])
            df = pd.merge(df, emb_df_subset, on="title_clean", how="left")
            df = df.drop(columns=["title_clean"])
            
            emb_dim = 384
            valid_emb = emb_df["embedding"].dropna().iloc[0] if not emb_df["embedding"].dropna().empty else None
            if valid_emb:
                try:
                    parsed_val = parse_embedding(valid_emb)
                    emb_dim = parsed_val.shape[0]
                except Exception:
                    pass
            
            zero_vec = [0.0] * emb_dim
            df["embedding"] = df["embedding"].apply(
                lambda x: parse_embedding(x) if pd.notna(x) else np.array(zero_vec, dtype=np.float32)
            )
        except Exception as e:
            print(f"Warning merging embeddings: {e}")
    else:
        print("Warning: Clean papers with embeddings file not found. Falling back to default embeddings.")

    contradictions = {}
    if os.path.exists(contradictions_path):
        try:
            with open(contradictions_path, "r", encoding="utf-8") as f:
                contradictions = json.load(f)
        except Exception as e:
            print(f"Warning reading contradictions: {e}")

    return df, contradictions


def preprocess_query(query: str) -> str:
    """Preprocess query to clean punctuation and correct common typos like 'metaformin'."""
    import difflib
    
    # Common domain vocabulary
    vocab = [
        "metformin", "breast", "cancer", "survival", "chemotherapy", "toxicity", 
        "synergy", "her2", "triple-negative", "rct", "cohort", "clinical", 
        "trial", "recurrence", "prevention", "diabetes", "insulin"
    ]
    
    words = query.split()
    corrected = []
    for w in words:
        clean = w.strip("?,.:;!\"'()").lower()
        if len(clean) > 4:
            matches = difflib.get_close_matches(clean, vocab, n=1, cutoff=0.7)
            if matches:
                corrected.append(matches[0])
                continue
        corrected.append(w)
    return " ".join(corrected)


def get_standard_rag_context(
    query: str,
    encoder_model: SentenceTransformer,
    ranked_df: pd.DataFrame,
    top_k: int = 3
) -> Tuple[str, List[Dict[str, Any]]]:
    """Retrieve top K papers based on vector similarity and format the context string."""
    corrected_query = preprocess_query(query)
    query_emb = encoder_model.encode([corrected_query], normalize_embeddings=True)[0]
    
    if "embedding" not in ranked_df.columns:
        # Fallback to top evidence score if embeddings are missing
        top_papers = ranked_df.sort_values(by="evidence_score", ascending=False).head(top_k)
        similarities = [0.0] * len(top_papers)
    else:
        emb_list = list(ranked_df["embedding"])
        embeddings_matrix = np.vstack(emb_list)
        similarities = (embeddings_matrix @ query_emb).astype(float)
        
        search_df = ranked_df.copy()
        search_df["similarity"] = similarities
        top_papers = search_df.sort_values(by="similarity", ascending=False).head(top_k)
        similarities = top_papers["similarity"].tolist()

    context_list = []
    sources = []
    
    for idx, (_, r) in enumerate(top_papers.iterrows(), 1):
        sample_size_str = str(int(r['sample_size'])) if ('sample_size' in r and r['sample_size'] > 0) else "N/A"
        design_str = r.get('study_design', 'Undetermined')
        sim_val = r.get('similarity', 0.0)
        
        context_list.append(
            f"[Source Paper {idx}]\n"
            f"Title: {r['title']}\n"
            f"Evidence Score: {r['evidence_score']}/10 | Design: {design_str} | Sample Size: {sample_size_str}\n"
            f"Abstract: {str(r['abstract'])}"
        )
        sources.append({
            "index": idx,
            "title": r['title'],
            "similarity": sim_val,
            "evidence_score": r['evidence_score'],
            "design": design_str,
            "sample_size": sample_size_str,
            "abstract": r['abstract']
        })

    context_str = "\n\n".join(context_list)
    return context_str, sources


def get_graph_rag_context(
    query: str,
    encoder_model: SentenceTransformer,
    ranked_df: pd.DataFrame,
    contradictions_dict: Dict[str, Any],
    top_k: int = 3
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve top K papers and traverse the contradictions graph to add related neighbors."""
    # 1. Start with Standard retrieval context
    standard_context, sources = get_standard_rag_context(query, encoder_model, ranked_df, top_k)
    
    retrieved_titles = [src["title"].strip().lower() for src in sources]
    
    # 2. Gather neighbor relations
    relations: List[Dict[str, Any]] = []
    
    # Scan contradictions, agreements, and partial agreements
    rel_lists = {
        "CONTRADICTION": contradictions_dict.get("contradictions", []),
        "AGREEMENT": contradictions_dict.get("agreements", []),
        "PARTIAL_AGREEMENT": contradictions_dict.get("partial_agreements", [])
    }
    
    visited_relationships = set()
    
    for rel_type, rel_list in rel_lists.items():
        for r in rel_list:
            title_a = r.get("claim_a_title", "").strip().lower()
            title_b = r.get("claim_b_title", "").strip().lower()
            
            # If relation matches any of our retrieved papers
            if title_a in retrieved_titles or title_b in retrieved_titles:
                # Deduplicate by sorting titles to form a unique key
                key = tuple(sorted([title_a, title_b]))
                if key in visited_relationships:
                    continue
                visited_relationships.add(key)
                
                relations.append({
                    "type": rel_type,
                    "claim_a_title": r.get("claim_a_title"),
                    "claim_a_text": r.get("claim_a_text"),
                    "claim_b_title": r.get("claim_b_title"),
                    "claim_b_text": r.get("claim_b_text"),
                    "explanation": r.get("explanation"),
                    "confidence": r.get("confidence", 1.0),
                    "weight": r.get("evidence_weight", 0.0)
                })

    # 3. Format Graph Context
    graph_context_list = [standard_context]
    
    if relations:
        graph_context_list.append("### GRAPH RELATIONSHIPS (CONNECTED CONFLICTS & CONSENSUS)")
        for idx, rel in enumerate(relations, 1):
            graph_context_list.append(
                f"[Graph Connection {idx} - {rel['type']}]\n"
                f"Paper A: {rel['claim_a_title']}\n"
                f"Claim A: {rel['claim_a_text']}\n"
                f"Paper B: {rel['claim_b_title']}\n"
                f"Claim B: {rel['claim_b_text']}\n"
                f"Relationship: {rel['type']} | Analyst Confidence: {rel['confidence']} | Avg Evidence Weight: {rel['weight']}\n"
                f"Explanation: {rel['explanation']}"
            )
            
    full_context_str = "\n\n".join(graph_context_list)
    return full_context_str, sources, relations


def generate_answer(prompt: str, model: str) -> Tuple[str, float]:
    """Execute LLM generation and measure time taken."""
    start_time = time.time()
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        ans = response["message"]["content"]
    except Exception as e:
        ans = f"Error calling Ollama: {e}"
    
    duration = time.time() - start_time
    return ans, duration
