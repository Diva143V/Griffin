"""Collect compound chemical data from PubChem PUG REST API and format into paper structure."""
from __future__ import annotations

import argparse
import time
import requests
import pandas as pd
from typing import List, Dict, Any


def fetch_pubchem_properties(session: requests.Session, name: str) -> Dict[str, Any]:
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IUPACName,MolecularFormula,MolecularWeight,CanonicalSMILES/JSON"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def collect(query: str, page_size: int = 5, max_pages: int = 1, rate_limit_sec: float = 1.0) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": "GriffinBioAgent/1.0"})
    
    compounds = []
    
    # Extract chemical keywords
    keywords = [w.strip() for w in query.split() if len(w.strip()) > 3]
    search_term = keywords[0] if keywords else query
    
    try:
        data = fetch_pubchem_properties(session, search_term)
        table = data.get("PropertyTable", {}) or {}
        properties = table.get("Properties", []) or []
        
        for prop in properties[:page_size]:
            cid = prop.get("CID", "")
            formula = prop.get("MolecularFormula", "N/A")
            mw = prop.get("MolecularWeight", "N/A")
            smiles = prop.get("CanonicalSMILES", "N/A")
            iupac = prop.get("IUPACName", "N/A")
            
            abstract = (
                f"Chemical Structure Profile: PubChem CID: {cid}. "
                f"IUPAC Name: {iupac}. "
                f"Molecular Formula: {formula} | Molecular Weight: {mw} g/mol. "
                f"Canonical SMILES: {smiles}."
            )
            
            compounds.append({
                "title": f"Chemical Profile: {search_term.capitalize()} (CID {cid})",
                "abstract": abstract,
                "authors": "National Center for Biotechnology Information (NCBI)",
                "journal": "PubChem Compound Database",
                "year": "N/A",
                "doi": f"PubChemCID:{cid}" if cid else "",
                "pmid": str(cid),
                "pmcid": "",
                "source": "PubChem",
            })
            
    except Exception as e:
        print(f"PubChem collection failed: {e}")
        
    df = pd.DataFrame(compounds)
    return df


def main():
    parser = argparse.ArgumentParser(description="Collect compounds from PubChem")
    parser.add_argument("--query", default="metformin")
    parser.add_argument("--page-size", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--output", default="dataset/pubchem.csv")
    args = parser.parse_args()

    df = collect(args.query, page_size=args.page_size, max_pages=args.max_pages, rate_limit_sec=args.rate_limit)
    df.to_csv(args.output, index=False)
    print(f"Saved {args.output} with {len(df)} records")


if __name__ == "__main__":
    main()
