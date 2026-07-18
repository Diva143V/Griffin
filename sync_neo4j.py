"""Synchronization tool to populate Neo4j with papers, claims, relationships, and entities."""
from __future__ import annotations

import os
import json
import hashlib
import logging
import argparse
from typing import Dict, List, Any, Tuple
import pandas as pd
from pydantic import BaseModel

from src.core.neo4j_client import Neo4jClient
from src.shared.llm import chat as llm_chat
from src.shared.config import (
    RANKED_PAPERS_PATH,
    CLAIMS_PATH,
    CONTRADICTIONS_PATH,
    FINAL_PAPERS_PATH,
    EMBEDDINGS_PATH,
    EXECUTION_TRACE_PATH,
    LAST_RESEARCH_GOAL_PATH,
    LLM_REPORTS_MAPPING
)

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
    ranked_path: str = RANKED_PAPERS_PATH,
    claims_path: str = CLAIMS_PATH,
    contradictions_path: str = CONTRADICTIONS_PATH,
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

    client.close()
    logger.info("Neo4j database synchronization finished successfully.")


def sync_reports(client: Neo4jClient, query_text: str, model: str, skip_reports: bool = False):
    """Scan dataset directory for reports and sync them with query and paper reference links."""
    if skip_reports:
        logger.info("Bypassing reports synchronization (skip_reports=True)")
        return

    # Map reports to agent names and types
    report_mapping = LLM_REPORTS_MAPPING

    import datetime
    timestamp = datetime.datetime.now().isoformat()

    # Find all papers to match paper titles in report text
    # We will search case-insensitively for paper titles
    papers = []
    try:
        if os.path.exists(RANKED_PAPERS_PATH):
            df = pd.read_csv(RANKED_PAPERS_PATH)
            papers = df["title"].dropna().tolist()
        elif os.path.exists(FINAL_PAPERS_PATH):
            df = pd.read_csv(FINAL_PAPERS_PATH)
            papers = df["title"].dropna().tolist()
    except Exception as e:
        logger.warning("Could not read paper list for reference matching: %s", e)

    for filename, (report_type, agent) in report_mapping.items():
        filepath = os.path.join("dataset", filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Ingest the report
                client.ingest_report(
                    query_text=query_text,
                    report_type=report_type,
                    content=content,
                    agent=agent,
                    model=model,
                    timestamp=timestamp,
                )
                logger.info("Successfully synced report: %s", filename)

                # Find references to papers
                ref_count = 0
                for paper_title in papers:
                    title_clean = paper_title.strip()
                    if not title_clean or len(title_clean) < 15:
                        continue
                    # Simple substring match (case insensitive)
                    if title_clean.lower() in content.lower():
                        client.ingest_report_paper_link(
                            query_text=query_text,
                            report_type=report_type,
                            paper_title=title_clean,
                        )
                        ref_count += 1
                if ref_count > 0:
                    logger.info("Found %d paper references in report %s", ref_count, filename)

            except Exception as e:
                logger.error("Error syncing report %s: %s", filename, e)


def sync_database(
    ranked_path: str = RANKED_PAPERS_PATH,
    claims_path: str = CLAIMS_PATH,
    contradictions_path: str = CONTRADICTIONS_PATH,
    model: str = "llama3.1:8b",
    skip_entities: bool = False,
    clear_db: bool = False,
    skip_reports: bool = False,
):
    """Sync CSV, JSON dataset files, reports and query execution trace to Neo4j graph database."""
    client = Neo4jClient()
    if not client.connect():
        logger.error("Could not connect to Neo4j instance. Please check your credentials.")
        return

    logger.info("Setting up constraints and indexes...")
    client.setup_constraints()

    if clear_db:
        logger.info("Clearing database before sync...")
        client.clear_database()
    else:
        logger.info("Bypassing database clearing (incremental sync mode)")

    # Retrieve query metadata from execution trace or default
    query_text = "Piles and its treatments"  # fallback default
    intent = "general_research_question"
    route = "standard_rag"
    timestamp = ""
    trace_model = model

    trace_path = EXECUTION_TRACE_PATH
    if os.path.exists(trace_path):
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                trace = json.load(f)
            plan = trace.get("plan", {})
            query_text = plan.get("query", query_text)
            intent = plan.get("intent", intent)
            route = plan.get("route", route)
            trace_model = plan.get("model", trace_model)
            import datetime
            timestamp = datetime.datetime.now().isoformat()
        except Exception as e:
            logger.warning("Error reading execution trace: %s", e)
    elif os.path.exists(LAST_RESEARCH_GOAL_PATH):
        try:
            with open(LAST_RESEARCH_GOAL_PATH, "r", encoding="utf-8") as f:
                query_text = f.read().strip()
        except Exception:
            pass

    # Ingest the starting Query node
    logger.info("Ingesting starting Query node: '%s'...", query_text)
    import datetime
    if not timestamp:
        timestamp = datetime.datetime.now().isoformat()
    client.ingest_query(
        text=query_text,
        intent=intent,
        route=route,
        model=trace_model,
        timestamp=timestamp,
    )

    # 1. Ingest All Fetched Papers (Raw Collection)
    final_papers_path = FINAL_PAPERS_PATH
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
    embeddings_path = EMBEDDINGS_PATH
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

    # 4. Ingest Reports (Synthesis, Consensus, clinical, methodology, etc.)
    sync_reports(client, query_text, trace_model, skip_reports)

    client.close()
    logger.info("Neo4j database synchronization finished successfully.")


def main():
    parser = argparse.ArgumentParser(description="Synchronize Griffin dataset to Neo4j graph database")
    run_dir = os.environ.get("GRIFFIN_RUN_DIR", "dataset")
    parser.add_argument("--ranked-papers", default=os.path.join(run_dir, "ranked_papers.csv"))
    parser.add_argument("--claims", default=os.path.join(run_dir, "claims.csv"))
    parser.add_argument("--contradictions", default=os.path.join(run_dir, "contradictions.json"))
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model for entity extraction")
    parser.add_argument("--skip-entities", action="store_true", help="Skip LLM-based entity-relationship extraction")
    parser.add_argument("--clear", action="store_true", help="Clear the database before syncing")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear the database (incremental sync)")
    parser.add_argument("--skip-reports", action="store_true", help="Skip LLM-generated reports synchronization")
    
    args = parser.parse_args()
    clear_db = args.clear and not args.no_clear
    sync_database(
        ranked_path=args.ranked_papers,
        claims_path=args.claims,
        contradictions_path=args.contradictions,
        model=args.model,
        skip_entities=args.skip_entities,
        clear_db=clear_db,
        skip_reports=args.skip_reports,
    )


if __name__ == "__main__":
    main()
