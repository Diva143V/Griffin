import os
import json
import ast
import time
import pandas as pd
import numpy as np
import streamlit as st
import ollama
from sentence_transformers import SentenceTransformer
from src.shared.llm import chat as llm_chat
from src.core import graph_rag
from src.agents.query_planner import build_query_plan, execute_query_plan, plan_to_dict
from src.agents.report_agent import generate_overseer_report
from src.agents.validation_agent import run_qa_audit
from src.agents.refinement_agent import refine_report_section
from src.agents.peer_review_agent import run_peer_review

def run_with_stop_button(func, *args, in_sidebar=False, show_terminal=False, **kwargs):
    import threading
    import time
    
    res_container = {"done": False, "result": None, "error": None, "stopped": False}
    stop_event = threading.Event()
    kwargs["stop_event"] = stop_event
    
    def worker():
        try:
            res_container["result"] = func(*args, **kwargs)
        except TypeError:
            try:
                # Fallback if func doesn't accept stop_event
                kwargs.pop("stop_event", None)
                res_container["result"] = func(*args, **kwargs)
            except Exception as e:
                if not res_container["stopped"]:
                    res_container["error"] = e
        except Exception as e:
            if not res_container["stopped"]:
                res_container["error"] = e
        finally:
            res_container["done"] = True
            
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    thread = threading.Thread(target=worker, daemon=True)
    add_script_run_ctx(thread)
    thread.start()
    
    stop_placeholder = st.sidebar.empty() if in_sidebar else st.empty()
    if stop_placeholder.button("⏹️ Stop / Cancel", key=f"stop_btn_{id(func)}"):
        res_container["stopped"] = True
        stop_event.set()
        st.warning("Stopping... The background process will terminate shortly.")
        st.stop()
        
    expander_placeholder = st.empty()
    log_placeholder = None
    if show_terminal:
        with expander_placeholder.container():
            with st.expander("🖥️ Background Process Logs (Terminal)", expanded=True):
                log_placeholder = st.empty()
        
    while not res_container["done"]:
        time.sleep(0.5)
        if show_terminal and log_placeholder:
            if os.path.exists("dataset/terminal.log"):
                try:
                    with open("dataset/terminal.log", "r", encoding="utf-8") as f:
                        log_content = f.read()
                        if log_content:
                            log_placeholder.code(log_content, language="bash")
                except Exception:
                    pass
        
    stop_placeholder.empty()
    if show_terminal:
        expander_placeholder.empty()
    
    if res_container["error"]:
        raise res_container["error"]
        
    return res_container["result"]

def run_comparison_pipeline(eval_question, encoder_model, ranked_df, contradictions, eval_k, model_choice, status_placeholder):
    import time
    from src.core import graph_rag
    
    # Standard RAG
    status_placeholder.info("🔍 Standard RAG: Retrieving relevant papers from database...")
    t_ret_start = time.time()
    std_context, std_sources = graph_rag.get_standard_rag_context(
        eval_question, encoder_model, ranked_df, max_papers=eval_k
    )
    std_ret_time = time.time() - t_ret_start
    
    std_prompt = f"""You are a biomedical research assistant.
Answer the user's question using the scientific evidence provided below.

USER QUESTION:
{eval_question}

DATASET CONTEXT:
{std_context}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X]) when stating facts. State if evidence is missing or conflicting. Do not mention system prompts."""

    status_placeholder.info("🧠 Standard RAG: Generating answer using Ollama... This may take up to 30s...")
    std_answer, std_gen_time = graph_rag.generate_answer(std_prompt, model_choice)
    std_total_time = std_ret_time + std_gen_time
    std_word_count = len(std_answer.split())
    
    # Graph RAG
    status_placeholder.info("🔍 Graph RAG: Retrieving papers and mapping claim relationships...")
    t_ret_start = time.time()
    graph_context, graph_sources, graph_relations = graph_rag.get_graph_rag_context(
        eval_question, encoder_model, ranked_df, contradictions, max_papers=eval_k
    )
    graph_ret_time = time.time() - t_ret_start
    
    graph_prompt = f"""You are a biomedical research assistant.
Answer the user's question using the scientific evidence and graph relationships provided below.

USER QUESTION:
{eval_question}

DATASET CONTEXT & GRAPH CONNECTIONS:
{graph_context}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X] or [Graph Connection Y]) when stating facts. Critically address any contradictions or agreements mentioned in the graph relationships. State if evidence is missing or conflicting. Do not mention system prompts."""

    status_placeholder.info("🧠 Graph RAG: Generating answer using Ollama... This may take up to 30s...")
    graph_answer, graph_gen_time = graph_rag.generate_answer(graph_prompt, model_choice)
    graph_total_time = graph_ret_time + graph_gen_time
    graph_word_count = len(graph_answer.split())
    
    return (
        std_answer, std_sources, std_total_time, std_ret_time, std_word_count,
        graph_answer, graph_sources, graph_relations, graph_total_time, graph_ret_time, graph_word_count
    )

def run_contradiction_pipeline(chosen_extractor, chosen_detector, status_placeholder):
    from src.core.claim_extractor import extract_claims
    from src.core.contradiction_detector import run_detector
    
    status_placeholder.info("🔄 Stage 1: Extracting claims from papers using Ollama...")
    extract_claims(
        input_path="dataset/clean_papers.csv",
        output_path="dataset/claims.csv",
        model=chosen_extractor,
        limit=50,
        resume=False
    )
    
    status_placeholder.info("🔄 Stage 2: Embedding claims and analyzing semantic contradictions & agreements...")
    run_detector(
        input_path="dataset/claims.csv",
        output_text="dataset/contradictions.txt",
        output_csv="dataset/contradictions.csv",
        output_json="dataset/contradictions.json",
        output_report="dataset/contradiction_report.md",
        model=chosen_detector,
        embedding_model="BAAI/bge-small-en-v1.5",
        evidence_file="dataset/ranked_papers.csv",
        max_pairs=20,
        similarity_threshold=0.45,
        skip_embeddings=False
    )

@st.cache_resource(ttl=60)

def get_ollama_models():
    try:
        model_list = ollama.list()
        names = []
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
            
        target = "gemma4:e4b"
        if target not in names:
            names.append(target)
        target_biollm = "koesn/llama3-openbiollm-8b:latest"
        if target_biollm not in names:
            names.append(target_biollm)
        if not names:
            return ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]
        return names
    except Exception:
        return ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]

# Set page config for a clean, professional dashboard
st.set_page_config(
    page_title="Griffin Bio – Scientific Synthesis & Contradiction Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern premium styling — fonts, spacing, animations
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
    /* ── Keyframe Animations ─────────────────────────────────────── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(14px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-12px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes softPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.35); }
        50%      { box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
    }
    @keyframes shimmer {
        0%   { background-position: -200% 0; }
        100% { background-position:  200% 0; }
    }
    @keyframes glowBorder {
        0%, 100% { border-color: rgba(99, 102, 241, 0.35); }
        50%      { border-color: rgba(129, 140, 248, 0.7); }
    }
    @keyframes floatY {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-3px); }
    }
    @keyframes tabUnderline {
        from { transform: scaleX(0); }
        to   { transform: scaleX(1); }
    }

    /* ── CSS Variables ───────────────────────────────────────────── */
    :root {
        --gx-bg-0: #070a12;
        --gx-bg-1: #0b1020;
        --gx-bg-2: #111827;
        --gx-bg-3: #1a2236;
        --gx-border: rgba(148, 163, 184, 0.14);
        --gx-border-strong: rgba(148, 163, 184, 0.28);
        --gx-text: #e8eef9;
        --gx-text-muted: #94a3b8;
        --gx-accent: #818cf8;
        --gx-accent-2: #38bdf8;
        --gx-accent-deep: #6366f1;
        --gx-success: #34d399;
        --gx-warn: #fbbf24;
        --gx-danger: #f87171;
        --gx-radius-sm: 10px;
        --gx-radius-md: 14px;
        --gx-radius-lg: 18px;
        --gx-radius-xl: 22px;
        --gx-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
        --gx-shadow-glow: 0 8px 40px rgba(99, 102, 241, 0.18);
        --gx-font: 'DM Sans', system-ui, -apple-system, sans-serif;
        --gx-font-display: 'Outfit', 'DM Sans', system-ui, sans-serif;
        --gx-font-mono: 'JetBrains Mono', ui-monospace, monospace;
        --gx-ease: cubic-bezier(0.22, 1, 0.36, 1);
    }

    /* ── Global Base ─────────────────────────────────────────────── */
    .stApp {
        background:
            radial-gradient(ellipse 80% 50% at 20% -10%, rgba(99, 102, 241, 0.16) 0%, transparent 55%),
            radial-gradient(ellipse 60% 40% at 90% 10%, rgba(56, 189, 248, 0.10) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 50% 100%, rgba(129, 140, 248, 0.06) 0%, transparent 60%),
            linear-gradient(180deg, var(--gx-bg-0) 0%, var(--gx-bg-1) 100%) !important;
        color: var(--gx-text);
        font-family: var(--gx-font);
        font-size: 15.5px;
        letter-spacing: 0.01em;
    }

    html, body, [class*="css"],
    .stMarkdown, .stText, p, span, label, div {
        font-family: var(--gx-font) !important;
        color: var(--gx-text);
    }

    /* Subtle page entrance */
    .main .block-container {
        animation: fadeInUp 0.55s var(--gx-ease) both;
        padding-top: 2.25rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        max-width: 1280px;
    }

    /* ── Headings ────────────────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 {
        font-family: var(--gx-font-display) !important;
        color: #f8fafc !important;
        letter-spacing: -0.03em !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
    }

    h1 {
        font-size: 2.65rem !important;
        font-weight: 800 !important;
        background: linear-gradient(120deg, #e0e7ff 0%, #818cf8 40%, #38bdf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.35rem !important;
        animation: fadeInUp 0.6s var(--gx-ease) both;
    }

    h2 {
        font-size: 1.75rem !important;
        border-bottom: 1px solid var(--gx-border);
        padding-bottom: 12px !important;
        margin-top: 28px !important;
        margin-bottom: 18px !important;
    }

    h3 {
        font-size: 1.35rem !important;
        color: var(--gx-accent) !important;
        -webkit-text-fill-color: var(--gx-accent) !important;
        background: none !important;
        margin-top: 8px !important;
        margin-bottom: 12px !important;
    }

    h4, h5 {
        font-size: 1.05rem !important;
        color: #cbd5e1 !important;
        -webkit-text-fill-color: #cbd5e1 !important;
        background: none !important;
        font-weight: 600 !important;
    }

    p, span, div, li {
        line-height: 1.72 !important;
    }

    /* Captions / muted */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--gx-text-muted) !important;
        font-size: 0.92rem !important;
        letter-spacing: 0.01em;
        animation: fadeIn 0.7s var(--gx-ease) both;
    }

    /* ── Premium Cards ───────────────────────────────────────────── */
    .card, [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(17, 24, 39, 0.85) 0%, rgba(11, 16, 32, 0.75) 100%) !important;
        backdrop-filter: blur(16px) saturate(140%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(140%) !important;
        border: 1px solid var(--gx-border) !important;
        border-radius: var(--gx-radius-lg) !important;
        padding: 22px 24px !important;
        margin-bottom: 18px;
        box-shadow: var(--gx-shadow);
        transition: transform 0.35s var(--gx-ease), box-shadow 0.35s var(--gx-ease), border-color 0.35s ease;
        animation: fadeInUp 0.5s var(--gx-ease) both;
    }

    .card:hover {
        border-color: rgba(129, 140, 248, 0.45) !important;
        box-shadow: var(--gx-shadow-glow);
        transform: translateY(-4px);
    }

    /* Staggered card delay helpers */
    .card:nth-child(1) { animation-delay: 0.05s; }
    .card:nth-child(2) { animation-delay: 0.12s; }
    .card:nth-child(3) { animation-delay: 0.18s; }

    /* ── Badges ──────────────────────────────────────────────────── */
    .badge {
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        display: inline-block;
        border: 1px solid transparent;
        transition: transform 0.2s var(--gx-ease), box-shadow 0.2s ease;
    }
    .badge:hover {
        transform: translateY(-1px);
    }

    /* ── Metrics ─────────────────────────────────────────────────── */
    [data-testid="stMetricValue"] {
        font-family: var(--gx-font-display) !important;
        font-size: 2.15rem !important;
        font-weight: 700 !important;
        color: var(--gx-accent) !important;
        padding: 14px 18px !important;
        background: linear-gradient(145deg, rgba(30, 27, 75, 0.45) 0%, rgba(15, 23, 42, 0.7) 100%) !important;
        border-radius: var(--gx-radius-md) !important;
        border: 1px solid rgba(129, 140, 248, 0.2) !important;
        transition: transform 0.3s var(--gx-ease), box-shadow 0.3s ease;
    }

    [data-testid="stMetric"]:hover [data-testid="stMetricValue"] {
        transform: scale(1.03);
        box-shadow: 0 0 24px rgba(99, 102, 241, 0.2);
    }

    [data-testid="stMetricLabel"] {
        font-family: var(--gx-font) !important;
        font-size: 0.78rem !important;
        color: var(--gx-text-muted) !important;
        text-transform: uppercase !important;
        letter-spacing: 1.6px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }

    /* ── Sidebar ─────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, rgba(11, 16, 32, 0.98) 0%, rgba(7, 10, 18, 0.99) 100%) !important;
        border-right: 1px solid var(--gx-border) !important;
        min-width: 320px !important;
        animation: slideInLeft 0.45s var(--gx-ease) both;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding: 1.4rem 1.15rem 2rem !important;
    }

    [data-testid="stSidebar"] * {
        color: #e2e8f0;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-family: var(--gx-font-display) !important;
        letter-spacing: -0.02em !important;
    }

    [data-testid="stSidebar"] .stMarkdown h3 {
        font-size: 0.95rem !important;
        color: var(--gx-accent) !important;
        -webkit-text-fill-color: var(--gx-accent) !important;
        text-transform: uppercase;
        letter-spacing: 0.08em !important;
        margin-top: 0.5rem !important;
    }

    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.55rem !important;
    }

    /* ── Tabs (main + nested) ────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        margin-bottom: 28px;
        padding: 6px;
        border-bottom: none !important;
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid var(--gx-border);
        border-radius: var(--gx-radius-xl);
        backdrop-filter: blur(12px);
        flex-wrap: wrap;
        row-gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 999px !important;
        padding: 12px 20px !important;
        min-height: 44px !important;
        color: var(--gx-text-muted) !important;
        font-weight: 500 !important;
        font-size: 0.92rem !important;
        font-family: var(--gx-font) !important;
        letter-spacing: 0.01em;
        transition: all 0.28s var(--gx-ease) !important;
        position: relative;
        overflow: hidden;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(129, 140, 248, 0.10) !important;
        color: #f1f5f9 !important;
        transform: translateY(-1px);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.28) 0%, rgba(56, 189, 248, 0.18) 100%) !important;
        border: 1px solid rgba(129, 140, 248, 0.45) !important;
        color: #eef2ff !important;
        font-weight: 650 !important;
        box-shadow: 0 4px 18px rgba(99, 102, 241, 0.22);
    }

    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        animation: fadeInUp 0.4s var(--gx-ease) both;
        padding-top: 4px;
    }

    /* Nested subtabs slightly smaller */
    .stTabs .stTabs [data-baseweb="tab"] {
        padding: 9px 16px !important;
        min-height: 38px !important;
        font-size: 0.86rem !important;
    }

    .stTabs .stTabs [data-baseweb="tab-list"] {
        margin-bottom: 18px;
        padding: 4px;
        border-radius: var(--gx-radius-lg);
    }

    /* ── Expanders ───────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--gx-border) !important;
        border-radius: var(--gx-radius-md) !important;
        background: rgba(15, 23, 42, 0.45) !important;
        margin-bottom: 12px !important;
        overflow: hidden;
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
        animation: fadeInUp 0.45s var(--gx-ease) both;
    }

    [data-testid="stExpander"]:hover {
        border-color: rgba(129, 140, 248, 0.35) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }

    .streamlit-expanderHeader,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details summary {
        background: transparent !important;
        border: none !important;
        border-radius: var(--gx-radius-md) !important;
        padding: 14px 18px !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-family: var(--gx-font-display) !important;
        font-size: 0.95rem !important;
        letter-spacing: -0.01em;
        transition: background 0.2s ease;
    }

    .streamlit-expanderHeader:hover,
    [data-testid="stExpander"] summary:hover {
        background: rgba(129, 140, 248, 0.08) !important;
    }

    .streamlit-expanderContent,
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background: rgba(7, 10, 18, 0.35) !important;
        border-top: 1px solid var(--gx-border) !important;
        padding: 16px 18px !important;
        animation: fadeIn 0.3s ease both;
    }

    /* ── DataFrames / Tables ─────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: var(--gx-radius-md) !important;
        overflow: hidden;
        border: 1px solid var(--gx-border) !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
        animation: fadeInUp 0.45s var(--gx-ease) both;
    }

    [data-testid="stDataFrame"] > div {
        background: rgba(15, 23, 42, 0.6) !important;
    }

    /* ── Inputs ──────────────────────────────────────────────────── */
    .stTextInput input,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div,
    .stTextArea textarea,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] {
        border-radius: var(--gx-radius-sm) !important;
        border: 1px solid var(--gx-border-strong) !important;
        background-color: rgba(7, 10, 18, 0.75) !important;
        color: var(--gx-text) !important;
        font-family: var(--gx-font) !important;
        font-size: 0.95rem !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
        min-height: 42px !important;
        transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
    }

    .stTextArea textarea {
        min-height: 96px !important;
        line-height: 1.6 !important;
        padding: 12px 14px !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stNumberInput input:focus {
        border-color: var(--gx-accent) !important;
        box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.22) !important;
        outline: none !important;
    }

    /* Labels */
    .stTextInput label,
    .stSelectbox label,
    .stTextArea label,
    .stNumberInput label,
    .stSlider label,
    .stMultiSelect label {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #cbd5e1 !important;
        letter-spacing: 0.01em !important;
        margin-bottom: 6px !important;
    }

    /* ── Buttons ─────────────────────────────────────────────────── */
    .stButton button {
        border-radius: 12px !important;
        font-family: var(--gx-font-display) !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 10px 22px !important;
        min-height: 44px !important;
        letter-spacing: 0.01em;
        transition: all 0.28s var(--gx-ease) !important;
        border: 1px solid var(--gx-border-strong) !important;
        background: rgba(30, 41, 59, 0.7) !important;
        color: #e2e8f0 !important;
    }

    .stButton button:hover {
        transform: translateY(-2px) !important;
        border-color: rgba(129, 140, 248, 0.5) !important;
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.28) !important;
        background: rgba(51, 65, 85, 0.85) !important;
    }

    .stButton button:active {
        transform: translateY(0) scale(0.98) !important;
    }

    .stButton button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 50%, #2563eb 100%) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.38) !important;
        position: relative;
        overflow: hidden;
    }

    .stButton button[kind="primary"]::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(110deg, transparent 20%, rgba(255,255,255,0.18) 45%, transparent 70%);
        background-size: 200% 100%;
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .stButton button[kind="primary"]:hover {
        box-shadow: 0 10px 28px rgba(99, 102, 241, 0.5) !important;
        transform: translateY(-2px) !important;
        filter: brightness(1.06);
    }

    .stButton button[kind="primary"]:hover::after {
        opacity: 1;
        animation: shimmer 1.4s linear infinite;
    }

    /* ── Toggles / Checkboxes / Sliders ──────────────────────────── */
    [data-testid="stCheckbox"],
    [data-testid="stWidgetLabel"] {
        font-size: 0.9rem !important;
    }

    .stSlider > div[data-baseweb="slider"] {
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }

    /* ── Alerts / Info boxes ─────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: var(--gx-radius-md) !important;
        border: 1px solid var(--gx-border) !important;
        backdrop-filter: blur(8px);
        animation: fadeInUp 0.4s var(--gx-ease) both;
        padding: 14px 16px !important;
    }

    /* ── Chat messages ───────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        border-radius: var(--gx-radius-md) !important;
        border: 1px solid var(--gx-border);
        background: rgba(15, 23, 42, 0.55) !important;
        margin-bottom: 10px !important;
        padding: 12px 14px !important;
        animation: fadeInUp 0.35s var(--gx-ease) both;
        transition: border-color 0.2s ease;
    }

    [data-testid="stChatMessage"]:hover {
        border-color: rgba(129, 140, 248, 0.3);
    }

    /* ── Dividers ────────────────────────────────────────────────── */
    hr, [data-testid="stMarkdownContainer"] hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--gx-border-strong), transparent) !important;
        margin: 1.4rem 0 !important;
    }

    /* ── Code ────────────────────────────────────────────────────── */
    code, .stCode, pre {
        font-family: var(--gx-font-mono) !important;
        font-size: 0.86rem !important;
    }

    code {
        background-color: rgba(30, 41, 59, 0.9) !important;
        border-radius: 6px;
        padding: 2px 7px;
        color: #fca5a5 !important;
        border: 1px solid rgba(248, 113, 113, 0.15);
    }

    pre, .stCodeBlock {
        border-radius: var(--gx-radius-md) !important;
        border: 1px solid var(--gx-border) !important;
        background: rgba(7, 10, 18, 0.85) !important;
    }

    /* ── Progress / Spinners ─────────────────────────────────────── */
    .stSpinner > div {
        border-top-color: var(--gx-accent) !important;
    }

    [data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #6366f1, #38bdf8) !important;
        border-radius: 999px !important;
    }

    /* ── Dialog / Modal ──────────────────────────────────────────── */
    [data-testid="stModal"] > div,
    div[role="dialog"] {
        border-radius: var(--gx-radius-xl) !important;
        border: 1px solid rgba(129, 140, 248, 0.25) !important;
        background: linear-gradient(160deg, #111827 0%, #0b1020 100%) !important;
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(129, 140, 248, 0.1) !important;
        animation: fadeInUp 0.35s var(--gx-ease) both;
        padding: 1.5rem !important;
    }

    /* ── Scrollbars ──────────────────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.45);
        border-radius: 999px;
        border: 2px solid transparent;
        background-clip: padding-box;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(129, 140, 248, 0.55);
        background-clip: padding-box;
        border: 2px solid transparent;
    }

    /* ── Layer legend chips (pipeline) ───────────────────────────── */
    .gx-chip {
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        border: 1px solid;
        transition: transform 0.22s var(--gx-ease), box-shadow 0.22s ease;
        animation: fadeInUp 0.45s var(--gx-ease) both;
        cursor: default;
    }
    .gx-chip:hover {
        transform: translateY(-2px) scale(1.03);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
    }

    /* ── Utility: pulse primary CTA subtly ───────────────────────── */
    .stButton button[kind="primary"] {
        animation: softPulse 2.8s ease-in-out infinite;
    }

    /* Reduce motion for accessibility */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }

    /* ── Selection highlight ─────────────────────────────────────── */
    ::selection {
        background: rgba(129, 140, 248, 0.35);
        color: #fff;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar - Settings & Actions
st.sidebar.title("🧬 Griffin Bio Controls")
st.sidebar.markdown("---")

DATASET_DIR = "dataset"
CLINICAL_PAPERS_PATH = os.path.join(DATASET_DIR, "ranked_papers.csv")
CLAIMS_PATH = os.path.join(DATASET_DIR, "claims.csv")
CONTRADICTION_PATH = os.path.join(DATASET_DIR, "contradictions.json")
SYNTHESIS_PATH = os.path.join(DATASET_DIR, "final_synthesis.md")
EMBEDDINGS_PATH = os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv")

def parse_embedding(value):
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
    return np.asarray(value, dtype=np.float32)

def pick_claim_text(row):
    for column in ("claim_output", "llm_output", "claim"):
        if column in row.index:
            value = str(row.get(column, "") or "").strip()
            if value:
                return value
    return ""

@st.cache_resource
def load_encoder_model():
    return SentenceTransformer("BAAI/bge-small-en-v1.5")

def format_reasoning_text(text: str, mode: str) -> str:
    """Format and separate reasoning (<think>...</think>) block from main text."""
    if not text:
        return ""
        
    import re
    # Extract everything between <think> and </think> tags
    think_match = re.search(r'<think>(.*?)</think>', text, re.DOTALL)
    
    if think_match:
        think_content = think_match.group(1).strip()
        # Remove the <think>...</think> block from the main text
        clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        
        if mode == "Display in Expander":
            with st.expander("💭 Show Reasoning Chain", expanded=False):
                st.markdown(think_content)
            return clean_text
        elif mode == "Strip Completely":
            return clean_text
        else: # Raw Text
            return text
            
    return text

# Load existing datasets safely
def load_data():
    ranked_df = pd.read_csv(CLINICAL_PAPERS_PATH) if os.path.exists(CLINICAL_PAPERS_PATH) else None
    claims_df = pd.read_csv(CLAIMS_PATH) if os.path.exists(CLAIMS_PATH) else None

    if ranked_df is not None:
        if "evidence_score" not in ranked_df.columns:
            ranked_df["evidence_score"] = 5.0
        if "sample_size" not in ranked_df.columns:
            ranked_df["sample_size"] = 0
        if "study_design" not in ranked_df.columns:
            ranked_df["study_design"] = "Undetermined"

    if claims_df is not None:
        if "claim" not in claims_df.columns:
            claims_df["claim"] = ""

    # Merge embeddings into ranked_df
    if ranked_df is not None and os.path.exists(EMBEDDINGS_PATH):
        try:
            emb_df = pd.read_csv(EMBEDDINGS_PATH)
            ranked_df["title_clean"] = ranked_df["title"].fillna("").astype(str).str.strip().str.lower()
            emb_df["title_clean"] = emb_df["title"].fillna("").astype(str).str.strip().str.lower()
            
            emb_df_subset = emb_df[["title_clean", "embedding"]].drop_duplicates(subset=["title_clean"])
            
            ranked_df = pd.merge(ranked_df, emb_df_subset, on="title_clean", how="left")
            ranked_df = ranked_df.drop(columns=["title_clean"])
            
            # Find embedding dimension to use as a fallback zero vector
            emb_dim = 384
            valid_emb = emb_df["embedding"].dropna().iloc[0] if not emb_df["embedding"].dropna().empty else None
            if valid_emb:
                try:
                    parsed_val = parse_embedding(valid_emb)
                    emb_dim = parsed_val.shape[0]
                except Exception:
                    pass
            
            zero_vec = [0.0] * emb_dim
            ranked_df["embedding"] = ranked_df["embedding"].apply(
                lambda x: parse_embedding(x) if pd.notna(x) else np.array(zero_vec, dtype=np.float32)
            )
        except Exception as e:
            st.error(f"Error merging embeddings: {e}")

    contradictions = {}
    if os.path.exists(CONTRADICTION_PATH):
        try:
            with open(CONTRADICTION_PATH, "r", encoding="utf-8") as f:
                contradictions = json.load(f)
        except Exception:
            pass

    synthesis_text = ""
    consensus_path = os.path.join(DATASET_DIR, "consensus_report.md")
    if os.path.exists(consensus_path):
        try:
            with open(consensus_path, "r", encoding="utf-8") as f:
                synthesis_text = f.read()
        except Exception:
            pass
            
    if not synthesis_text and os.path.exists(SYNTHESIS_PATH):
        try:
            with open(SYNTHESIS_PATH, "r", encoding="utf-8") as f:
                synthesis_text = f.read()
        except Exception:
            pass

    return ranked_df, claims_df, contradictions, synthesis_text


def render_network_graph(contradictions_dict):
    """Render an interactive Vis.js network graph of scientific claims and relations."""
    if not isinstance(contradictions_dict, dict) or not contradictions_dict:
        return
        
    all_relations = []
    all_relations.extend([dict(r, type="contradiction") for r in contradictions_dict.get("contradictions", [])])
    all_relations.extend([dict(r, type="agreement") for r in contradictions_dict.get("agreements", [])])
    all_relations.extend([dict(r, type="partial_agreement") for r in contradictions_dict.get("partial_agreements", [])])
    
    if not all_relations:
        return
        
    nodes_map = {}
    nodes_list = []
    edges_list = []
    node_id_counter = 0
    
    for r in all_relations:
        t_a = r.get("claim_a_title", "")
        t_b = r.get("claim_b_title", "")
        c_a = r.get("claim_a_text", "")
        c_b = r.get("claim_b_text", "")
        
        if not t_a or not t_b:
            continue
            
        # Register node A
        if t_a not in nodes_map:
            node_id_counter += 1
            nodes_map[t_a] = node_id_counter
            lbl = f"Paper {node_id_counter}"
            nodes_list.append({
                "id": node_id_counter,
                "label": lbl,
                "title": f"<b>Paper:</b> {t_a}<br><br><b>Claim:</b> {c_a}",
                "color": {
                    "background": "#0b1020",
                    "border": "#818cf8",
                    "highlight": {"background": "#6366f1", "border": "#e0e7ff"}
                }
            })
            
        # Register node B
        if t_b not in nodes_map:
            node_id_counter += 1
            nodes_map[t_b] = node_id_counter
            lbl = f"Paper {node_id_counter}"
            nodes_list.append({
                "id": node_id_counter,
                "label": lbl,
                "title": f"<b>Paper:</b> {t_b}<br><br><b>Claim:</b> {c_b}",
                "color": {
                    "background": "#0b1020",
                    "border": "#818cf8",
                    "highlight": {"background": "#6366f1", "border": "#e0e7ff"}
                }
            })
            
        rel_type = r.get("type", "")
        if rel_type == "contradiction":
            color = "#ef4444" # Red
            label = "Contradicts"
            width = 3
        elif rel_type == "agreement":
            color = "#10b981" # Green
            label = "Agrees"
            width = 3
        else:
            color = "#f59e0b" # Orange
            label = "Partial"
            width = 2
            
        edges_list.append({
            "from": nodes_map[t_a],
            "to": nodes_map[t_b],
            "label": label,
            "color": color,
            "width": width,
            "font": {"color": "#94a3b8", "size": 10, "strokeWidth": 0, "face": "DM Sans, sans-serif"}
        })

    nodes_json = json.dumps(nodes_list)
    edges_json = json.dumps(edges_list)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
        <style type="text/css">
            html, body {{
                margin: 0;
                padding: 0;
                background-color: #070a12;
                overflow: hidden;
                font-family: 'DM Sans', system-ui, sans-serif;
            }}
            #mynetwork {{
                width: 100%;
                height: 420px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 18px;
                background:
                    radial-gradient(ellipse 70% 50% at 30% 20%, rgba(99,102,241,0.12) 0%, transparent 55%),
                    #070a12;
            }}
            div.vis-tooltip {{
                position: absolute;
                visibility: hidden;
                padding: 14px 16px;
                white-space: pre-wrap;
                background-color: rgba(15, 23, 42, 0.96);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(129, 140, 248, 0.28);
                border-radius: 12px;
                color: #e2e8f0;
                font-family: 'DM Sans', system-ui, sans-serif;
                font-size: 12px;
                line-height: 1.55;
                box-shadow: 0 12px 32px rgba(0,0,0,0.55);
                max-width: 340px;
            }}
        </style>
    </head>
    <body>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});
        var container = document.getElementById('mynetwork');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            nodes: {{
                shape: 'dot',
                size: 18,
                font: {{ color: '#e2e8f0', size: 12, face: 'DM Sans, sans-serif' }},
                borderWidth: 2,
                shadow: {{ enabled: true, color: 'rgba(99,102,241,0.35)', size: 14, x: 0, y: 4 }}
            }},
            edges: {{
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.55 }} }},
                font: {{ align: 'middle', face: 'DM Sans, sans-serif', size: 10, color: '#94a3b8' }},
                smooth: {{ type: 'cubicBezier', forceDirection: 'none', roundness: 0.4 }}
            }},
            physics: {{
                stabilization: true,
                barnesHut: {{ gravitationalConstant: -4000, centralGravity: 0.15, springLength: 180 }}
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
    </body>
    </html>
    """
    import streamlit.components.v1 as components
    st.markdown("##### 🌐 Visual Claim Dispute Map")
    components.html(html_content, height=430)

def audit_methodology(row):
    """Audit the paper's abstract, title, and metadata for methodology bias risks."""
    flags = []
    
    # 1. Sample size risk
    n = row.get("sample_size", 0)
    if pd.isna(n) or n <= 0:
        flags.append("❓ Unreported Cohort Size")
    elif n < 100:
        flags.append(f"⚠️ Low Statistical Power (N={int(n)})")
        
    # 2. Design risk
    design = str(row.get("study_design", "")).lower()
    if "review" in design or "editorial" in design or "commentary" in design:
        flags.append("⚠️ Low Primary Evidence (Review/Commentary)")
    elif "undetermined" in design or "default" in design:
        flags.append("❓ Unspecified Design Quality")
        
    # 3. Methodological bias keywords check
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


if "execution" not in st.session_state:
    st.session_state.execution = None

ranked_df, claims_df, contradictions, synthesis_text = load_data()
encoder_model = load_encoder_model()
installed_models = get_ollama_models()
model_choice = installed_models[0] if installed_models else "koesn/llama3-openbiollm-8b:latest"

# Credentials Settings Sidebar Block
st.sidebar.subheader("🔑 Credentials & Settings")
pubmed_email = st.sidebar.text_input(
    "PubMed / Entrez Email:",
    value="test@example.com",
    help="Required for Entrez API requests to PubMed/PMC.",
    key="pubmed_email_input"
)
sc_api_key = st.sidebar.text_input(
    "Semantic Scholar API Key:",
    value="",
    type="password",
    help="Optional, unlocks Semantic Scholar searches.",
    key="sc_api_key_input"
)
google_api_key = st.sidebar.text_input(
    "Google API Key (Gemini):",
    value="",
    type="password",
    help="Required for Grounded Overseer Report and Peer Review capabilities.",
    key="google_api_key_input"
)

@st.cache_data(show_spinner=False, ttl=300)
def get_gemini_models(api_key):
    fallback_models = ["gemini-2.5-flash", "gemini-2.5-pro"]

    if not api_key:
        return fallback_models

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        valid_models = []
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                valid_models.append(m.name.replace("models/", ""))

        # Prefer current Gemini 2.5 models at the top if available.
        preferred = [m for m in ["gemini-2.5-flash", "gemini-2.5-pro"] if m in valid_models]
        remaining = [m for m in valid_models if m not in preferred]

        return preferred + remaining if valid_models else fallback_models

    except Exception:
        return fallback_models

gemini_model_list = get_gemini_models(google_api_key)
gemini_model_choice = st.sidebar.selectbox(
    "Gemini Model (for Overseer/Review):",
    gemini_model_list,
    index=0,
    key="gemini_model_choice"
)
# LLM Model Routing block
st.sidebar.subheader("🤖 LLM Model Routing")
use_global_model = st.sidebar.toggle(
    "Global Model ",
    value=False,
    help="Toggle ON to enforce a single global model for all agents and tasks, or OFF to use customized routing/default mixtures."
)

model_routing = {}
if use_global_model:
    global_model_choice = st.sidebar.selectbox(
        "Select Global Model:",
        installed_models,
        index=0,
        key="global_model_select"
    )
    model_routing = {
        "planner": global_model_choice,
        "claim_extractor": global_model_choice,
        "contradiction_detector": global_model_choice,
        "consensus_analyst": global_model_choice,
        "synthesis": global_model_choice,
        "experiment_planner": global_model_choice
    }
    model_choice = global_model_choice
else:
    use_custom_routing = st.sidebar.toggle(
        "Custom Specialist Routing",
        value=False,
        help="Toggle ON to manually assign specific models to pipeline stages, or OFF to use the default optimized mixture."
    )

    if use_custom_routing:
        st.sidebar.markdown("<small>Assign models to pipeline stages:</small>", unsafe_allow_html=True)
        model_routing["planner"] = st.sidebar.selectbox(
            "Query Planner / Router:",
            installed_models,
            index=installed_models.index("gemma3:4b") if "gemma3:4b" in installed_models else 0,
            key="route_planner"
        )
        model_routing["claim_extractor"] = st.sidebar.selectbox(
            "Claim Extractor Agent:",
            installed_models,
            index=installed_models.index("gemma3:4b") if "gemma3:4b" in installed_models else 0,
            key="route_claim_extractor"
        )
        model_routing["contradiction_detector"] = st.sidebar.selectbox(
            "Contradiction Detector:",
            installed_models,
            index=installed_models.index("qwen3.5:9b") if "qwen3.5:9b" in installed_models else 0,
            key="route_contradiction_detector"
        )
        model_routing["consensus_analyst"] = st.sidebar.selectbox(
            "Consensus Analyst:",
            installed_models,
            index=installed_models.index("koesn/llama3-openbiollm-8b:latest") if "koesn/llama3-openbiollm-8b:latest" in installed_models else 0,
            key="route_consensus_analyst"
        )
        model_routing["synthesis"] = st.sidebar.selectbox(
            "Synthesis / generator:",
            installed_models,
            index=installed_models.index("gemma3:4b") if "gemma3:4b" in installed_models else 0,
            key="route_synthesis"
        )
        model_routing["experiment_planner"] = st.sidebar.selectbox(
            "Protocol & ELN Agent:",
            installed_models,
            index=installed_models.index("gemma3:4b") if "gemma3:4b" in installed_models else 0,
            key="route_experiment_planner"
        )
    else:
        model_routing = {
            "planner": "llama3.1:8b",
            "claim_extractor": "llama3.1:8b",
            "contradiction_detector": "qwen3.5:9b",
            "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
            "synthesis": "llama3.1:8b",
            "experiment_planner": "llama3.1:8b"
        }

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ LLM Options")
with st.sidebar.expander("Ollama Generation Options", expanded=True):
    llm_temp = st.slider(
        "Temperature:", 
        min_value=0.0, 
        max_value=2.0, 
        value=0.7, 
        step=0.1, 
        key="llm_temperature",
        help="Controls the creativity and randomness of the model's outputs. Lower values (e.g., 0.2) are more focused and deterministic, while higher values (e.g., 1.2) encourage broader variety."
    )
    llm_num_ctx = st.selectbox(
        "Context Length (num_ctx):", 
        [2048, 4096, 8192, 16384, 32768, 65536], 
        index=2, 
        key="llm_num_ctx",
        help="Determines the size of the memory window (in tokens) assigned to the model. Larger context sizes allow the agent to evaluate more papers simultaneously but require more system RAM/VRAM."
    )
    llm_num_predict = st.select_slider(
        "Max output tokens (num_predict):",
        options=[1024, 2048, 4096, 8192],
        value=4096,
        key="llm_num_predict",
        help="Maximum number of tokens the model can generate. Higher values reduce truncation risk for long synthesis/consensus outputs."
    )
    llm_think = st.toggle(
        "Enable Thinking Mode (/set think)", 
        value=True, 
        key="llm_think",
        help="Forces reasoning models (like gemma4:e4b or DeepSeek-R1) to execute systematic thinking chains. Disable this if you want faster, direct answers without reasoning steps."
    )
    llm_reasoning_mode = st.selectbox(
        "Reasoning Log Output:",
        ["Display in Expander", "Strip Completely", "Raw Text"],
        index=0,
        key="llm_reasoning_mode",
        help="Governs how generated <think> tags are displayed in the dashboard: place them in a collapsible box, hide them completely for clean synthesis, or print them raw."
    )

st.session_state["llm_options"] = {
    "temperature": llm_temp,
    "num_ctx": llm_num_ctx,
    "num_predict": llm_num_predict,
}
st.session_state["reasoning_mode"] = llm_reasoning_mode

st.sidebar.markdown("---")

st.markdown("""
<div style="margin-bottom: 1.75rem; animation: fadeInUp 0.55s cubic-bezier(0.22,1,0.36,1) both;">
  <div style="display:inline-flex;align-items:center;gap:10px;padding:6px 14px;border-radius:999px;
              border:1px solid rgba(129,140,248,0.35);background:rgba(99,102,241,0.12);
              color:#c7d2fe;font-size:0.78rem;font-weight:600;letter-spacing:0.06em;
              text-transform:uppercase;margin-bottom:14px;">
    <span style="width:7px;height:7px;border-radius:50%;background:#818cf8;
                 box-shadow:0 0 10px #818cf8;display:inline-block;"></span>
    Multi-Agent Scientific Workbench
  </div>
</div>
""", unsafe_allow_html=True)

st.title("🧬 Griffin Bio Dashboard")
st.caption("Scientific evidence synthesis · contradiction detection · research exploration")

# 2. Main Tabs — pill-style with larger hit targets
tabs = st.tabs([
    "🧭  Query Planner",
    "📝  Synthesis",
    "⚡  Contradictions",
    "📚  Evidence",
    "🔎  Claims",
    "🤖  RAG Benchmark",
    "🧐  Overseer",
])

with tabs[0]:
    st.markdown("### 🧭 Query Planner")
    st.caption("Enter a question and walk the full workflow from query → verification before generating an answer.")

    layer_palette = {
        "input": {"border": "#7C3AED", "bg": "#151026", "text": "#E9D5FF"},
        "orchestration": {"border": "#0EA5E9", "bg": "#0E1D2B", "text": "#BAE6FD"},
        "retrieval": {"border": "#22C55E", "bg": "#0E2016", "text": "#BBF7D0"},
        "collector": {"border": "#F59E0B", "bg": "#2A1C0B", "text": "#FDE68A"},
        "processing": {"border": "#14B8A6", "bg": "#0E2220", "text": "#99F6E4"},
        "indexing": {"border": "#3B82F6", "bg": "#0E1A2F", "text": "#BFDBFE"},
        "execution": {"border": "#F97316", "bg": "#2A170B", "text": "#FDBA74"},
        "analysis": {"border": "#EF4444", "bg": "#2A0E12", "text": "#FECACA"},
        "output": {"border": "#A855F7", "bg": "#1F102A", "text": "#E9D5FF"},
    }

    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:10px 12px;margin:6px 0 22px;'>"
        "<span class='gx-chip' style='animation-delay:0.02s;border-color:#7C3AED;color:#E9D5FF;background:rgba(124,58,237,0.12);'>Input</span>"
        "<span class='gx-chip' style='animation-delay:0.06s;border-color:#0EA5E9;color:#BAE6FD;background:rgba(14,165,233,0.12);'>Orchestration</span>"
        "<span class='gx-chip' style='animation-delay:0.10s;border-color:#22C55E;color:#BBF7D0;background:rgba(34,197,94,0.12);'>Retrieval</span>"
        "<span class='gx-chip' style='animation-delay:0.14s;border-color:#F59E0B;color:#FDE68A;background:rgba(245,158,11,0.12);'>Collector</span>"
        "<span class='gx-chip' style='animation-delay:0.18s;border-color:#14B8A6;color:#99F6E4;background:rgba(20,184,166,0.12);'>Processing</span>"
        "<span class='gx-chip' style='animation-delay:0.22s;border-color:#3B82F6;color:#BFDBFE;background:rgba(59,130,246,0.12);'>Indexing</span>"
        "<span class='gx-chip' style='animation-delay:0.26s;border-color:#F97316;color:#FDBA74;background:rgba(249,115,22,0.12);'>Execution</span>"
        "<span class='gx-chip' style='animation-delay:0.30s;border-color:#EF4444;color:#FECACA;background:rgba(239,68,68,0.12);'>Analysis</span>"
        "<span class='gx-chip' style='animation-delay:0.34s;border-color:#A855F7;color:#E9D5FF;background:rgba(168,85,247,0.12);'>Output</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    planner_query = st.text_area(
        "Query to plan:",
        value="",
        height=110,
        key="planner_query_input",
        placeholder="e.g. Does metformin reduce breast cancer recurrence in diabetic patients?",
    )
    if use_global_model:
        planner_model = global_model_choice
        st.info(f"Locked to Global Model: `{global_model_choice}`")
    else:
        planner_model = st.selectbox("Planner / answer model:", installed_models, index=0, key="planner_model_choice")
    
    # Dynamic per-collector limit selectors
    st.markdown("##### 📥 Max Papers to Fetch per Source:")
    from src.collectors.collector_registry import get_collector_names
    c_names = get_collector_names()
    c_cols = st.columns(len(c_names))
    collector_limits = {}
    for idx, name in enumerate(c_names):
        with c_cols[idx]:
            collector_limits[name] = st.number_input(
                f"{name}:",
                min_value=0,
                max_value=500,
                value=20,
                step=5,
                key=f"limit_{name.lower()}"
            )
    planner_max_papers = sum(collector_limits.values())

    st.markdown("##### 🔬 Select Synthesis Components & Agent Targets:")
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        use_manual_agents = st.toggle("Override LLM Routing (manually select output agents)", value=False, key="use_manual_agents")
    with col_opt2:
        force_fresh = st.toggle("Force Fresh Retrieval (ignore database cache)", value=False, key="force_fresh")
    
    forced_agents = None
    if use_manual_agents:
        st.markdown("<small>Toggle individual specialist agents ON or OFF:</small>", unsafe_allow_html=True)
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        selected_targets = []
        with col_c1:
            if st.toggle("Claim Extractor", value=True, key="sel_claim_extractor", help="Extracts structured claims from abstracts"):
                selected_targets.append("claim_extractor")
            if st.toggle("Consensus Analyst", value=True, key="sel_consensus", help="Analyzes consensus and agreements"):
                selected_targets.append("consensus_analyst")
        with col_c2:
            if st.toggle("Evidence Ranker", value=True, key="sel_evidence", help="Ranks study designs and scores evidence quality"):
                selected_targets.append("evidence_ranker")
            if st.toggle("Lab Experiment Planner", value=True, key="sel_experiment", help="Designs step-by-step laboratory experiment protocols"):
                selected_targets.append("experiment_planner")
        with col_c3:
            if st.toggle("Contradiction Detector", value=True, key="sel_contradiction", help="Performs pairwise contradiction analysis"):
                selected_targets.append("contradiction_detector")
            if st.toggle("ELN Assistant Logger", value=True, key="sel_eln", help="Logs formal entries to the Electronic Lab Notebook"):
                selected_targets.append("eln_assistant")
        with col_c4:
            if st.toggle("Executive Synthesis & RAG", value=True, key="sel_synthesis", help="Generates main citation-verified synthesis report"):
                selected_targets.append("synthesis")
        forced_agents = selected_targets

    # Modal Confirmation Dialog
    @st.dialog("🧬 Verify Research Intent & Routing")
    def confirm_plan_dialog(plan_obj, forced_agts, routing_cfg, limits_cfg):
        plan_dict = plan_to_dict(plan_obj)
        st.markdown(f"**Parsed Research Intent:**\n> {plan_dict['intent']}")
        st.markdown(f"**Assigned Pipeline Route:** `{plan_dict['route']}`")
        st.markdown(f"**Primary LLM Router:** `{plan_dict['model']}`")
        
        st.markdown("---")
        st.write("Does this match what you intended to search and execute? If you want to change or refine the query, describe it below:")
        refinement = st.text_input("Refinement / clarification instruction:", placeholder="e.g., focus on clinical evidence, skip cellular in-vitro studies")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Proceed & Execute", type="primary", key="btn_confirm_proceed"):
                st.session_state.execute_confirmed = {
                    "plan": plan_obj,
                    "refinement": refinement,
                    "forced_agents": forced_agts,
                    "model_routing": routing_cfg,
                    "collector_limits": limits_cfg
                }
                st.rerun()
        with col2:
            if st.button("Cancel & Edit", key="btn_confirm_cancel"):
                st.rerun()

    plan = build_query_plan(planner_query, planner_model, default_top_k=planner_max_papers)
    plan_data = plan_to_dict(plan)

    # Process execution if confirmed from the dialog modal
    if "execute_confirmed" in st.session_state and st.session_state.execute_confirmed:
        conf = st.session_state.execute_confirmed
        st.session_state.execute_confirmed = None
        
        exec_plan = conf["plan"]
        if conf["refinement"].strip():
            refined_query = f"{exec_plan.query} (Refinement: {conf['refinement']})"
            exec_plan = build_query_plan(refined_query, planner_model, default_top_k=planner_max_papers)
            
        status_placeholder = st.empty()
        def update_status_msg(msg: str):
            status_placeholder.info(f"🔄 {msg}")
            
        with st.spinner("Executing optimized specialist routing..."):
            st.session_state.execution = run_with_stop_button(
                execute_query_plan,
                exec_plan, 
                encoder_model, 
                ranked_df, 
                claims_df, 
                contradictions, 
                similarity_threshold=0.60,
                email=pubmed_email,
                api_key=sc_api_key,
                forced_agents=conf["forced_agents"],
                force_fresh=force_fresh,
                model_routing=conf["model_routing"],
                collector_limits=conf["collector_limits"],
                status_callback=update_status_msg,
                llm_options=st.session_state.get("llm_options"),
                show_terminal=True
            )
            # Reload datasets in memory so the sidebar and metrics update to the new topic
            ranked_df, claims_df, contradictions, synthesis_text = load_data()
            status_placeholder.empty()
            st.rerun()

    if st.button("Run Planned Query", type="primary", key="run_planned_query") and planner_query.strip():
        confirm_plan_dialog(plan, forced_agents, model_routing, collector_limits)

    if st.session_state.execution is not None:
        execution = st.session_state.execution
        
        # Retrieve synthesis answer directly from verification loop
        st.markdown("#### Routed Answer (Citation Verified)")
        st.markdown(format_reasoning_text(execution.get("synthesis_answer", "No answer generated."), st.session_state["reasoning_mode"]))
        
        # Show verification loop details
        st.markdown("#### Citation Verification Loop (0/1 Auditor Status)")
        verify_status = execution.get("verification", {}).get("status", "review").upper()
        status_color = "green" if verify_status == "PASS" else "orange"
        st.markdown(f"Status: **<span style='color:{status_color};'>{verify_status}</span>**", unsafe_allow_html=True)
        
        with st.expander("Auditor Verification History", expanded=False):
            for trace in execution.get("verification_trace", []):
                st.markdown(f"**Attempt {trace['attempt']}** - Status: `{trace['status']}`")
                if trace.get("findings"):
                    for finding in trace["findings"]:
                        st.markdown(f"- *{finding}*")
        
        # LLM Routing & Performance Summary
        if "routing_stats" in execution:
            with st.expander("🤖 LLM Routing & Performance Summary", expanded=True):
                stats_data = []
                for stage, details in execution["routing_stats"].items():
                    fallback_alert = "✅ OK"
                    if details.get("fallback_logs"):
                        fallback_alert = "⚠️ Sibling / Fallback Used"
                    
                    stats_data.append({
                        "Stage": stage.replace("_", " ").title(),
                        "Requested Model": details.get("requested"),
                        "Resolved Model": details.get("resolved"),
                        "Latency (sec)": f"{details.get('duration_sec', 0.0):.2f}s",
                        "Status": fallback_alert
                    })
                
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
                
                # If there are fallback logs, show them as warnings
                all_fb_logs = []
                for details in execution["routing_stats"].values():
                    if details.get("fallback_logs"):
                        all_fb_logs.extend(details["fallback_logs"])
                if all_fb_logs:
                    st.warning("  \n".join(all_fb_logs))
        
        # Show Consensus Agent Report
        if execution.get("consensus"):
            con_data = execution["consensus"]
            with st.expander(f"🤝 Consensus Analyst Report ({con_data.get('confidence_level')})", expanded=True):
                st.markdown(con_data.get("consensus_report"))
                st.caption(f"Execution time: {con_data.get('execution_time_sec')}s")
        
        # Show Experiment Agent Report
        if execution.get("experiment_protocol"):
            with st.expander("🧪 Experiment Protocol Draft", expanded=False):
                st.markdown(execution["experiment_protocol"])
        
        # Show ELN Agent Log
        if execution.get("eln_entry"):
            with st.expander("📓 ELN Lab Record Log", expanded=False):
                st.markdown(execution["eln_entry"])

        st.markdown("#### Routing Evidence")
        st.write({
            "sources": len(execution.get("sources", [])),
            "relations": len(execution.get("relations", [])),
            "claims": len(execution.get("claims", [])),
            "workflow_nodes": len(execution.get("workflow_trace", [])),
        })

        if execution.get("workflow_trace"):
            with st.expander("Workflow Trace", expanded=False):
                trace_df = pd.DataFrame(execution["workflow_trace"])
                st.dataframe(trace_df, use_container_width=True, hide_index=True)

        if execution.get("sources"):
            with st.expander("Fetched Papers", expanded=False):
                for idx, src in enumerate(execution["sources"], 1):
                    st.markdown(f"**[{idx}] {src['title']}**")
                    st.caption(f"Similarity: {src.get('similarity', 0.0):.3f} | Evidence Score: {src.get('evidence_score', 'N/A')}")
                    st.markdown(f"*{str(src.get('abstract', ''))[:220]}...")

        if execution.get("claims"):
            with st.expander("Matched Claims", expanded=False):
                for item in execution["claims"]:
                    st.markdown(f"**{item['title']}**")
                    st.caption(f"Stance: {item['stance']} | Match score: {item['score']}")
                    st.markdown(f"{item['claim']}")
                    st.markdown(f"*{item['reason']}*")
                    st.markdown("---")

        if execution.get("relations"):
            with st.expander("Graph Relations", expanded=False):
                for rel in execution["relations"]:
                    st.markdown(f"**{rel['type']}**: {rel['claim_a_title']} ↔ {rel['claim_b_title']}")
                    st.markdown(f"*{rel['explanation']}*")
                    st.markdown("---")



with tabs[1]:
    st.markdown("### 🔬 Executive Synthesis & Consensus Report")
    
    # Check if dataset is available
    has_papers = os.path.exists(CLINICAL_PAPERS_PATH)
    
    if has_papers:
        # Load sources and relations
        temp_ranked = pd.read_csv(CLINICAL_PAPERS_PATH)
        temp_sources = temp_ranked.to_dict(orient="records")
        
        # Load relations from contradictions.json
        temp_relations = []
        if os.path.exists(CONTRADICTION_PATH):
            try:
                with open(CONTRADICTION_PATH, "r", encoding="utf-8") as f:
                    temp_contr = json.load(f)
                # Combine contradictions, agreements, partial_agreements
                for r in temp_contr.get("contradictions", []):
                    temp_relations.append(dict(r, type="contradicts"))
                for r in temp_contr.get("agreements", []):
                    temp_relations.append(dict(r, type="agrees"))
                for r in temp_contr.get("partial_agreements", []):
                    temp_relations.append(dict(r, type="partial_agrees"))
            except Exception:
                pass
                
        if st.button("🔬 Run Scientific Synthesis Agent", type="primary", key="run_synthesis_agent"):
            with st.spinner("Executing Consensus & Synthesis Agent..."):
                try:
                    from src.agents.consensus_agent import analyze_consensus
                    # Run the consensus agent
                    consensus_res = run_with_stop_button(
                        analyze_consensus,
                        query=planner_query,
                        sources=temp_sources,
                        relations=temp_relations,
                        model_name=model_routing.get("consensus_analyst", "gemma3:4b"),
                        options=st.session_state.get("llm_options")
                    )
                    
                    # Store results in session state
                    if st.session_state.execution is None:
                        st.session_state.execution = {}
                    st.session_state.execution["consensus"] = consensus_res
                    
                    # Write report to dataset/consensus_report.md
                    os.makedirs(DATASET_DIR, exist_ok=True)
                    with open(os.path.join(DATASET_DIR, "consensus_report.md"), "w", encoding="utf-8") as f:
                        f.write(consensus_res.get("consensus_report", ""))
                        
                    # Refresh synthesis_text in memory
                    synthesis_text = consensus_res.get("consensus_report", "")
                    
                    st.success(f"Synthesis completed! Confidence Level: {consensus_res.get('confidence_level')}")
                except Exception as ex:
                    st.error(f"Failed to run synthesis: {ex}")

    if st.session_state.execution is not None and st.session_state.execution.get("consensus"):
        con_report = st.session_state.execution["consensus"].get("consensus_report", "")
        if con_report:
            st.markdown(format_reasoning_text(con_report, st.session_state["reasoning_mode"]))
        else:
            st.info("No consensus report available for this query.")
    elif synthesis_text:
        st.markdown(format_reasoning_text(synthesis_text, st.session_state["reasoning_mode"]))
    else:
        st.info("No synthesis report found. Please run the synthesis agent first.")
        
    st.markdown("---")
    st.markdown("#### 🔬 Peer Review & Devil's Advocate Critique")
    has_report_for_review = (st.session_state.execution is not None and st.session_state.execution.get("consensus")) or synthesis_text
    if has_report_for_review:
        with st.expander("Run Critical Appraisal", expanded=False):
            focus_area = st.text_input("Review Focus Area:", value="Methodological flaws, logical gaps, and unsupported claims", key="pr_focus")
            if st.button("Run Devil's Advocate", type="primary", key="btn_run_pr"):
                with st.spinner("Reviewing synthesis..."):
                    report_to_review = st.session_state.execution["consensus"].get("consensus_report", "") if (st.session_state.execution and st.session_state.execution.get("consensus")) else synthesis_text
                    pr_result = run_with_stop_button(run_peer_review, google_api_key, report_to_review, focus_area, gemini_model_choice)
                    st.markdown(pr_result)
    else:
        st.info("Generate or load a synthesis report first to enable Peer Review.")

with tabs[2]:
    st.markdown("### ⚡ Pairwise Analysis & Scientific Disputes")
    
    # Check if dataset is available
    has_papers = os.path.exists("dataset/clean_papers.csv")
    
    if has_papers:
        if st.button("⚡ Run Contradiction & Agreements Agent", type="primary", key="run_contradiction_agent"):
            with st.spinner("Executing pipeline..."):
                try:
                    status_placeholder = st.empty()
                    chosen_extractor = model_routing.get("claim_extractor", model_choice)
                    chosen_detector = model_routing.get("contradiction_detector", model_choice)
                    
                    run_with_stop_button(
                        run_contradiction_pipeline,
                        chosen_extractor,
                        chosen_detector,
                        status_placeholder
                    )
                    
                    status_placeholder.success("🎉 Contradiction detection completed successfully! Reloading dashboard...")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to run contradiction agent: {e}")
    else:
        st.warning("⚠️ No active dataset found. Please run a query in the 'Query Planner' first to fetch papers.")

    st.markdown("---")

    # Render interactive network graph of claims
    render_network_graph(contradictions)
    st.markdown("---")

    if isinstance(contradictions, dict) and contradictions:
        subtab1, subtab2, subtab3 = st.tabs(["Contradictions", "Agreements", "Partial Agreements"])
        
        with subtab1:
            con_list = contradictions.get("contradictions", [])
            if con_list:
                for c in con_list:
                    with st.expander(f"⚡ Conflict: {c['claim_a_title'][:60]}... VS {c['claim_b_title'][:60]}..."):
                        st.markdown(f"**Claim A**: {c['claim_a_text']}")
                        st.markdown(f"**Claim B**: {c['claim_b_text']}")
                        st.markdown(f"**Cosine Similarity**: `{c['cosine_similarity']:.3f}` | **Confidence**: `{c['confidence']:.2f}` | **Weight**: `{c['evidence_weight']:.1f}`")
                        st.markdown(f"**Explanation**: {c['explanation']}")
            else:
                st.success("No direct contradictions detected in this cohort!")

        with subtab2:
            ag_list = contradictions.get("agreements", [])
            if ag_list:
                for a in ag_list:
                    with st.expander(f"✅ Agreement: {a['claim_a_title'][:60]}..."):
                        st.markdown(f"**Claim A**: {a['claim_a_text']}")
                        st.markdown(f"**Claim B**: {a['claim_b_text']}")
                        st.markdown(f"**Explanation**: {a['explanation']}")
            else:
                st.info("No explicit agreements found.")

        with subtab3:
            pa_list = contradictions.get("partial_agreements", [])
            if pa_list:
                for p in pa_list:
                    with st.expander(f"🔀 Partial: {p['claim_a_title'][:60]}..."):
                        st.markdown(f"**Claim A**: {p['claim_a_text']}")
                        st.markdown(f"**Claim B**: {p['claim_b_text']}")
                        st.markdown(f"**Explanation**: {p['explanation']}")
            else:
                st.info("No partial agreements found.")
    else:
        st.info("No contradiction data found.")

with tabs[3]:
    st.markdown("### 📚 Ranked Evidence (Oxford Level of Evidence)")
    if ranked_df is not None:
        min_score = st.slider("Filter by Evidence Score", 1.0, 10.0, 1.0, step=0.5)
        filtered_df = ranked_df[ranked_df["evidence_score"] >= min_score].sort_values("evidence_score", ascending=False)

        st.dataframe(
            filtered_df[["title", "evidence_score", "study_design", "sample_size", "source", "year"]],
            column_config={
                "title": "Paper Title",
                "evidence_score": st.column_config.ProgressColumn(
                    "Evidence Score", min_value=1.0, max_value=10.0, format="%.1f"
                ),
                "study_design": "Study Design",
                "sample_size": "Sample Size",
                "source": "Source",
                "year": "Year"
            },
            hide_index=True,
            use_container_width=True
        )
        
        st.markdown("---")
        st.markdown("#### 🔬 Methodological Quality & Bias Audit")
        for idx, (_, r) in enumerate(filtered_df.iterrows(), 1):
            flags = audit_methodology(r)
            status_text = "🟢 HIGH QUALITY" if not [f for f in flags if "⚠️" in f or "❓" in f] else "🟡 AUDIT WARNINGS"
            
            with st.expander(f"[{r['evidence_score']:.1f}/10] - {r['title'][:80]}... ({status_text})"):
                st.markdown(f"**Full Title**: {r['title']}")
                st.markdown(f"**Study Design**: `{r['study_design']}` | **Sample Size**: `{int(r['sample_size']) if r['sample_size'] > 0 else 'N/A'}`")
                
                # Render badges
                if flags:
                    badge_html = " ".join([
                        f"<span class='badge' style='background:rgba(245,158,11,0.12);color:#fbbf24;border-color:rgba(245,158,11,0.45);margin:0 6px 6px 0;'>{f}</span>"
                        if "⚠️" in f or "❓" in f else
                        f"<span class='badge' style='background:rgba(52,211,153,0.12);color:#34d399;border-color:rgba(52,211,153,0.45);margin:0 6px 6px 0;'>{f}</span>"
                        for f in flags
                    ])
                    st.markdown(f"**Methodological Audit**: {badge_html}", unsafe_allow_html=True)
                else:
                    st.markdown("**Methodological Audit**: 🟢 High quality clinical study layout (no bias markers detected).")
                st.markdown(f"**Abstract**: *{r['abstract']}*")
    else:
        st.info("No ranked evidence data found.")

with tabs[4]:
    st.markdown("### 🔎 Claim & Stance Exploration")
    if claims_df is not None:
        search_query = st.text_input("Filter claims by keyword:", "")
        stance_filter = st.multiselect("Stance:", ["support", "contradict", "neutral"], default=["support", "contradict", "neutral"])

        filtered_claims = claims_df.copy()
        if search_query:
            filtered_claims = filtered_claims[filtered_claims["claim"].str.contains(search_query, case=False, na=False)]
        filtered_claims = filtered_claims[filtered_claims["stance"].isin(stance_filter)]

        st.dataframe(
            filtered_claims[["title", "claim", "stance", "reason"]],
            column_config={
                "title": "Paper Title",
                "claim": "Extracted Claim",
                "stance": "Stance",
                "reason": "Supporting Reasoning"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No extracted claims found.")

with tabs[5]:
    st.markdown("### 🤖 RAG vs. Graph RAG Performance Comparison")
    st.markdown(
        "Compare the generation latency, citation completeness, and conflict-handling capabilities "
        "of standard vector-based RAG against relationship-traversing Graph RAG."
    )
    
    # Input panel
    q_col1, q_col2 = st.columns([3, 1])
    with q_col1:
        eval_question = st.text_input(
            "Enter your research query:",
            value="",
            key="eval_user_question"
        )
    with q_col2:
        eval_k = st.slider("Top K Papers to retrieve:", 1, 5, 3, key="eval_top_k")
        
    compare_btn = st.button("⚖️ Compare Performance", type="primary")
    
    if compare_btn and eval_question:
        status_placeholder = st.empty()
        with st.spinner("Executing comparison queries..."):
            (
                std_answer, std_sources, std_total_time, std_ret_time, std_word_count,
                graph_answer, graph_sources, graph_relations, graph_total_time, graph_ret_time, graph_word_count
            ) = run_with_stop_button(
                run_comparison_pipeline,
                eval_question, 
                encoder_model, 
                ranked_df, 
                contradictions, 
                eval_k, 
                model_choice, 
                status_placeholder
            )
            status_placeholder.empty()
            
            # Display answers side-by-side
            ans_col1, ans_col2 = st.columns(2)
            
            with ans_col1:
                st.markdown(
                    '<div class="card" style="border-left: 4px solid #94a3b8 !important; padding: 22px 24px; margin-bottom: 20px; animation-delay:0.05s;">',
                    unsafe_allow_html=True,
                )
                st.markdown("### 📋 Standard Vector RAG")
                st.markdown(std_answer)
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Standard Metrics
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric("Total Latency", f"{std_total_time:.2f}s", delta=None)
                    st.metric("Retrieval Latency", f"{std_ret_time:.3f}s")
                with m_col2:
                    st.metric("Word Count", f"{std_word_count}")
                    st.metric("Sources Cited", f"{len(std_sources)}")
                    
                # Sources Cited Expandable
                if std_sources:
                    with st.expander("📚 Retrieved Papers", expanded=False):
                        for src in std_sources:
                            st.markdown(f"**[{src['index']}] {src['title']}**")
                            st.caption(f"Similarity: {src['similarity']:.3f} | Score: {src['evidence_score']}/10")
                            st.markdown(f"*{src['abstract'][:180]}...*")
                            st.markdown("---")
                            
            with ans_col2:
                st.markdown(
                    '<div class="card" style="border-left: 4px solid #818cf8 !important; box-shadow: 0 8px 32px rgba(99, 102, 241, 0.22) !important; padding: 22px 24px; margin-bottom: 20px; animation-delay:0.12s;">',
                    unsafe_allow_html=True,
                )
                st.markdown("### 🕸️ Relationship-Traversing Graph RAG")
                st.markdown(graph_answer)
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Graph Metrics
                gm_col1, gm_col2 = st.columns(2)
                with gm_col1:
                    st.metric("Total Latency", f"{graph_total_time:.2f}s", delta=f"{graph_total_time - std_total_time:.2f}s", delta_color="inverse")
                    st.metric("Retrieval Latency", f"{graph_ret_time:.3f}s", delta=f"{graph_ret_time - std_ret_time:.3f}s", delta_color="inverse")
                with gm_col2:
                    st.metric("Word Count", f"{graph_word_count}", delta=f"{graph_word_count - std_word_count}")
                    st.metric("Graph Relations", f"{len(graph_relations)}")
                
                # Graph Relations Expandable
                if graph_relations:
                    with st.expander(f"🕸️ Traversed Relationships ({len(graph_relations)})", expanded=True):
                        for r_idx, r in enumerate(graph_relations, 1):
                            st.markdown(f"**[{r_idx}] {r['type']}**")
                            st.markdown(f"- **Paper A**: {r['claim_a_title']}")
                            st.markdown(f"- **Paper B**: {r['claim_b_title']}")
                            st.markdown(f"- *{r['explanation']}*")
                            st.markdown("---")



# 3. Interactive Multi-Turn Chat (Ask the LLM with Dataset Context)
st.sidebar.markdown("---")
st.sidebar.subheader("💬 Ask the Dataset (RAG Chat)")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if use_global_model:
    rag_model_choice = global_model_choice
    st.sidebar.info(f"Chat locked to Global Model: `{global_model_choice}`")
else:
    rag_model_choice = st.sidebar.selectbox("Ollama Model:", installed_models, key="rag_model_choice")

# Clear chat history button
if st.sidebar.button("🗑️ Clear Chat History", key="clear_chat_history"):
    st.session_state.chat_history = []
    st.rerun()

# Scrollable chat message container inside the sidebar
chat_container = st.sidebar.container(height=350)
with chat_container:
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Display cited papers for this message if they exist
            if msg.get("sources"):
                with st.expander("📚 Cited Papers", expanded=False):
                    for src in msg["sources"]:
                        st.markdown(f"**[{src['index']}] {src['title']}**")
                        st.caption(f"Similarity: {src['similarity']:.3f} | Score: {src['evidence_score']}/10")
                        st.markdown(f"*{src['abstract'][:120]}...*")

# Chat input at the bottom of the sidebar
user_chat_input = st.sidebar.chat_input("Ask about this evidence...", key="rag_chat_input")

if user_chat_input:
    # Append user question immediately to history
    st.session_state.chat_history.append({"role": "user", "content": user_chat_input})
    
    # Search dataset context
    context_list = []
    retrieved_sources = []
    
    # 1. Encode user question semantically
    query_emb = encoder_model.encode([user_chat_input], normalize_embeddings=True)[0]
    
    # 2. Semantic Search on Papers
    if ranked_df is not None and "embedding" in ranked_df.columns:
        emb_list = list(ranked_df["embedding"])
        if emb_list:
            embeddings_matrix = np.vstack(emb_list)
            similarities = (embeddings_matrix @ query_emb).astype(float)
            search_df = ranked_df.copy()
            search_df["similarity"] = similarities
            top_papers = search_df.sort_values(by="similarity", ascending=False).head(5)
            
            for idx, (_, r) in enumerate(top_papers.iterrows(), 1):
                sample_size_str = str(int(r['sample_size'])) if ('sample_size' in r and r['sample_size'] > 0) else "N/A"
                design_str = r.get('study_design', 'Undetermined')
                context_list.append(
                    f"[Source Paper {idx}]\n"
                    f"Title: {r['title']}\n"
                    f"Evidence Score: {r['evidence_score']}/10 | Design: {design_str} | Sample Size: {sample_size_str}\n"
                    f"Abstract: {str(r['abstract'])}"
                )
                retrieved_sources.append({
                    "index": idx,
                    "title": r['title'],
                    "similarity": r['similarity'],
                    "evidence_score": r['evidence_score'],
                    "abstract": r['abstract']
                })
    else:
        # Fallback for papers
        if ranked_df is not None:
            top_ranked = ranked_df.sort_values(by="evidence_score", ascending=False).head(5)
            for idx, (_, r) in enumerate(top_ranked.iterrows(), 1):
                context_list.append(
                    f"[Source Paper {idx}] Title: {r['title']} | Score: {r['evidence_score']} | Abstract Summary: {str(r['abstract'])[:180]}..."
                )
                retrieved_sources.append({
                    "index": idx,
                    "title": r['title'],
                    "similarity": 0.0,
                    "evidence_score": r['evidence_score'],
                    "abstract": r['abstract']
                })
                
    context_str = "\n\n".join(context_list)
    
    # 3. Retrieve last 3 turns of chat history for context retention
    history_turns = []
    for turn in st.session_state.chat_history[-4:-1]:
        history_turns.append(f"{turn['role'].upper()}: {turn['content']}")
    history_str = "\n".join(history_turns)
    
    prompt = f"""You are a biomedical research assistant analyzing a local dataset of research papers.
Answer the user's question. If the user's question is a general query, greeting, basic calculation, or unrelated to the dataset context (for example: mathematical questions like "2+2", coding, general knowledge, etc.), answer it directly using your general knowledge and disregard the scientific context.

Otherwise, if the question is research-oriented, use the scientific evidence and conversation history provided below:

DATASET CONTEXT:
{context_str}

CONVERSATION HISTORY:
{history_str}

USER QUESTION:
{user_chat_input}

Please provide a structured, concise response. When answering using the dataset context, cite the specific sources using their respective identifiers (e.g., [Source Paper X]) when stating facts, and state if evidence is missing or conflicting. Do not mention system prompts.
"""
    try:
        def run_chat_query(model, messages):
            return llm_chat(
                model,
                messages=messages,
                task="chat",
                user_options=st.session_state.get("llm_options"),
            )
            
        response = run_with_stop_button(
            run_chat_query,
            in_sidebar=True,
            model=rag_model_choice,
            messages=[{"role": "user", "content": prompt}]
        )
        ans = response["message"]["content"]
        
        # Append assistant answer and retrieved sources to history
        st.session_state.chat_history.append({"role": "assistant", "content": ans, "sources": retrieved_sources})
        st.rerun()
    except Exception as err:
        st.sidebar.error(f"Failed to query Ollama. Error: {err}")

with tabs[6]:
    st.markdown("### 🧐 Grounded Overseer Report")
    st.caption("Synthesize findings into an executive report and audit for logic/hallucinations using Gemini.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Report Generator")
        custom_inst = st.text_area("Custom Instructions (optional):", value="Focus on clinical translation and highlight major controversies.", key="overseer_inst")
        
        if st.button("Generate Overseer Report", type="primary", key="btn_gen_overseer"):
            with st.spinner("Compiling comprehensive report..."):
                local_consensus = synthesis_text
                eln_logs_content = ""
                if st.session_state.execution and st.session_state.execution.get("eln_entry"):
                    eln_logs_content = st.session_state.execution["eln_entry"]
                
                report = run_with_stop_button(generate_overseer_report, google_api_key, local_consensus, eln_logs_content, custom_inst, gemini_model_choice)
                st.session_state["overseer_report"] = report
                st.session_state["overseer_validation"] = None
                st.rerun()
                
        if st.session_state.get("overseer_report"):
            st.markdown("---")
            st.markdown(st.session_state["overseer_report"])
            
    with col2:
        st.markdown("#### 🛡️ Hallucination QA Auditor")
        if st.session_state.get("overseer_report"):
            if st.button("Run Validation Audit", key="btn_run_audit"):
                with st.spinner("Auditing report..."):
                    audit_res = run_with_stop_button(run_qa_audit, google_api_key, st.session_state["overseer_report"], gemini_model_choice)
                    st.session_state["overseer_validation"] = audit_res
                    st.rerun()
                    
            if st.session_state.get("overseer_validation"):
                val = st.session_state["overseer_validation"]
                score = val.get("score", 0)
                color = "green" if score > 80 else "orange" if score > 50 else "red"
                st.markdown(f"**Credibility Score:** <span style='color:{color}; font-size:1.5em; font-weight:bold;'>{score}/100</span>", unsafe_allow_html=True)
                st.markdown(f"*{val.get('feedback', '')}*")
                
                if val.get("issues"):
                    st.markdown("**Issues Identified:**")
                    for issue in val["issues"]:
                        st.markdown(f"- {issue}")
                        
        st.markdown("---")
        st.markdown("#### ✍️ Iterative Refiner")
        if st.session_state.get("overseer_report"):
            refine_inst = st.text_area("Refinement Instructions:", placeholder="e.g. Make the conclusion more conservative.", key="refine_inst")
            if st.button("Refine Report", key="btn_refine"):
                with st.spinner("Refining..."):
                    refined_text = run_with_stop_button(refine_report_section, google_api_key, st.session_state["overseer_report"], refine_inst, gemini_model_choice)
                    st.session_state["overseer_report"] = refined_text
                    st.rerun()