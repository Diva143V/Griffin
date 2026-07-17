"""Retriever agent wrapping the semantic and graph retrieval helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

import pandas as pd

from ..core import graph_rag


def retrieve_standard(
    query: str,
    encoder_model: Any,
    ranked_df: pd.DataFrame,
    similarity_threshold: float = 0.60,
    max_papers: int = 8
) -> Tuple[str, List[Dict[str, Any]]]:
    return graph_rag.get_standard_rag_context(
        query, encoder_model, ranked_df, similarity_threshold, max_papers
    )


def retrieve_graph(
    query: str,
    encoder_model: Any,
    ranked_df: pd.DataFrame,
    contradictions_dict: Dict[str, Any],
    similarity_threshold: float = 0.60,
    max_papers: int = 8,
    neo4j_client: Optional[Any] = None
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    if neo4j_client is None:
        try:
            from ..core.neo4j_client import Neo4jClient
            client = Neo4jClient()
            if client.connect():
                neo4j_client = client
        except Exception:
            neo4j_client = None

    return graph_rag.get_graph_rag_context(
        query, encoder_model, ranked_df, contradictions_dict, similarity_threshold, max_papers, neo4j_client
    )
