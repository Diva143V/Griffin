"""Semantic Scholar API client with simple rate-limiting and helpers.

Usage:
  - Set the `SEMANTIC_SCHOLAR_API_KEY` environment variable (do NOT commit it).
  - Instantiate `SemanticScholarClient()` and call `search()` or `get_paper()`.

The Semantic Scholar API requires the API key to be sent as `x-api-key` header
and enforces a rate limit of 1 request per second. This client respects that.
"""
from __future__ import annotations

import time
import requests
from typing import List, Dict, Any

from ..shared.config import SEMANTIC_SCHOLAR_BASE_URL, require_semantic_scholar_api_key


class SemanticScholarClient:
    def __init__(self, api_key: str | None = None, rate_limit_per_sec: float = 1.0, session: requests.Session | None = None):
        self.api_key = api_key or require_semantic_scholar_api_key()
        if rate_limit_per_sec <= 0:
            raise ValueError("rate_limit_per_sec must be > 0")
        self.min_interval = 1.0 / rate_limit_per_sec
        self._last_call = 0.0
        self.session = session or requests.Session()

    def _wait_for_slot(self) -> None:
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        # Implement exponential-backoff retries to handle 429 / transient errors.
        retries = 5
        base_backoff = 1.0
        url = SEMANTIC_SCHOLAR_BASE_URL.rstrip("/") + "/" + path.lstrip("/")
        headers = {"x-api-key": self.api_key}

        for attempt in range(1, retries + 1):
            self._wait_for_slot()
            try:
                resp = self.session.get(url, headers=headers, params=params, timeout=30)
                self._last_call = time.time()

                # Handle rate limit specially so we can back off and retry
                if resp.status_code == 429:
                    wait = base_backoff * (2 ** (attempt - 1))
                    print(f"Semantic Scholar 429 (rate limit). Backing off {wait}s (attempt {attempt}/{retries})")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as e:
                # transient network error, back off and retry
                if attempt == retries:
                    raise
                wait = base_backoff * (2 ** (attempt - 1))
                print(f"Request error: {e}. Retrying in {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)

        raise RuntimeError(f"Failed to GET {url} after {retries} attempts")

    def search(self, query: str, limit: int = 10, offset: int = 0, fields: List[str] | None = None) -> List[Dict[str, Any]]:
        """Search for papers matching `query`. Returns a list of paper dicts.

        The Graph API `/paper/search` endpoint is used. `fields` is a list
        of requested fields (see Semantic Scholar docs).
        """
        if fields is None:
            fields = ["title", "abstract", "year", "authors", "venue", "url", "externalIds"]
        params = {"query": query, "limit": limit, "offset": offset, "fields": ",".join(fields)}
        data = self._get("/paper/search", params=params)
        # API returns top-level "data" list for search
        return data.get("data", [])

    def get_paper(self, paper_id: str, fields: List[str] | None = None) -> Dict[str, Any]:
        """Fetch a single paper by Semantic Scholar id (paperId) or DOI.
        Example paper_id: "CorpusID:..." or DOI string.
        """
        if fields is None:
            fields = ["title", "abstract", "year", "authors", "venue", "url", "externalIds"]
        params = {"fields": ",".join(fields)}
        return self._get(f"/paper/{paper_id}", params=params)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Query Semantic Scholar")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    client = SemanticScholarClient()
    results = client.search(args.query, limit=args.limit)
    print(json.dumps(results, indent=2))
