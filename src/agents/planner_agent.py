"""Planner agent for routing medical research questions into workflow stages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class PlannerStep:
    name: str
    description: str
    enabled: bool = True


@dataclass
class WorkflowNode:
    name: str
    layer: str
    description: str
    status: str = "available"
    outputs: List[str] = field(default_factory=list)


@dataclass
class WorkflowSection:
    name: str
    description: str
    node_names: List[str] = field(default_factory=list)


@dataclass
class WorkflowEdge:
    source: str
    target: str
    label: str = ""


@dataclass
class QueryPlan:
    query: str
    intent: str
    route: str
    model: str
    top_k: int
    steps: List[PlannerStep] = field(default_factory=list)
    workflow: List[WorkflowNode] = field(default_factory=list)
    sections: List[WorkflowSection] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    collector_targets: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _keyword_match(query: str, keywords: List[str]) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in keywords)


def _collector_targets() -> List[str]:
    return ["PubMed", "PMC", "Semantic Scholar"]


def _build_sections() -> List[WorkflowSection]:
    return [
        WorkflowSection("Input", "Query capture and routing", ["Query", "Planner"]),
        WorkflowSection("Collection", "Source collection from external APIs", ["Retriever", "PubMed", "PMC", "Semantic Scholar"]),
        WorkflowSection("Preparation", "Filtering and normalization", ["Filter", "Converter/Standardizer"]),
        WorkflowSection("Indexing", "Embedding and vector search", ["Embedding", "Vector DB"]),
        WorkflowSection("Execution", "Route-specific execution and analysis", ["Executor", "Evidence Ranker", "Claim Extractor", "Contradiction Agent", "Consensus Agent"]),
        WorkflowSection("Output", "Synthesis and verification", ["Synthesizer", "Verifier"]),
    ]


def _build_edges() -> List[WorkflowEdge]:
    return [
        WorkflowEdge("Query", "Planner"),
        WorkflowEdge("Planner", "Retriever"),
        WorkflowEdge("Retriever", "PubMed"),
        WorkflowEdge("Retriever", "PMC"),
        WorkflowEdge("Retriever", "Semantic Scholar"),
        WorkflowEdge("PubMed", "Filter"),
        WorkflowEdge("PMC", "Filter"),
        WorkflowEdge("Semantic Scholar", "Filter"),
        WorkflowEdge("Filter", "Converter/Standardizer"),
        WorkflowEdge("Converter/Standardizer", "Embedding"),
        WorkflowEdge("Embedding", "Vector DB"),
        WorkflowEdge("Vector DB", "Executor"),
        WorkflowEdge("Executor", "Evidence Ranker"),
        WorkflowEdge("Evidence Ranker", "Claim Extractor"),
        WorkflowEdge("Claim Extractor", "Contradiction Agent"),
        WorkflowEdge("Contradiction Agent", "Consensus Agent"),
        WorkflowEdge("Consensus Agent", "Synthesizer"),
        WorkflowEdge("Synthesizer", "Verifier"),
    ]


def _build_workflow(route: str) -> List[WorkflowNode]:
    active_agents = {
        "standard_rag": {"Claim Extractor": "available", "Evidence Ranker": "active"},
        "ranked_evidence_rag": {"Claim Extractor": "available", "Evidence Ranker": "active"},
        "claims_exploration": {"Claim Extractor": "active", "Evidence Ranker": "available"},
        "scientific_synthesis": {"Claim Extractor": "active", "Contradiction Agent": "active", "Consensus Agent": "active", "Evidence Ranker": "active"},
        "graph_rag + contradiction_review": {"Claim Extractor": "active", "Contradiction Agent": "active", "Consensus Agent": "active", "Evidence Ranker": "active"},
    }

    route_overrides = active_agents.get(route, {})

    def status_for(name: str, default: str = "available") -> str:
        return route_overrides.get(name, default)

    return [
        WorkflowNode("Query", "input", "Capture the user question and convert it into a structured task.", status="active", outputs=["query_text"]),
        WorkflowNode("Planner", "orchestration", "Choose the route, top-k, and downstream stages.", status="active", outputs=["query_plan"]),
        WorkflowNode("Retriever", "retrieval", "Coordinate the retrieval path for the current query.", status="active", outputs=["retrieval_mode"]),
        WorkflowNode("PubMed", "collector", "Optional upstream source collector for biomedical literature.", status="available", outputs=["pubmed.csv"]),
        WorkflowNode("PMC", "collector", "Optional upstream source collector for Europe PMC.", status="available", outputs=["pmc.csv"]),
        WorkflowNode("Semantic Scholar", "collector", "Optional upstream source collector for broader citation coverage.", status="available", outputs=["semantic_scholar.csv"]),
        WorkflowNode("Filter", "processing", "Remove duplicates and enforce topic relevance.", status="active", outputs=["clean_papers.csv"]),
        WorkflowNode("Converter/Standardizer", "processing", "Normalize paper fields into a unified schema.", status="active", outputs=["canonical_rows"]),
        WorkflowNode("Embedding", "indexing", "Convert paper text into dense vector representations.", status="active", outputs=["embedding_vectors"]),
        WorkflowNode("Vector DB", "indexing", "Store and query embeddings for semantic retrieval.", status="active", outputs=["vector_matches"]),
        WorkflowNode("Executor", "execution", "Run the selected retrieval and reasoning pipeline.", status="active", outputs=["execution_trace"]),
        WorkflowNode("Evidence Ranker", "analysis", "Score evidence quality, study design, and sample size.", status=status_for("Evidence Ranker"), outputs=["ranked_papers.csv"]),
        WorkflowNode("Claim Extractor", "analysis", "Extract structured claims and stance from the evidence corpus.", status=status_for("Claim Extractor"), outputs=["claims.csv"]),
        WorkflowNode("Contradiction Agent", "analysis", "Compare claim pairs and detect scientific conflict.", status=status_for("Contradiction Agent"), outputs=["contradictions.json"]),
        WorkflowNode("Consensus Agent", "analysis", "Summarize agreement and convergence across studies.", status=status_for("Consensus Agent"), outputs=["consensus_summary"]),
        WorkflowNode("Synthesizer", "output", "Combine the evidence into the final answer or report.", status="active", outputs=["final_synthesis.md"]),
        WorkflowNode("Verifier", "output", "Check that claims, citations, and conclusions are consistent.", status="active", outputs=["verified_response"]),
    ]


def build_query_plan(query: str, model: str, default_top_k: int = 5) -> QueryPlan:
    text = query.strip()
    if not text:
        return QueryPlan(
            query=query,
            intent="empty",
            route="idle",
            model=model,
            top_k=default_top_k,
            steps=[PlannerStep("collect_query", "Wait for a non-empty query from the user.")],
            workflow=_build_workflow("idle"),
            sections=_build_sections(),
            edges=_build_edges(),
            collector_targets=_collector_targets(),
            notes=["Enter a medical research question to generate a route."],
        )

    is_contradiction = _keyword_match(text, ["contradiction", "conflict", "agree", "agreement", "disagree", "different"])
    is_evidence = _keyword_match(text, ["evidence", "rank", "quality", "study design", "sample size", "level of evidence"])
    is_claim = _keyword_match(text, ["claim", "stance", "assertion", "argument"])
    is_summary = _keyword_match(text, ["summary", "synthes", "overview", "conclusion", "what do studies show"])

    if is_contradiction:
        route = "graph_rag + contradiction_review"
        intent = "conflict_analysis"
        top_k = max(default_top_k, 5)
        steps = [
            PlannerStep("retrieve_papers", "Retrieve the most relevant papers from the evidence index."),
            PlannerStep("load_relations", "Load contradiction and agreement relationships from the graph."),
            PlannerStep("compose_graph_context", "Combine source papers with graph links for comparison."),
            PlannerStep("generate_answer", "Use the selected Ollama model to explain agreement or conflict."),
        ]
        notes = ["Focus on contradictions, agreements, and relationship evidence."]
    elif is_evidence:
        route = "ranked_evidence_rag"
        intent = "evidence_review"
        top_k = max(default_top_k, 5)
        steps = [
            PlannerStep("retrieve_papers", "Retrieve ranked papers by similarity and evidence score."),
            PlannerStep("filter_quality", "Prioritize papers with stronger study design and sample size."),
            PlannerStep("generate_answer", "Summarize evidence quality with citations."),
        ]
        notes = ["Emphasize study quality, design, and sample size."]
    elif is_claim:
        route = "claims_exploration"
        intent = "claim_analysis"
        top_k = max(default_top_k, 3)
        steps = [
            PlannerStep("retrieve_claims", "Find structured claims that match the query topic."),
            PlannerStep("compare_claims", "Inspect stance and supporting reasons across sources."),
            PlannerStep("generate_answer", "Summarize the claim-level pattern for the user."),
        ]
        notes = ["Inspect the claim extraction layer rather than full paper text."]
    elif is_summary:
        route = "scientific_synthesis"
        intent = "summary"
        top_k = max(default_top_k, 5)
        steps = [
            PlannerStep("retrieve_papers", "Retrieve the strongest evidence papers for the topic."),
            PlannerStep("review_contradictions", "Check whether the topic has recorded conflicts or agreements."),
            PlannerStep("generate_answer", "Produce a concise synthesis of the evidence."),
        ]
        notes = ["Use synthesis-first reasoning with evidence-aware citations."]
    else:
        route = "standard_rag"
        intent = "general_research_question"
        top_k = default_top_k
        steps = [
            PlannerStep("retrieve_papers", "Retrieve the most relevant papers by semantic similarity."),
            PlannerStep("build_context", "Construct a concise context window from the top papers."),
            PlannerStep("generate_answer", "Answer the question using the selected Ollama model."),
        ]
        notes = ["Use general retrieval first; route to graph mode only if conflict language appears."]

    return QueryPlan(
        query=text,
        intent=intent,
        route=route,
        model=model,
        top_k=top_k,
        steps=steps,
        workflow=_build_workflow(route),
        sections=_build_sections(),
        edges=_build_edges(),
        collector_targets=_collector_targets(),
        notes=notes,
    )


def plan_to_dict(plan: QueryPlan) -> Dict[str, object]:
    return {
        "query": plan.query,
        "intent": plan.intent,
        "route": plan.route,
        "model": plan.model,
        "top_k": plan.top_k,
        "steps": [asdict(step) for step in plan.steps],
        "workflow": [asdict(node) for node in plan.workflow],
        "sections": [asdict(section) for section in plan.sections],
        "edges": [asdict(edge) for edge in plan.edges],
        "collector_targets": plan.collector_targets,
        "notes": plan.notes,
    }
