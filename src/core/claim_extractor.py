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

import ollama
import pandas as pd


DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_INPUT = "dataset/clean_papers.csv"
DEFAULT_OUTPUT = "dataset/claims.csv"
ALLOWED_STANCES = {"support", "contradict", "neutral"}


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
    """Best-effort parse of the model response into structured fields."""
    import json
    claim = ""
    stance = ""
    reason = ""

    try:
        data = json.loads(output)
        claim = data.get("claim", "")
        raw_stance = data.get("stance", "")
        reason = data.get("reason", "")
        
        normalized = raw_stance.lower().strip()
        stance = normalized if normalized in ALLOWED_STANCES else raw_stance
        return {"claim": claim, "stance": stance, "reason": reason}
    except Exception:
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
    for idx, row in df.iterrows():
        if limit is not None and processed_count >= limit:
            break

        title = str(row["title"]).strip()
        abstract = str(row["abstract"]).strip()

        if not abstract:
            continue

        title_key = title.lower()
        if resume and title_key in existing_titles:
            continue

        prompt = build_prompt(title, abstract)

        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format="json"
            )
            output = response["message"]["content"]
            parsed = parse_output(output)

            rows.append(
                {
                    "title": title,
                    "claim": parsed["claim"],
                    "stance": parsed["stance"],
                    "reason": parsed["reason"],
                    "claim_output": output,
                    "model": model,
                }
            )

            existing_titles.add(title_key)
            processed_count += 1

            print("\n" + "=" * 60)
            print(f"PAPER {processed_count}")
            print("=" * 60)
            print(output)

            if save_every and processed_count % save_every == 0:
                pd.DataFrame(rows).to_csv(output_path, index=False)
                print(f"Checkpoint saved to {output_path} ({len(rows)} rows)")

        except Exception as exc:
            rows.append(
                {
                    "title": title,
                    "claim": "",
                    "stance": "",
                    "reason": "",
                    "claim_output": f"ERROR: {exc}",
                    "model": model,
                }
            )
            processed_count += 1
            print(f"Error processing paper {idx + 1}: {exc}")

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