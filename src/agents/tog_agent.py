"""Think-on-Graph (ToG) reasoning agent with Weight-Aware Path Ranking and Active Self-Healing Retrieval."""
from __future__ import annotations

import json
import logging
import re
import os
import sys
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from ..shared.llm import chat as llm_chat
from ..core.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


def trigger_self_healing_retrieval(term_a: str, term_b: str, model: str = "llama3.1:8b") -> bool:
    """Invokes the paper collection, ranking, extraction, and sync pipeline for a missing link.
    
    Reads ENTREZ_EMAIL from environment. Returns False if the email is not set.
    """
    search_query = f"{term_a} {term_b}"
    logger.info("Self-Healing: Triggering active collection for '%s'...", search_query)
    
    python_exe = sys.executable
    run_dir = os.environ.get("GRIFFIN_RUN_DIR", "dataset")
    email = os.environ.get("ENTREZ_EMAIL", "")
    if not email:
        logger.error("Self-healing aborted: ENTREZ_EMAIL environment variable is not set.")
        return False
    
    # Run the collector pipeline steps incrementally
    steps = [
        [python_exe, "build_dataset.py", "--query", search_query, "--max-results", "10", "--run-filter", "--email", email],
        [python_exe, "generate_embeddings.py", "--input", os.path.join(run_dir, "clean_papers.csv"), "--output", os.path.join(run_dir, "clean_papers_with_embeddings.csv"), "--include-title"],
        [python_exe, "-m", "src.core.evidence_ranker"],
        [python_exe, "-m", "src.core.claim_extractor", "--input", os.path.join(run_dir, "clean_papers.csv"), "--output", os.path.join(run_dir, "claims.csv"), "--limit", "10", "--model", model],
        [python_exe, "-m", "src.core.contradiction_detector", "--max-pairs", "10", "--model", model],
        # Run sync_neo4j in incremental mode so it doesn't delete existing data!
        [python_exe, "sync_neo4j.py", "--model", model, "--no-clear"]
    ]
    
    env = os.environ.copy()
    env["GRIFFIN_RUN_DIR"] = run_dir
    
    for cmd in steps:
        try:
            logger.info("Executing self-healing step: %s", " ".join(cmd))
            # Set timeout to 120 seconds to prevent hanging subprocesses
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120, env=env)
            logger.info("Step completed successfully.")
        except subprocess.TimeoutExpired:
            logger.error("Self-healing step timed out: %s", " ".join(cmd))
            return False
        except subprocess.CalledProcessError as e:
            logger.error("Self-healing step failed: %s. Output: %s. Stderr: %s", " ".join(cmd), e.stdout, e.stderr)
            return False
            
    return True


def extract_starting_entities(query: str, client: Neo4jClient, model: str = "llama3.1:8b") -> List[str]:
    """Identify potential starting entities (drugs, targets, diseases) in the query using LLM + regex fallback."""
    entities = []
    prompt = f"""
    You are a biomedical taxonomy extractor. Identify the primary chemical, drug, target gene, protein, or disease entities mentioned in the following user query:
    "{query}"

    Extract them as a JSON list of strings, using standard scientific names if possible (e.g., ["Metformin", "AMPK", "Breast Cancer", "SIRT1"]).
    Only return valid JSON. Do not include markdown wraps or explanations.
    """
    try:
        response = llm_chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            task="extract"
        )
        content = response["message"]["content"].strip()
        if "```" in content:
            content = re.sub(r"```[a-zA-Z]*", "", content).strip()
            content = content.replace("```", "").strip()
            
        parsed = json.loads(content)
        if isinstance(parsed, list):
            entities.extend(str(item).strip() for item in parsed)
    except Exception as e:
        logger.warning("Failed to extract start entities via LLM: %s", e)

    # Regex fallback: capture uppercase acronyms/genes (e.g. SIRT1, GLP-1, AMPK, mTOR)
    pattern = r'\b[A-Za-z0-9\-]{3,15}\b'
    common_words = {"does", "with", "that", "this", "from", "have", "been", "were", "ther", "cancer", "breast", "treat"}
    for match in re.finditer(pattern, query):
        term = match.group(0).strip()
        term_lower = term.lower()
        
        # Check if it has uppercase letters or numbers (like SIRT1, AMPK, GLP-1) and is not a common stopword
        if term_lower not in common_words and len(term) >= 3:
            # If it's mixed case/uppercase or contains a digit, it's highly likely to be a gene/protein
            if any(c.isupper() for c in term) or any(c.isdigit() for c in term):
                if term not in entities and term_lower not in [e.lower() for e in entities]:
                    entities.append(term)
            # Add metformin specifically
            elif term_lower == "metformin" and term not in entities and "metformin" not in [e.lower() for e in entities]:
                entities.append(term)

    # Verify if any of these entities actually exist in the database (fuzzy match)
    verified_entities = []
    for ent in entities:
        ent_clean = str(ent).strip()
        check_query = """
        MATCH (n)
        WHERE n.name = $val OR n.title = $val OR n.id = $val
        RETURN count(n) AS cnt
        """
        res = client.query_graph(check_query, {"val": ent_clean})
        if res and res[0]["cnt"] > 0:
            verified_entities.append(ent_clean)
        else:
            # Try case-insensitive lookup
            check_query_lower = """
            MATCH (n)
            WHERE toLower(n.name) = toLower($val) 
               OR toLower(n.title) = toLower($val) 
               OR toLower(n.id) = toLower($val)
            RETURN coalesce(n.name, n.title, n.id) AS matched_name
            LIMIT 1
            """
            res_lower = client.query_graph(check_query_lower, {"val": ent_clean})
            if res_lower:
                verified_entities.append(res_lower[0]["matched_name"])
            else:
                # If completely missing from database, keep it so it triggers self-healing!
                verified_entities.append(ent_clean)
    
    # Dynamic fallback: If no entities were found or matched, use query keywords instead of hardcoded 'Metformin'
    if not verified_entities:
        query_words = [
            w.strip().capitalize() for w in re.split(r'\W+', query)
            if len(w.strip()) > 3 and w.lower() not in common_words
        ]
        if query_words:
            verified_entities.extend(query_words[:3])

    return list(set(verified_entities)) if verified_entities else ["Metformin"]


def explore_neighbors(active_node: str, client: Neo4jClient) -> List[Dict[str, Any]]:
    """Retrieve neighboring nodes and relationships, including confidence/weight properties."""
    query = """
    MATCH (n)
    WHERE n.name = $val OR n.title = $val OR n.id = $val
    MATCH (n)-[r]-(m)
    RETURN labels(n) as n_labels,
           coalesce(n.name, n.title, n.id) as n_identifier,
           type(r) as rel_type,
           r.predicate as predicate,
           r.explanation as explanation,
           r.confidence as confidence,
           r.weight as weight,
           labels(m) as m_labels,
           coalesce(m.name, m.title, m.id) as m_identifier
    ORDER BY coalesce(r.weight, 0) DESC, coalesce(r.confidence, 0) DESC
    LIMIT 100
    """
    try:
        return client.query_graph(query, {"val": active_node})
    except Exception as e:
        logger.error("Failed to query neighbors for '%s': %s", active_node, e)
        return []


class ThinkOnGraphAgent:
    """Implements weight-aware path search and active self-healing retrieval on Neo4j."""

    def __init__(self, client: Neo4jClient, model: str = "llama3.1:8b"):
        self.client = client
        self.model = model

    def run_tog(
        self,
        query: str,
        max_hops: int = 3,
        beam_width: int = 2
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Runs the weight-aware ToG reasoning loop with self-healing hooks."""
        if not self.client.verify_connection():
            return "Neo4j is not connected. Skipping Think-on-Graph reasoning.", []

        # 1. Extract starting nodes using the configured model
        raw_entities = extract_starting_entities(query, self.client, model=self.model)
        
        # Determine fallback default if completely empty
        if not raw_entities:
            # Try to grab query keywords as dynamic default fallback
            query_words = [
                w.strip().capitalize() for w in re.split(r'\W+', query)
                if len(w.strip()) > 3
            ]
            raw_entities = query_words[:3] if query_words else ["Metformin"]

        traversal_history: List[str] = []
        traversal_history.append(f"### Think-on-Graph (ToG) Traversal Initialization\n- **Extracted Query Entities**: {', '.join([f'`{n}`' for n in raw_entities])}")

        # --- Self-Healing Missing Link Check ---
        missing_entities = []
        for ent in raw_entities:
            check_q = "MATCH (n) WHERE n.name = $val OR n.title = $val OR n.id = $val RETURN count(n) AS cnt"
            res = self.client.query_graph(check_q, {"val": ent})
            if not res or res[0]["cnt"] == 0:
                missing_entities.append(ent)

        if missing_entities:
            known_entities = [e for e in raw_entities if e not in missing_entities]
            primary_known = known_entities[0] if known_entities else "Metformin"
            
            for missing in missing_entities:
                logger.info("Self-healing: Node '%s' is missing. Triggering active collector loop...", missing)
                traversal_history.append(f"- **Self-Healing Active**: Node `{missing}` was missing from the knowledge base. Triggering live PubMed/PMC collection for `'{primary_known} {missing}'`...")
                
                success = trigger_self_healing_retrieval(primary_known, missing, model=self.model)
                if success:
                    traversal_history.append(f"  * Dynamic ingestion completed successfully! Connected nodes for `{missing}` synced to Neo4j.")
                else:
                    traversal_history.append(f"  * Dynamic ingestion returned no results for `{missing}`. Traversal will proceed with existing nodes.")
            
            # Re-extract starting nodes after healing
            active_nodes = extract_starting_entities(query, self.client, model=self.model)
            if not active_nodes:
                active_nodes = raw_entities
        else:
            active_nodes = raw_entities

        traversal_history.append(f"- **Starting Nodes**: {', '.join([f'`{n}`' for n in active_nodes])}")
        
        visited = set(active_nodes)
        all_referenced_papers = []

        # 2. Iterate graph exploration hops
        for hop in range(1, max_hops + 1):
            traversal_history.append(f"\n#### Hop {hop} Exploration")
            
            neighbors_pool: Dict[str, Dict[str, Any]] = {}
            for node in active_nodes:
                neighbors = explore_neighbors(node, self.client)
                for rec in neighbors:
                    m_val = rec.get("m_identifier")
                    if m_val and m_val not in visited:
                        rel_desc = rec.get("rel_type")
                        if rec.get("predicate"):
                            rel_desc = f"{rel_desc} ({rec.get('predicate')})"
                        
                        neighbors_pool[m_val] = {
                            "neighbor": m_val,
                            "label": rec.get("m_labels", ["Node"])[0],
                            "parent": rec.get("n_identifier"),
                            "relationship": rel_desc,
                            "explanation": rec.get("explanation", ""),
                            "confidence": rec.get("confidence"),
                            "weight": rec.get("weight")
                        }
            
            if not neighbors_pool:
                traversal_history.append("- *No new neighbors found. Terminating path traversal.*")
                break

            # Format neighbors with weight-aware metrics for the LLM
            neighbors_list = list(neighbors_pool.values())
            formatted_neighbors = []
            for idx, n in enumerate(neighbors_list, 1):
                metric_parts = []
                if n.get("confidence") is not None:
                    metric_parts.append(f"Confidence: {n['confidence']:.2f}")
                if n.get("weight") is not None:
                    metric_parts.append(f"Weight/Consensus: {n['weight']:.2f}")
                metrics_str = f" ({', '.join(metric_parts)})" if metric_parts else ""
                
                formatted_neighbors.append(
                    f"{idx}. Node: `{n['neighbor']}` (Type: {n['label']})\n"
                    f"   Connected to: `{n['parent']}` via relationship `{n['relationship']}`{metrics_str}\n"
                    f"   Explanation: {n['explanation']}"
                )
            
            neighbors_str = "\n".join(formatted_neighbors)
            active_nodes_str = ", ".join([f"`{n}`" for n in active_nodes])
            
            prompt = f"""
            You are a Think-on-Graph reasoning agent. Our research goal is:
            "{query}"

            We are currently positioned at nodes: {active_nodes_str}
            We found the following neighboring nodes in the knowledge graph:
            
            {neighbors_str}

            Select the top {beam_width} most promising neighbor nodes to explore next that help solve the research goal.
            Give preference to connections that have higher Confidence scores and Weight/Consensus ratings.

            Format your response as a JSON array of objects. Do not include markdown codeblocks or explanations outside the JSON array:
            [
              {{
                "node": "Name of Node", 
                "reason": "Brief scientific reason why this node is relevant, mentioning its weight/evidence strength if appropriate"
              }}
            ]
            """
            
            try:
                response = llm_chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    task="route"
                )
                content = response["message"]["content"].strip()
                if "```" in content:
                    content = re.sub(r"```[a-zA-Z]*", "", content).strip()
                    content = content.replace("```", "").strip()
                
                selections = json.loads(content)
                next_nodes = []
                
                if isinstance(selections, list):
                    traversal_history.append("- **Traversed Paths chosen by LLM (Weight-Aware)**:")
                    for sel in selections:
                        node_name = sel.get("node")
                        reason = sel.get("reason")
                        if node_name in neighbors_pool:
                            next_nodes.append(node_name)
                            visited.add(node_name)
                            
                            n_info = neighbors_pool[node_name]
                            traversal_history.append(
                                f"  * Walked to `{node_name}` ({n_info['label']}) from `{n_info['parent']}` via `{n_info['relationship']}`.\n"
                                f"    *Rationale*: {reason}"
                            )
                            
                            if n_info["label"] == "Paper":
                                all_referenced_papers.append(node_name)
                            elif n_info["label"] == "Claim":
                                paper_query = "MATCH (p:Paper)-[:EXTRACTED_CLAIM]->(c:Claim {id: $cid}) RETURN p.title AS title"
                                res_paper = self.client.query_graph(paper_query, {"cid": node_name})
                                if res_paper:
                                    all_referenced_papers.append(res_paper[0]["title"])
                
                if not next_nodes:
                    traversal_history.append("- *LLM selected empty/invalid branches. Defaulting to first neighbors.*")
                    next_nodes = [n["neighbor"] for n in neighbors_list[:beam_width]]
                    for n in next_nodes:
                        visited.add(n)
                
                active_nodes = next_nodes
            except Exception as e:
                logger.error("Error in ToG evaluation: %s", e)
                next_nodes = [n["neighbor"] for n in neighbors_list[:beam_width]]
                traversal_history.append(f"- *Reasoning failure: {e}. Falling back to default traversal: {', '.join(next_nodes)}*")
                for n in next_nodes:
                    visited.add(n)
                active_nodes = next_nodes

        # 3. Query details of visited papers
        paper_sources = []
        if all_referenced_papers:
            unique_papers = list(set(all_referenced_papers))
            for idx, title in enumerate(unique_papers, 1):
                p_query = """
                MATCH (p:Paper {title: $title})
                RETURN p.title AS title,
                       p.abstract AS abstract,
                       p.evidence_score AS evidence_score,
                       p.study_design AS study_design,
                       p.sample_size AS sample_size
                """
                res = self.client.query_graph(p_query, {"title": title})
                if res:
                    r = res[0]
                    paper_sources.append({
                        "index": idx,
                        "title": r["title"],
                        "evidence_score": r.get("evidence_score", 5.0),
                        "design": r.get("study_design", "Undetermined"),
                        "sample_size": r.get("sample_size", 0),
                        "abstract": r.get("abstract", "")
                    })

        context_str = "\n\n".join(traversal_history)
        return context_str, paper_sources
