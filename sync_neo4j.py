"""Synchronization tool to populate Neo4j with papers, claims, relationships, and entities."""
from __future__ import annotations

import os
import json
import hashlib
import logging
import argparse
from typing import Dict, List, Any
import pandas as pd
from pydantic import BaseModel

from src.core.neo4j_client import Neo4jClient
from src.shared.llm import chat as llm_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_neo4j")


class Entity(BaseModel):
    name: str
    type: str  # Chemical | Target | Disease | Symptom | Organism


class EntityRelation(BaseModel):
    entity_a: str
    predicate: str
    entity_b: str


class EntityExtractionOutput(BaseModel):
    entities: List[Entity]
    relations: List[EntityRelation]


def get_md5_hash(*args: str) -> str:
    """Generate a deterministic MD5 hash string from arguments."""
    hasher = hashlib.md5()
    for arg in args:
        hasher.update(str(arg).strip().lower().encode("utf-8"))
    return hasher.hexdigest()


def extract_entities_from_claim(claim_text: str, model: str) -> EntityExtractionOutput:
    """Query local LLM to extract entity-relationship triples from a claim."""
    prompt = f"""
    You are a biomedical expert parser. Read the biomedical claim below.
    Extract:
    1. A list of entities (Name, Type: Chemical, Target, Disease, Symptom, or Organism).
    2. A list of semantic relationships/interactions between those entities.
    
    Return ONLY a valid JSON object in this exact format:
    {{
      "entities": [
        {{"name": "<entity name>", "type": "<Chemical|Target|Disease|Symptom|Organism>"}}
      ],
      "relations": [
        {{"entity_a": "<entity name A>", "predicate": "<interacts with|inhibits|activates|causes|etc>", "entity_b": "<entity name B>"}}
      ]
    }}
    
    Claim: {claim_text}
    """.strip()
    
    try:
        resp = llm_chat(
            model,
            messages=[{"role": "user", "content": prompt}],
            task="extract",
            format=EntityExtractionOutput.model_json_schema()
        )
        content = resp["message"]["content"]
        return EntityExtractionOutput.model_validate_json(content)
    except Exception as e:
        logger.warning("Entity extraction failed for claim '%s': %s", claim_text, e)
        return EntityExtractionOutput(entities=[], relations=[])


def sync_database(
    ranked_path: str = "dataset/ranked_papers.csv",
    claims_path: str = "dataset/claims.csv",
    contradictions_path: str = "dataset/contradictions.json",
    model: str = "llama3.1:8b",
    skip_entities: bool = False,
    no_clear: bool = False,
):
    """Sync CSV and JSON dataset files to Neo4j graph database."""
    client = Neo4jClient()
    if not client.connect():
        logger.error("Could not connect to Neo4j instance. Please check your credentials.")
        return

    logger.info("Setting up constraints and indexes...")
    client.setup_constraints()

    if not no_clear:
        logger.info("Clearing database before sync...")
        client.clear_database()
    else:
        logger.info("Bypassing database clearing (incremental sync mode)")

    # 1. Ingest All Fetched Papers (Raw Collection)
    final_papers_path = "dataset/final_papers.csv"
    if os.path.exists(final_papers_path):
        logger.info("Loading all fetched papers from %s...", final_papers_path)
        df_final = pd.read_csv(final_papers_path)
        for _, row in df_final.iterrows():
            title = str(row.get("title", "")).strip()
            abstract = str(row.get("abstract", "")).strip()
            if not title:
                continue
            # Merge with default metrics
            client.ingest_paper(
                title=title,
                evidence_score=5.0,
                study_design="Undetermined",
                sample_size=0,
                abstract=abstract
            )
        logger.info("Successfully synced all %d fetched papers.", len(df_final))
    else:
        logger.warning("Final papers file not found: %s", final_papers_path)

    # 2. Ingest/Update Papers with Vector Embeddings
    embeddings_path = "dataset/clean_papers_with_embeddings.csv"
    if os.path.exists(embeddings_path):
        logger.info("Loading paper embeddings from %s...", embeddings_path)
        df_emb = pd.read_csv(embeddings_path)
        
        from src.core.graph_rag import parse_embedding
        
        count = 0
        for _, row in df_emb.iterrows():
            title = str(row.get("title", "")).strip()
            abstract = str(row.get("abstract", "")).strip()
            emb_val = row.get("embedding")
            if not title:
                continue
                
            parsed_emb = None
            if pd.notna(emb_val):
                try:
                    parsed_emb = parse_embedding(emb_val).tolist()
                except Exception as e:
                    logger.warning("Error parsing embedding for paper '%s': %s", title, e)
                    
            client.ingest_paper(
                title=title,
                evidence_score=5.0,
                study_design="Undetermined",
                sample_size=0,
                embedding=parsed_emb,
                abstract=abstract
            )
            count += 1
        logger.info("Successfully synced embeddings for %d papers.", count)
    else:
        logger.warning("Embeddings file not found: %s", embeddings_path)

    # 3. Update Papers with Evidence Scores and Study Designs
    if os.path.exists(ranked_path):
        logger.info("Loading ranked papers from %s to update metadata...", ranked_path)
        df_papers = pd.read_csv(ranked_path)
        
        # Ensure fallback column values
        if "evidence_score" not in df_papers.columns:
            df_papers["evidence_score"] = 5.0
        if "study_design" not in df_papers.columns:
            df_papers["study_design"] = "Undetermined"
        if "sample_size" not in df_papers.columns:
            df_papers["sample_size"] = 0
            
        for _, row in df_papers.iterrows():
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            client.ingest_paper(
                title=title,
                evidence_score=float(row.get("evidence_score", 5.0)),
                study_design=str(row.get("study_design", "Undetermined")),
                sample_size=int(row.get("sample_size", 0) if pd.notna(row.get("sample_size")) else 0)
            )
        logger.info("Successfully updated paper evidence metadata.")
    else:
        logger.warning("Ranked papers file not found: %s", ranked_path)


    # 2. Ingest Claims and Entities
    if os.path.exists(claims_path):
        logger.info("Loading claims from %s...", claims_path)
        df_claims = pd.read_csv(claims_path)
        
        for _, row in df_claims.iterrows():
            title = str(row.get("title", "")).strip()
            claim_text = str(row.get("claim", "")).strip()
            stance = str(row.get("stance", "neutral")).strip()
            if not claim_text or not title:
                continue
                
            claim_id = get_md5_hash(title, claim_text)
            client.ingest_claim(
                paper_title=title,
                claim_id=claim_id,
                claim_text=claim_text,
                stance=stance
            )
            
            # Extract and sync entities if enabled
            if not skip_entities:
                extracted = extract_entities_from_claim(claim_text, model)
                entity_map = {e.name.lower().strip(): e for e in extracted.entities}
                
                # Ingest each extracted relationship
                for rel in extracted.relations:
                    ent_a_key = rel.entity_a.lower().strip()
                    ent_b_key = rel.entity_b.lower().strip()
                    
                    ent_a = entity_map.get(ent_a_key)
                    ent_b = entity_map.get(ent_b_key)
                    
                    # Fallback to general type if not explicitly listed in entities
                    ent_a_type = ent_a.type if ent_a else "Chemical"
                    ent_b_type = ent_b.type if ent_b else "Target"
                    
                    client.ingest_entity_and_interaction(
                        claim_id=claim_id,
                        entity_a_name=rel.entity_a,
                        entity_a_type=ent_a_type,
                        entity_b_name=rel.entity_b,
                        entity_b_type=ent_b_type,
                        predicate=rel.predicate,
                        paper_title=title
                    )
        logger.info("Successfully synced claims and entities.")
    else:
        logger.warning("Claims file not found: %s", claims_path)

    # 3. Ingest Claim-to-Claim Contradiction/Agreement Relationships
    if os.path.exists(contradictions_path):
        logger.info("Loading contradictions graph from %s...", contradictions_path)
        try:
            with open(contradictions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            rel_lists = {
                "CONTRADICTS": data.get("contradictions", []),
                "AGREES": data.get("agreements", []),
                "PARTIAL_AGREES": data.get("partial_agreements", [])
            }
            
            count = 0
            for rel_name, rel_list in rel_lists.items():
                for item in rel_list:
                    title_a = item.get("claim_a_title", "")
                    text_a = item.get("claim_a_text", "")
                    title_b = item.get("claim_b_title", "")
                    text_b = item.get("claim_b_text", "")
                    
                    if not title_a or not text_a or not title_b or not text_b:
                        continue
                        
                    claim_a_id = get_md5_hash(title_a, text_a)
                    claim_b_id = get_md5_hash(title_b, text_b)
                    
                    client.ingest_claim_relationship(
                        claim_a_id=claim_a_id,
                        claim_b_id=claim_b_id,
                        relationship_type=rel_name,
                        confidence=float(item.get("confidence", 1.0)),
                        explanation=str(item.get("explanation", "")),
                        weight=float(item.get("evidence_weight", 0.0))
                    )
                    count += 1
            logger.info("Successfully synced %d claim relationships.", count)
        except Exception as e:
            logger.error("Error reading contradictions file: %s", e)
    else:
        logger.warning("Contradictions file not found: %s", contradictions_path)

    client.close()
    logger.info("Neo4j database synchronization finished successfully.")


def main():
    parser = argparse.ArgumentParser(description="Synchronize Griffin dataset to Neo4j graph database")
    parser.add_argument("--ranked-papers", default="dataset/ranked_papers.csv")
    parser.add_argument("--claims", default="dataset/claims.csv")
    parser.add_argument("--contradictions", default="dataset/contradictions.json")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model for entity extraction")
    parser.add_argument("--skip-entities", action="store_true", help="Skip LLM-based entity-relationship extraction")
    parser.add_argument("--no-clear", action="store_true", help="Bypass database clearing (incremental sync)")
    
    args = parser.parse_args()
    sync_database(
        ranked_path=args.ranked_papers,
        claims_path=args.claims,
        contradictions_path=args.contradictions,
        model=args.model,
        skip_entities=args.skip_entities,
        no_clear=args.no_clear
    )


if __name__ == "__main__":
    main()
