"""Collect molecule data from ChEMBL API and format into paper structure."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def fetch_molecules(session: requests.Session, query: str, limit: int = 10) -> Dict[str, Any]:
    url = "https://www.ebi.ac.uk/chembl/api/data/molecule.json"
    params = {
        "search": query,
        "limit": limit
    }
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 10, max_pages: int = 1, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "GriffinBioAgent/1.0"})
    
    compounds = []
    
    # Extract chemical keywords from query
    keywords = [w.strip() for w in query.split() if len(w.strip()) > 3]
    search_term = keywords[0] if keywords else query
    
    try:
        data = fetch_molecules(session, search_term, limit=page_size)
        molecules = data.get("molecules", [])
        
        for mol in molecules:
            name = mol.get("pref_name") or mol.get("chembl_id", "Unknown Compound")
            chembl_id = mol.get("chembl_id", "")
            
            # Reconstruct properties into a pseudo-abstract
            props = mol.get("molecule_properties", {}) or {}
            mw = props.get("mw_freebase", "N/A")
            logp = props.get("alogp", "N/A")
            hbd = props.get("hbd", "N/A")
            hba = props.get("hba", "N/A")
            smiles = mol.get("molecule_structures", {}).get("canonical_smiles", "N/A") if mol.get("molecule_structures") else "N/A"
            
            abstract = (
                f"Chemical Compound Profile: {name} (ChEMBL ID: {chembl_id}). "
                f"Molecular Weight: {mw} g/mol | ALOGP: {logp} | "
                f"Hydrogen Bond Donors: {hbd} | Hydrogen Bond Acceptors: {hba}. "
                f"Canonical SMILES: {smiles}."
            )
            
            compounds.append({
                "title": f"Compound Profile: {name} ({chembl_id})",
                "abstract": abstract,
                "authors": "ChEMBL Database Team",
                "journal": "EMBL-EBI ChEMBL Database",
                "year": "N/A",
                "doi": f"ChEMBL:{chembl_id}" if chembl_id else "",
                "pmid": chembl_id,
                "pmcid": "",
                "source": "ChEMBL",
            })
            
    except Exception as e:
        print(f"ChEMBL collection failed: {e}")
        
    df = pd.DataFrame(compounds)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect compounds from ChEMBL")
    parser.add_argument("--query", default="metformin")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--output", default="dataset/chembl.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
