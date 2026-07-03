"""Claim extractor agent facade."""
from __future__ import annotations

from ..core.claim_extractor import build_prompt, extract_claims, load_existing_titles, parse_output

__all__ = ["build_prompt", "extract_claims", "load_existing_titles", "parse_output"]
