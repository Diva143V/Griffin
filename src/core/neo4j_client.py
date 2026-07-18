"""Neo4j client utility wrapper for connections, setup, and data ingestion (including Vector Search)."""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


class Neo4jClient:
    """Manages connections and schema operations for Neo4j."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USERNAME,
        password: str = NEO4J_PASSWORD,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[Driver] = None

    def connect(self) -> bool:
        """Establishes connection to the Neo4j instance."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Failed to connect to Neo4j database: %s", e)
            self.driver = None
            return False

    def close(self):
        """Closes the database driver connection."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def verify_connection(self) -> bool:
        """Verifies if the connection is active."""
        if not self.driver:
            return self.connect()
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def setup_constraints(self):
        """Creates unique constraints and native Vector Index."""
        if not self.driver:
            raise RuntimeError("Database driver is not connected.")

        queries = [
            "CREATE CONSTRAINT paper_title_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.title IS UNIQUE",
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT query_text_unique IF NOT EXISTS FOR (q:Query) REQUIRE q.text IS UNIQUE",
            "CREATE CONSTRAINT report_composite_unique IF NOT EXISTS FOR (r:Report) REQUIRE (r.type, r.query_text) IS UNIQUE",
            # Native Vector Index for Paper embeddings (384-dimensional cosine similarity index)
            """
            CREATE VECTOR INDEX paper_embeddings IF NOT EXISTS
            FOR (p:Paper) ON (p.embedding)
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 384,
                `vector.similarity_function`: 'cosine'
              }
            }
            """
        ]

        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    logger.warning("Constraint/index creation skipped or failed: %s", e)

    def clear_database(self):
        """Deletes all nodes and relationships from the database."""
        if not self.driver:
            raise RuntimeError("Database driver is not connected.")
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query)

    def ingest_paper(
        self,
        title: str,
        evidence_score: float,
        study_design: str,
        sample_size: int,
        embedding: Optional[List[float]] = None,
        abstract: str = "",
    ):
        """Merges a paper node in Neo4j, updating metadata and optional vector embeddings."""
        if embedding is not None:
            query = """
            MERGE (p:Paper {title: $title})
            SET p.evidence_score = $evidence_score,
                p.study_design = $study_design,
                p.sample_size = $sample_size,
                p.embedding = $embedding,
                p.abstract = $abstract
            """
            params = {
                "title": title,
                "evidence_score": evidence_score,
                "study_design": study_design,
                "sample_size": sample_size,
                "embedding": embedding,
                "abstract": abstract
            }
        else:
            query = """
            MERGE (p:Paper {title: $title})
            SET p.evidence_score = $evidence_score,
                p.study_design = $study_design,
                p.sample_size = $sample_size,
                p.abstract = $abstract
            """
            params = {
                "title": title,
                "evidence_score": evidence_score,
                "study_design": study_design,
                "sample_size": sample_size,
                "abstract": abstract
            }

        with self.driver.session() as session:
            session.run(query, **params)

    def ingest_claim(
        self,
        paper_title: str,
        claim_id: str,
        claim_text: str,
        stance: str,
    ):
        """Merges a claim node and links it to its parent paper."""
        query = """
        MERGE (c:Claim {id: $claim_id})
        SET c.claim_text = $claim_text,
            c.stance = $stance
        WITH c
        MERGE (p:Paper {title: $paper_title})
        MERGE (p)-[:EXTRACTED_CLAIM]->(c)
        """
        with self.driver.session() as session:
            session.run(
                query,
                claim_id=claim_id,
                claim_text=claim_text,
                stance=stance,
                paper_title=paper_title,
            )

    def ingest_claim_relationship(
        self,
        claim_a_id: str,
        claim_b_id: str,
        relationship_type: str,
        confidence: float,
        explanation: str,
        weight: float,
    ):
        """Creates a relationship edge between two claim nodes."""
        valid_rel_types = {"CONTRADICTS", "AGREES", "PARTIAL_AGREES"}
        rel_type = relationship_type.upper().strip()
        if rel_type not in valid_rel_types:
            logger.warning("Unsupported relationship type: %s", rel_type)
            return

        query = f"""
        MATCH (a:Claim {{id: $claim_a_id}})
        MATCH (b:Claim {{id: $claim_b_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r.confidence = $confidence,
            r.explanation = $explanation,
            r.weight = $weight
        """
        with self.driver.session() as session:
            session.run(
                query,
                claim_a_id=claim_a_id,
                claim_b_id=claim_b_id,
                confidence=confidence,
                explanation=explanation,
                weight=weight,
            )

    def ingest_entity_and_interaction(
        self,
        claim_id: str,
        entity_a_name: str,
        entity_a_type: str,
        entity_b_name: str,
        entity_b_type: str,
        predicate: str,
        paper_title: str,
    ):
        """Merges two entity nodes, links them to the claim, and creates an interaction relationship."""
        query = """
        MERGE (e1:Entity {name: $entity_a_name})
        SET e1.type = $entity_a_type
        MERGE (e2:Entity {name: $entity_b_name})
        SET e2.type = $entity_b_type
        WITH e1, e2
        MATCH (c:Claim {id: $claim_id})
        MERGE (c)-[:MENTIONS]->(e1)
        MERGE (c)-[:MENTIONS]->(e2)
        MERGE (e1)-[r:INTERACTS_WITH {predicate: $predicate, paper_title: $paper_title}]->(e2)
        """
        with self.driver.session() as session:
            session.run(
                query,
                claim_id=claim_id,
                entity_a_name=entity_a_name,
                entity_a_type=entity_a_type,
                entity_b_name=entity_b_name,
                entity_b_type=entity_b_type,
                predicate=predicate,
                paper_title=paper_title,
            )

    def ingest_query(
        self,
        text: str,
        intent: str,
        route: str,
        model: str,
        timestamp: str,
    ):
        """Merges a Query node representing a pipeline execution."""
        query = """
        MERGE (q:Query {text: $text})
        SET q.intent = $intent,
            q.route = $route,
            q.model = $model,
            q.timestamp = $timestamp
        """
        with self.driver.session() as session:
            session.run(
                query,
                text=text,
                intent=intent,
                route=route,
                model=model,
                timestamp=timestamp,
            )

    def ingest_report(
        self,
        query_text: str,
        report_type: str,
        content: str,
        agent: str,
        model: str,
        timestamp: str,
    ):
        """Merges a Report node and links it to its starting Query."""
        query = """
        MERGE (r:Report {type: $report_type, query_text: $query_text})
        SET r.content = $content,
            r.agent = $agent,
            r.model = $model,
            r.timestamp = $timestamp
        WITH r
        MATCH (q:Query {text: $query_text})
        MERGE (q)-[:PRODUCED_REPORT]->(r)
        """
        with self.driver.session() as session:
            session.run(
                query,
                query_text=query_text,
                report_type=report_type,
                content=content,
                agent=agent,
                model=model,
                timestamp=timestamp,
            )

    def ingest_report_paper_link(
        self,
        query_text: str,
        report_type: str,
        paper_title: str,
    ):
        """Creates a REFERENCES_PAPER link from a Report to a Paper if both exist."""
        query = """
        MATCH (r:Report {type: $report_type, query_text: $query_text})
        MATCH (p:Paper {title: $paper_title})
        MERGE (r)-[:REFERENCES_PAPER]->(p)
        """
        with self.driver.session() as session:
            session.run(
                query,
                query_text=query_text,
                report_type=report_type,
                paper_title=paper_title,
            )

    def query_vector_similar_papers(
        self,
        query_vector: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Queries Neo4j's native vector index to find semantically similar papers."""
        if not self.driver:
            raise RuntimeError("Database driver is not connected.")
        query = """
        CALL db.index.vector.queryNodes('paper_embeddings', $top_k, $query_vector)
        YIELD node, score
        RETURN node.title AS title,
               node.abstract AS abstract,
               node.evidence_score AS evidence_score,
               node.study_design AS study_design,
               node.sample_size AS sample_size,
               score
        """
        return self.query_graph(query, {"query_vector": query_vector, "top_k": top_k})

    def query_graph(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query and returns the results."""
        if not self.driver:
            raise RuntimeError("Database driver is not connected.")
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]
