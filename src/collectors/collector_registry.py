"""Registry for paper collectors used by the dataset build pipeline.

Collectors are defined in one place so the orchestrator can treat them as
independent add-ons while still keeping a stable merge order and output paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping

import pandas as pd

from .collect_pmc import collect as collect_pmc
from .collect_pubmed import collect as collect_pubmed
from .collect_semanticscholar import collect as collect_semanticscholar
from .collect_openalex import collect as collect_openalex


@dataclass(frozen=True)
class CollectorSpec:
    name: str
    output_path: str
    priority: int
    description: str
    runner: Callable[[str, Any], pd.DataFrame]


DEFAULT_COLLECTORS: Dict[str, CollectorSpec] = {
    "PubMed": CollectorSpec(
        name="PubMed",
        output_path="dataset/pubmed.csv",
        priority=0,
        description="PubMed Entrez collector",
        runner=lambda query, args: collect_pubmed(
            query,
            email=args.email,
            batch_size=args.pubmed_batch_size,
            rate_limit_sec=args.pubmed_rate_limit,
        ),
    ),
    "PMC": CollectorSpec(
        name="PMC",
        output_path="dataset/pmc.csv",
        priority=1,
        description="Europe PMC collector",
        runner=lambda query, args: collect_pmc(
            query,
            page_size=args.pmc_page_size,
            max_pages=args.pmc_max_pages,
            rate_limit_sec=args.pmc_rate_limit,
        ),
    ),
    "SemanticScholar": CollectorSpec(
        name="SemanticScholar",
        output_path="dataset/semantic_scholar.csv",
        priority=2,
        description="Semantic Scholar collector",
        runner=lambda query, args: collect_semanticscholar(
            query,
            limit=args.ss_limit,
            offset=args.ss_offset,
            max_pages=args.ss_max_pages,
            delay=args.ss_delay,
        ),
    ),
    "OpenAlex": CollectorSpec(
        name="OpenAlex",
        output_path="dataset/openalex.csv",
        priority=3,
        description="OpenAlex collector",
        runner=lambda query, args: collect_openalex(
            query,
            per_page=getattr(args, "openalex_per_page", 20),
            max_pages=getattr(args, "openalex_max_pages", 2),
            rate_limit_sec=getattr(args, "openalex_rate_limit", 1.0),
            email=getattr(args, "email", None),
        ),
    ),
}


def list_collectors() -> List[CollectorSpec]:
    return sorted(DEFAULT_COLLECTORS.values(), key=lambda spec: spec.priority)


def get_collector_names() -> List[str]:
    return [spec.name for spec in list_collectors()]


def get_selected_collectors(selected: Iterable[str] | None = None) -> List[CollectorSpec]:
    if selected is None:
        return list_collectors()

    selected_names = [str(name).strip() for name in selected if str(name).strip()]
    if not selected_names:
        return list_collectors()

    unknown = [name for name in selected_names if name not in DEFAULT_COLLECTORS]
    if unknown:
        raise ValueError(f"Unknown collector(s): {', '.join(unknown)}")

    return [spec for spec in list_collectors() if spec.name in selected_names]


def source_paths(selected: Iterable[str] | None = None) -> Mapping[str, str]:
    return {spec.name: spec.output_path for spec in get_selected_collectors(selected)}
