"""Extract structured claims from the cleaned paper dataset using Ollama.

Upgrades over the original version:
- CLI arguments for input/output/model/row limits
- resume support if an output CSV already exists
- structured parsing into claim/stance/reason columns
- skip bad rows and keep going on model errors
- optional raw model output for debugging
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Optional
import concurrent.futures
from ..shared.llm import chat as llm_chat

import pandas as pd
from pydantic import BaseModel, ValidationError


DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_INPUT = "dataset/clean_papers.csv"
DEFAULT_OUTPUT = "dataset/claims.csv"
ALLOWED_STANCES = {"support", "contradict", "neutral"}

class ClaimOutput(BaseModel):
    claim: str
    stance: str
    reason: str


def build_prompt(title: str, abstract: str) -> str:
    return f"""
You are a biomedical research assistant.

Read the scientific abstract below and extract:
1. Main claim
2. Stance (support / contradict / neutral)
3. Short reason

Return ONLY a valid JSON object in this exact format:
{{
  "claim": "<one short sentence>",
  "stance": "<support|contradict|neutral>",
  "reason": "<one short sentence>"
}}

Title:
{title}

Abstract:
{abstract}
""".strip()


def parse_output(output: str) -> Dict[str, str]:
    """Best-effort parse of the model response into structured fields using Pydantic."""
    claim = ""
    stance = ""
    reason = ""

    try:
        data = ClaimOutput.model_validate_json(output)
        claim = data.claim
        raw_stance = data.stance
        reason = data.reason
        
        normalized = raw_stance.lower().strip()
        stance = normalized if normalized in ALLOWED_STANCES else raw_stance
        return {"claim": claim, "stance": stance, "reason": reason}
    except (ValidationError, ValueError):
        pass

    # Fallback to regex if JSON parsing fails
    patterns = {
        "claim": r"(?im)^\s*[\"']?claim[\"']?\s*:\s*[\"']?(.+?)[\"']?,?$",
        "stance": r"(?im)^\s*[\"']?stance[\"']?\s*:\s*[\"']?(.+?)[\"']?,?$",
        "reason": r"(?im)^\s*[\"']?reason[\"']?\s*:\s*[\"']?(.+?)[\"']?,?$",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            value = match.group(1).strip()
            if key == "claim":
                claim = value
            elif key == "stance":
                normalized = value.lower().strip()
                stance = normalized if normalized in ALLOWED_STANCES else value
            else:
                reason = value

    return {"claim": claim, "stance": stance, "reason": reason}


def load_existing_titles(path: str) -> set:
    if not os.path.exists(path):
        return set()
    try:
        existing = pd.read_csv(path)
    except Exception:
        return set()
    if "title" not in existing.columns:
        return set()
    return set(existing["title"].astype(str).str.strip().str.lower().tolist())


def _process_one_row(row, model, prompt_builder, resume, existing_titles):
    title = str(row["title"]).strip()
    abstract = str(row["abstract"]).strip()
    if not abstract:
        return None, None
    if resume and title.lower() in existing_titles:
        return None, None
    prompt = prompt_builder(title, abstract)
    try:
        resp = llm_chat(model, messages=[{"role": "user", "content": prompt}],
                        task="extract", format=ClaimOutput.model_json_schema())
        parsed = parse_output(resp["message"]["content"])
        return title, {
            "title": title, "claim": parsed["claim"], "stance": parsed["stance"],
            "reason": parsed["reason"], "claim_output": resp["message"]["content"], "model": model,
        }, None
    except Exception as exc:
        return title, {
            "title": title, "claim": "", "stance": "", "reason": "",
            "claim_output": f"ERROR: {exc}", "model": model,
        }, exc


def extract_claims(
    input_path: str,
    output_path: str,
    model: str,
    limit: Optional[int] = None,
    resume: bool = True,
    save_every: int = 10,
) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    print(f"Loaded papers: {len(df)} from {input_path}")

    if "title" not in df.columns:
        df["title"] = ""
    if "abstract" not in df.columns:
        raise ValueError("Input CSV must contain an 'abstract' column")

    df["title"] = df["title"].fillna("").astype(str)
    df["abstract"] = df["abstract"].fillna("").astype(str)

    existing_titles = load_existing_titles(output_path) if resume else set()
    if existing_titles:
        print(f"Resuming from {output_path}: {len(existing_titles)} already processed titles")

    rows: List[Dict[str, str]] = []
    if os.path.exists(output_path) and resume:
        try:
            rows = pd.read_csv(output_path).to_dict(orient="records")
        except Exception:
            rows = []

    processed_count = 0
    to_process = [r for _, r in df.iterrows()]
    if limit is not None:
        to_process = to_process[:limit]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(_process_one_row, r, model, build_prompt, resume, existing_titles)
                   for r in to_process]
        for fut in concurrent.futures.as_completed(futures):
            result = fut.result()
            if result[1] is None:
                continue
            title, record, err = result
            rows.append(record)
            existing_titles.add(title.lower())
            processed_count += 1
            if err:
                print(f"Error processing paper: {err}")
            else:
                print("\n" + "=" * 60)
                print(f"PAPER {processed_count}")
                print("=" * 60)
                print(record["claim_output"])
            
            if save_every and processed_count % save_every == 0:
                pd.DataFrame(rows).to_csv(output_path, index=False)
                print(f"Checkpoint saved to {output_path} ({len(rows)} rows)")

    claims_df = pd.DataFrame(rows)
    claims_df.to_csv(output_path, index=False)
    print(f"\nSaved {output_path} ({len(claims_df)} rows)")
    return claims_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured claims from clean papers using Ollama")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=50, help="Maximum papers to process from the input file")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from an existing output CSV")
    parser.add_argument("--save-every", type=int, default=10, help="Checkpoint every N processed papers")
    args = parser.parse_args()

    extract_claims(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        limit=args.limit,
        resume=not args.no_resume,
        save_every=args.save_every,
    )


if __name__ == "__main__":
    main()