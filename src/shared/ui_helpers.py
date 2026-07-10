"""Shared utility functions for both Streamlit and Reflex UIs.

Eliminates code duplication across app.py and griffin_reflex.py.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def parse_embedding(value: Any) -> np.ndarray:
    """Safely parse embedding vectors from CSV values (JSON, Python literal, or raw)."""
    if isinstance(value, list):
        return np.asarray(value, dtype=np.float32)
    if isinstance(value, str):
        try:
            return np.asarray(json.loads(value), dtype=np.float32)
        except Exception:
            try:
                return np.asarray(ast.literal_eval(value), dtype=np.float32)
            except Exception:
                pass
    if isinstance(value, np.ndarray):
        return value.astype(np.float32)
    return np.zeros(384, dtype=np.float32)


def format_reasoning_text(text: str, mode: str) -> str:
    """Format <think>...</think> reasoning blocks from LLM output.

    Args:
        text: Raw LLM output that may contain <think> tags.
        mode: One of "Display in Expander", "Strip Completely", "Raw Text".

    Returns:
        Processed text with reasoning blocks handled per mode.
    """
    if not text:
        return ""

    think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
    if think_match:
        think_content = think_match.group(1).strip()
        clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        if mode == "Display in Expander":
            return f"**💭 Reasoning Chain:**\n```\n{think_content}\n```\n\n{clean_text}"
        elif mode == "Strip Completely":
            return clean_text
        else:
            return text
    return text


def audit_methodology(row: Dict[str, Any] | pd.Series) -> List[str]:
    """Audit a paper's metadata for methodology bias risks.

    Returns a list of flag strings describing potential issues.
    """
    flags: List[str] = []

    # Sample size risk
    n = row.get("sample_size", 0)
    try:
        n = float(n)
        if pd.isna(n) or n <= 0:
            flags.append("❓ Unreported Cohort Size")
        elif n < 100:
            flags.append(f"⚠️ Low Statistical Power (N={int(n)})")
    except Exception:
        flags.append("❓ Unreported Cohort Size")

    # Design risk
    design = str(row.get("study_design", "")).lower()
    if "review" in design or "editorial" in design or "commentary" in design:
        flags.append("⚠️ Low Primary Evidence (Review/Commentary)")
    elif "undetermined" in design or "default" in design:
        flags.append("❓ Unspecified Design Quality")

    # Methodological bias keywords
    abstract = str(row.get("abstract", "")).lower()
    title = str(row.get("title", "")).lower()
    if "retrospective" in abstract or "retrospective" in title:
        flags.append("⚠️ Retrospective Recall Bias")
    if "open-label" in abstract or "open-label" in title:
        flags.append("⚠️ Open-Label Bias Risk")
    if "uncontrolled" in abstract or "uncontrolled" in title:
        flags.append("⚠️ Uncontrolled Cohort")
    if "pilot" in abstract or "pilot" in title:
        flags.append("ℹ️ Pilot Feasibility Study")

    return flags


def get_ollama_model_names() -> List[str]:
    """Fetch installed Ollama model names, handling both dict and object API formats."""
    try:
        import ollama
        model_list = ollama.list()
        names: List[str] = []
        if isinstance(model_list, dict) and "models" in model_list:
            for m in model_list["models"]:
                if isinstance(m, dict):
                    if "model" in m:
                        names.append(m["model"])
                    elif "name" in m:
                        names.append(m["name"])
                elif hasattr(m, "model"):
                    names.append(m.model)
                elif hasattr(m, "name"):
                    names.append(m.name)
        elif hasattr(model_list, "models"):
            names = [m.model for m in model_list.models]

        # Ensure common targets are in the list
        for target in ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest"]:
            if target not in names:
                names.append(target)

        if not names:
            return ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest", "llama3.1:8b",
                    "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]
        return names
    except Exception:
        return ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest", "llama3.1:8b",
                "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]


def get_gemini_model_names(api_key: str) -> List[str]:
    """Fetch available Gemini models from Google API."""
    default = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-pro-latest", "gemini-1.5-flash-latest"]
    if not api_key:
        return default
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        valid_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name.replace('models/', ''))
        return valid_models if valid_models else default[:2]
    except Exception:
        return default


def safe_clean_query(raw_query: str) -> str:
    """Simple regex-based query cleaning fallback (no LLM needed)."""
    cleaned = re.sub(r'\(.*?\)', ' ', raw_query)
    cleaned = re.sub(r'[^\w\s-]', ' ', cleaned)
    return ' '.join(cleaned.split())
