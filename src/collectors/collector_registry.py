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
from .collect_clinicaltrials import collect as collect_clinicaltrials
from .collect_biorxiv import collect as collect_biorxiv
from .collect_chembl import collect as collect_chembl
from .collect_uniprot import collect as collect_uniprot
from .collect_pubchem import collect as collect_pubchem
from .collect_dbsnp import collect as collect_dbsnp


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
    "ClinicalTrials": CollectorSpec(
        name="ClinicalTrials",
        output_path="dataset/clinicaltrials.csv",
        priority=4,
        description="ClinicalTrials.gov collector",
        runner=lambda query, args: collect_clinicaltrials(
            query,
            page_size=getattr(args, "clinicaltrials_limit", 50),
            max_pages=1,
            rate_limit_sec=getattr(args, "clinicaltrials_rate_limit", 1.0),
        ),
    ),
    "bioRxiv": CollectorSpec(
        name="bioRxiv",
        output_path="dataset/biorxiv.csv",
        priority=5,
        description="bioRxiv preprint collector",
        runner=lambda query, args: collect_biorxiv(
            query,
            page_size=getattr(args, "biorxiv_limit", 100),
            max_pages=1,
        ),
    ),
    "ChEMBL": CollectorSpec(
        name="ChEMBL",
        output_path="dataset/chembl.csv",
        priority=6,
        description="ChEMBL bioactive molecule collector",
        runner=lambda query, args: collect_chembl(
            query,
            page_size=getattr(args, "chembl_limit", 10),
            max_pages=1,
        ),
    ),
    "UniProt": CollectorSpec(
        name="UniProt",
        output_path="dataset/uniprot.csv",
        priority=7,
        description="UniProt protein collector",
        runner=lambda query, args: collect_uniprot(
            query,
            page_size=getattr(args, "uniprot_limit", 5),
            max_pages=1,
        ),
    ),
    "PubChem": CollectorSpec(
        name="PubChem",
        output_path="dataset/pubchem.csv",
        priority=8,
        description="PubChem chemical properties collector",
        runner=lambda query, args: collect_pubchem(
            query,
            page_size=getattr(args, "pubchem_limit", 5),
            max_pages=1,
        ),
    ),
    "dbSNP": CollectorSpec(
        name="dbSNP",
        output_path="dataset/dbsnp.csv",
        priority=9,
        description="NCBI dbSNP genetic variant collector",
        runner=lambda query, args: collect_dbsnp(
            query,
            page_size=getattr(args, "dbsnp_limit", 5),
            max_pages=1,
            email=getattr(args, "email", ""),
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
