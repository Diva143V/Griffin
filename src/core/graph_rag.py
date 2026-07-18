"""Core RAG engine implementing both Standard (vector similarity) and Graph (relationship traversal) RAG."""
from __future__ import annotations

import ast
import json
import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from ..shared.llm import chat as llm_chat
from ..shared.config import (
    RANKED_PAPERS_PATH,
    EMBEDDINGS_PATH,
    CONTRADICTIONS_PATH
)

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


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
    ranked_path: str = RANKED_PAPERS_PATH,
    embeddings_path: str = EMBEDDINGS_PATH,
    contradictions_path: str = CONTRADICTIONS_PATH
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


def get_standard_rag_context(
    query: str,
    encoder_model: SentenceTransformer,
    ranked_df: pd.DataFrame,
    similarity_threshold: float = 0.60,
    max_papers: int = 8,
    neo4j_client: Optional[Any] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """Dynamically retrieve papers based on semantic threshold and sort by evidence score quality (Neo4j native vector index or local fallback)."""
    if neo4j_client and neo4j_client.verify_connection():
        try:
            logger.info("Using Neo4j Native Vector Index for RAG retrieval...")
            query_emb = encoder_model.encode([query], normalize_embeddings=True)[0].tolist()
            # Retrieve similar nodes directly from Neo4j index
            similar_papers = neo4j_client.query_vector_similar_papers(query_vector=query_emb, top_k=max_papers)
            
            context_list = []
            sources = []
            
            for idx, r in enumerate(similar_papers, 1):
                sample_size_val = r.get('sample_size', 0)
                sample_size_str = str(int(sample_size_val)) if (pd.notna(sample_size_val) and sample_size_val > 0) else "N/A"
                design_str = r.get('study_design', 'Undetermined')
                sim_val = r.get('score', 0.0)
                
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
        except Exception as e:
            logger.error("Neo4j vector search failed, falling back to local file traversal: %s", e)

    # Local fallback logic
    ranked_df = ranked_df.copy()
    if "evidence_score" not in ranked_df.columns:
        ranked_df["evidence_score"] = 5.0
    if "sample_size" not in ranked_df.columns:
        ranked_df["sample_size"] = 0
    if "study_design" not in ranked_df.columns:
        ranked_df["study_design"] = "Undetermined"
        
    query_emb = encoder_model.encode([query], normalize_embeddings=True)[0]
    
    if "embedding" not in ranked_df.columns:
        # Fallback to top evidence score if embeddings are missing
        top_papers = ranked_df.sort_values(by="evidence_score", ascending=False).head(3)
        similarities = [0.0] * len(top_papers)
    else:
        emb_list = list(ranked_df["embedding"])
        embeddings_matrix = np.vstack(emb_list)
        similarities = (embeddings_matrix @ query_emb).astype(float)
        
        search_df = ranked_df.copy()
        search_df["similarity"] = similarities
        
        # Calculate hybrid keyword match boost (0.05 per title match, 0.02 per abstract match)
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        boosts = []
        for _, r in search_df.iterrows():
            title_text = str(r.get("title", "")).lower()
            abstract_text = str(r.get("abstract", "")).lower()
            matches = sum(1 for w in query_words if w in title_text) * 0.05 + sum(1 for w in query_words if w in abstract_text) * 0.02
            boosts.append(matches)
        
        # Hybrid Score = Dense Vector Similarity + Sparse Keyword Matches
        search_df["hybrid_score"] = search_df["similarity"] + boosts
        
        # Dynamic filtering: keep only papers above threshold based on hybrid score
        relevant_df = search_df[search_df["hybrid_score"] >= similarity_threshold]
        
        # If no papers meet the threshold, fall back to top 3 closest matches
        if relevant_df.empty:
            top_papers = search_df.sort_values(by="hybrid_score", ascending=False).head(3)
        else:
            # Sort the relevant papers by evidence quality score (highest first)
            top_papers = relevant_df.sort_values(by="evidence_score", ascending=False).head(max_papers)
            
        similarities = top_papers["similarity"].tolist()

    context_list = []
    sources = []
    
    for idx, (_, r) in enumerate(top_papers.iterrows(), 1):
        sample_size_val = r.get('sample_size', 0)
        sample_size_str = str(int(sample_size_val)) if (pd.notna(sample_size_val) and sample_size_val > 0) else "N/A"
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
    similarity_threshold: float = 0.60,
    max_papers: int = 8,
    neo4j_client: Optional[Any] = None,
    use_tog: bool = False
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve papers matching semantic threshold, sort by evidence score, and traverse contradiction graph (Neo4j or local JSON)."""
    # 1. Check if we should use iterative Think-on-Graph (ToG) search
    if use_tog and neo4j_client and neo4j_client.verify_connection():
        try:
            logger.info("Initializing iterative Think-on-Graph (ToG) reasoning loop...")
            from ..agents.tog_agent import ThinkOnGraphAgent
            tog_agent = ThinkOnGraphAgent(client=neo4j_client)
            
            # Execute the ToG explorer agent
            tog_history, sources = tog_agent.run_tog(query=query, max_hops=3, beam_width=2)
            
            # Fetch contradiction relationships among claims connected to the visited papers
            retrieved_titles = [src["title"].strip() for src in sources]
            relations: List[Dict[str, Any]] = []
            
            cypher_claims = """
            MATCH (p:Paper)-[:EXTRACTED_CLAIM]->(c:Claim)
            WHERE p.title IN $retrieved_titles
            MATCH (c)-[r:CONTRADICTS|AGREES|PARTIAL_AGREES]-(other:Claim)
            RETURN type(r) AS rel_type,
                   c.claim_text AS claim_a_text,
                   p.title AS claim_a_title,
                   other.claim_text AS claim_b_text,
                   [(other_paper:Paper)-[:EXTRACTED_CLAIM]->(other) | other_paper.title][0] AS claim_b_title,
                   r.explanation AS explanation,
                   r.confidence AS confidence,
                   r.weight AS weight
            """
            records = neo4j_client.query_graph(cypher_claims, {"retrieved_titles": retrieved_titles})
            visited_relationships = set()
            for rec in records:
                title_a = rec.get("claim_a_title", "").strip().lower()
                title_b = rec.get("claim_b_title", "").strip().lower()
                key = tuple(sorted([title_a, title_b]))
                if key in visited_relationships:
                    continue
                visited_relationships.add(key)
                relations.append({
                    "type": rec.get("rel_type"),
                    "claim_a_title": rec.get("claim_a_title"),
                    "claim_a_text": rec.get("claim_a_text"),
                    "claim_b_title": rec.get("claim_b_title"),
                    "claim_b_text": rec.get("claim_b_text"),
                    "explanation": rec.get("explanation"),
                    "confidence": rec.get("confidence", 1.0),
                    "weight": rec.get("weight", 0.0)
                })
                
            # Query Entity-to-Entity interactions for visited papers
            entities_context = ""
            cypher_entities = """
            MATCH (p:Paper)-[:EXTRACTED_CLAIM]->(c:Claim)-[:MENTIONS]->(e1:Entity)-[r:INTERACTS_WITH]->(e2:Entity)
            WHERE p.title IN $retrieved_titles
            RETURN e1.name AS entity_a,
                   e1.type AS type_a,
                   e2.name AS entity_b,
                   e2.type AS type_b,
                   r.predicate AS predicate,
                   r.paper_title AS paper_title
            """
            ent_records = neo4j_client.query_graph(cypher_entities, {"retrieved_titles": retrieved_titles})
            if ent_records:
                lines = ["### GRAPH BIOMEDICAL ENTITIES & INTERACTIONS"]
                for e_rec in ent_records:
                    lines.append(
                        f"- [{e_rec['type_a']}] {e_rec['entity_a']} --[{e_rec['predicate']}]--> [{e_rec['type_b']}] {e_rec['entity_b']} (from Paper: {e_rec['paper_title']})"
                    )
                entities_context = "\n".join(lines)
            
            # Format the standard references
            standard_context_list = []
            for src in sources:
                sample_size_str = str(int(src["sample_size"])) if (pd.notna(src["sample_size"]) and src["sample_size"] > 0) else "N/A"
                standard_context_list.append(
                    f"[Source Paper {src['index']}]\n"
                    f"Title: {src['title']}\n"
                    f"Evidence Score: {src['evidence_score']}/10 | Design: {src['design']} | Sample Size: {sample_size_str}\n"
                    f"Abstract: {src['abstract']}"
                )
            
            full_context_parts = [
                "\n\n".join(standard_context_list),
                "### THINK-ON-GRAPH (ToG) REASONING PATHWAY EXPLORATION",
                tog_history
            ]
            
            if relations:
                full_context_parts.append("### CONNECTED CONFLICTS & CONSENSUS RELATIONSHIPS")
                for idx, rel in enumerate(relations, 1):
                    full_context_parts.append(
                        f"[Connection {idx} - {rel['type']}]\n"
                        f"Paper A: {rel['claim_a_title']}\n"
                        f"Claim A: {rel['claim_a_text']}\n"
                        f"Paper B: {rel['claim_b_title']}\n"
                        f"Claim B: {rel['claim_b_text']}\n"
                        f"Relationship: {rel['type']} | Analyst Confidence: {rel['confidence']} | Avg Evidence Weight: {rel['weight']}\n"
                        f"Explanation: {rel['explanation']}"
                    )
            
            if entities_context:
                full_context_parts.append(entities_context)
                
            full_context_str = "\n\n".join(full_context_parts)
            return full_context_str, sources, relations
        except Exception as e:
            logger.error("ToG iterative search failed, falling back to standard graph search: %s", e)

    # 2. Start with Standard retrieval context (Fallback)
    standard_context, sources = get_standard_rag_context(
        query, encoder_model, ranked_df, similarity_threshold, max_papers, neo4j_client=neo4j_client
    )
    
    retrieved_titles = [src["title"].strip() for src in sources]
    retrieved_titles_lower = [t.lower() for t in retrieved_titles]
    
    relations: List[Dict[str, Any]] = []
    entities_context = ""
    
    # 2. Query Neo4j if available and active
    if neo4j_client and neo4j_client.verify_connection():
        try:
            logger.info("Querying Neo4j Graph Database for relationships...")
            # Query Claim-to-Claim relationships
            cypher_claims = """
            MATCH (p:Paper)-[:EXTRACTED_CLAIM]->(c:Claim)
            WHERE p.title IN $retrieved_titles
            MATCH (c)-[r:CONTRADICTS|AGREES|PARTIAL_AGREES]-(other:Claim)
            RETURN type(r) AS rel_type,
                   c.claim_text AS claim_a_text,
                   p.title AS claim_a_title,
                   other.claim_text AS claim_b_text,
                   [(other_paper:Paper)-[:EXTRACTED_CLAIM]->(other) | other_paper.title][0] AS claim_b_title,
                   r.explanation AS explanation,
                   r.confidence AS confidence,
                   r.weight AS weight
            """
            records = neo4j_client.query_graph(cypher_claims, {"retrieved_titles": retrieved_titles})
            visited_relationships = set()
            for rec in records:
                title_a = rec.get("claim_a_title", "").strip().lower()
                title_b = rec.get("claim_b_title", "").strip().lower()
                key = tuple(sorted([title_a, title_b]))
                if key in visited_relationships:
                    continue
                visited_relationships.add(key)
                relations.append({
                    "type": rec.get("rel_type"),
                    "claim_a_title": rec.get("claim_a_title"),
                    "claim_a_text": rec.get("claim_a_text"),
                    "claim_b_title": rec.get("claim_b_title"),
                    "claim_b_text": rec.get("claim_b_text"),
                    "explanation": rec.get("explanation"),
                    "confidence": rec.get("confidence", 1.0),
                    "weight": rec.get("weight", 0.0)
                })
                
            # Query Entity-to-Entity interactions
            cypher_entities = """
            MATCH (p:Paper)-[:EXTRACTED_CLAIM]->(c:Claim)-[:MENTIONS]->(e1:Entity)-[r:INTERACTS_WITH]->(e2:Entity)
            WHERE p.title IN $retrieved_titles
            RETURN e1.name AS entity_a,
                   e1.type AS type_a,
                   e2.name AS entity_b,
                   e2.type AS type_b,
                   r.predicate AS predicate,
                   r.paper_title AS paper_title
            """
            ent_records = neo4j_client.query_graph(cypher_entities, {"retrieved_titles": retrieved_titles})
            if ent_records:
                lines = ["### GRAPH BIOMEDICAL ENTITIES & INTERACTIONS"]
                for e_rec in ent_records:
                    lines.append(
                        f"- [{e_rec['type_a']}] {e_rec['entity_a']} --[{e_rec['predicate']}]--> [{e_rec['type_b']}] {e_rec['entity_b']} (from Paper: {e_rec['paper_title']})"
                    )
                entities_context = "\n".join(lines)
        except Exception as e:
            logger.error("Error querying Neo4j. Falling back to local JSON: %s", e)
            neo4j_client = None

    # Fallback to JSON-based relationship dictionary traversal
    if not neo4j_client or not relations:
        visited_relationships = set()
        rel_lists = {
            "CONTRADICTS": contradictions_dict.get("contradictions", []),
            "AGREES": contradictions_dict.get("agreements", []),
            "PARTIAL_AGREES": contradictions_dict.get("partial_agreements", [])
        }
        for rel_type, rel_list in rel_lists.items():
            for r in rel_list:
                title_a = r.get("claim_a_title", "").strip().lower()
                title_b = r.get("claim_b_title", "").strip().lower()
                if title_a in retrieved_titles_lower or title_b in retrieved_titles_lower:
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
            
    if entities_context:
        graph_context_list.append(entities_context)
        
    full_context_str = "\n\n".join(graph_context_list)
    return full_context_str, sources, relations


def generate_answer(prompt: str, model: str) -> Tuple[str, float]:
    """Execute LLM generation and measure time taken."""
    start_time = time.time()
    try:
        response = llm_chat(
            model,
            messages=[{"role": "user", "content": prompt}],
            task="synthesis",
        )
        ans = response["message"]["content"]
    except Exception as e:
        logger.error("Failed to generate answer: %s", e)
        ans = f"Error generating answer: {e}"
    
    duration = time.time() - start_time
    return ans, duration
