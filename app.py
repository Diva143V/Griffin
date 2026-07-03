import os
import json
import ast
import time
import pandas as pd
import numpy as np
import streamlit as st
import ollama
from sentence_transformers import SentenceTransformer
from src.core import graph_rag
from src.agents.query_planner import build_query_plan, execute_query_plan, plan_to_dict

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
            
        target = "koesn/llama3-openbiollm-8b:latest"
        if target not in names:
            names.append(target)
        if not names:
            return ["koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]
        return names
    except Exception:
        return ["koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]

# Set page config for a clean, professional dashboard
st.set_page_config(
    page_title="Griffin Bio – Scientific Synthesis & Contradiction Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean premium styling
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
    /* Global Base */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #171d2b 0%, #0d1117 75%);
        color: #E6EDF3;
        font-family: 'Inter', sans-serif;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #D6DCE5;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Poppins', sans-serif !important;
        color: #F4F7FA !important;
        letter-spacing: -0.5px;
        font-weight: 600 !important;
    }

    h1 {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #58A6FF 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px !important;
    }

    h2 {
        font-size: 1.7rem !important;
        border-bottom: 1px solid #21262d;
        padding-bottom: 8px;
        margin-top: 24px !important;
    }

    h3 {
        font-size: 1.3rem !important;
        color: #58A6FF !important;
    }

    p, span, div {
        line-height: 1.7;
    }

    /* Premium Cards & Containers */
    .card, [data-testid="stMetricValue"] {
        background: rgba(22, 27, 34, 0.7) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(48, 54, 61, 0.6) !important;
        border-radius: 16px !important;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .card:hover {
        border-color: rgba(59, 130, 246, 0.6) !important;
        box-shadow: 0 8px 30px rgba(59, 130, 246, 0.15);
        transform: translateY(-3px);
    }

    /* Premium Badges */
    .badge {
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
        border: 1px solid transparent;
    }

    /* Metric Override */
    [data-testid="stMetricValue"] {
        font-family: 'Poppins', sans-serif !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: #58A6FF !important;
        padding: 16px 20px !important;
        background: linear-gradient(145deg, rgba(22, 27, 34, 0.8) 0%, rgba(13, 17, 23, 0.8) 100%) !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.8rem !important;
        color: #8B949E !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        font-weight: 600 !important;
        margin-bottom: 6px !important;
    }

    /* Sidebar Customization */
    [data-testid="stSidebar"] {
        background: #0d1117 !important;
        border-right: 1px solid #21262d !important;
    }

    [data-testid="stSidebar"] * {
        color: #DDE3EA;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        margin-bottom: 24px;
        border-bottom: 1px solid #21262d;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(22, 27, 34, 0.5) !important;
        border: 1px solid rgba(48, 54, 61, 0.8) !important;
        border-bottom: none !important;
        border-radius: 12px 12px 0 0 !important;
        padding: 10px 18px !important;
        color: #8B949E !important;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(33, 38, 45, 0.7) !important;
        color: #F0F6FC !important;
    }

    .stTabs [aria-selected="true"] {
        background: #161b22 !important;
        border: 1px solid #30363d !important;
        border-bottom: 2px solid #58A6FF !important;
        color: #58A6FF !important;
        font-weight: 600 !important;
    }

    /* Smooth Expanders */
    .streamlit-expanderHeader {
        background-color: rgba(22, 27, 34, 0.4) !important;
        border: 1px solid #21262d !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        color: #c9d1d9 !important;
        font-weight: 500 !important;
        font-family: 'Poppins', sans-serif;
    }
    
    .streamlit-expanderContent {
        background-color: rgba(22, 27, 34, 0.1) !important;
        border: 1px solid #21262d !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        padding: 16px !important;
    }

    /* Custom Tables & DataFrames */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #30363d;
    }

    /* Input & Selection Elements */
    .stTextInput input,
    .stSelectbox div,
    .stMultiSelect div,
    .stTextArea textarea,
    .stNumberInput input {
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
        background-color: #0d1117 !important;
        color: #E6EDF3 !important;
        font-family: 'Inter', sans-serif !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #58A6FF !important;
        box-shadow: 0 0 0 1px #58A6FF !important;
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        padding: 8px 20px !important;
        transition: all 0.2s ease !important;
    }

    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #1f6feb 0%, #0969da 100%) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(31, 111, 235, 0.3) !important;
    }

    .stButton button[kind="primary"]:hover {
        box-shadow: 0 6px 18px rgba(31, 111, 235, 0.45) !important;
        transform: translateY(-1px) !important;
    }

    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }
    
    /* Code block styling */
    code {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #161b22 !important;
        border-radius: 4px;
        padding: 2px 6px;
        color: #ff7b72;
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
    return SentenceTransformer("all-MiniLM-L6-v2")

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
            lbl = (c_a[:40] + "...") if len(c_a) > 40 else c_a
            nodes_list.append({
                "id": node_id_counter,
                "label": lbl,
                "title": f"<b>Paper:</b> {t_a}<br><br><b>Claim:</b> {c_a}",
                "color": {
                    "background": "#0d1117",
                    "border": "#58a6ff",
                    "highlight": {"background": "#58a6ff", "border": "#c9d1d9"}
                }
            })
            
        # Register node B
        if t_b not in nodes_map:
            node_id_counter += 1
            nodes_map[t_b] = node_id_counter
            lbl = (c_b[:40] + "...") if len(c_b) > 40 else c_b
            nodes_list.append({
                "id": node_id_counter,
                "label": lbl,
                "title": f"<b>Paper:</b> {t_b}<br><br><b>Claim:</b> {c_b}",
                "color": {
                    "background": "#0d1117",
                    "border": "#58a6ff",
                    "highlight": {"background": "#58a6ff", "border": "#c9d1d9"}
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
            "font": {"color": "#8b949e", "size": 9, "strokeWidth": 0, "face": "Inter, sans-serif"}
        })

    nodes_json = json.dumps(nodes_list)
    edges_json = json.dumps(edges_list)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style type="text/css">
            html, body {{
                margin: 0;
                padding: 0;
                background-color: #0d1117;
                overflow: hidden;
                font-family: 'Inter', sans-serif;
            }}
            #mynetwork {{
                width: 100%;
                height: 400px;
                border: 1px solid #30363d;
                border-radius: 14px;
                background-color: #0d1117;
            }}
            /* Clean visual tooltips matching premium dark styling */
            div.vis-tooltip {{
                position: absolute;
                visibility: hidden;
                padding: 12px;
                white-space: pre-wrap;
                background-color: rgba(22, 27, 34, 0.95);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(48, 54, 61, 0.8);
                border-radius: 10px;
                color: #c9d1d9;
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                line-height: 1.5;
                box-shadow: 0 8px 24px rgba(0,0,0,0.5);
                max-width: 320px;
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
                size: 16,
                font: {{ color: '#c9d1d9', size: 11, face: 'Inter, sans-serif' }},
                borderWidth: 2,
                shadow: {{ enabled: true, color: 'rgba(0,0,0,0.5)', size: 10, x: 0, y: 4 }}
            }},
            edges: {{
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
                font: {{ align: 'middle' }},
                smooth: {{ type: 'cubicBezier', forceDirection: 'none', roundness: 0.4 }}
            }},
            physics: {{
                stabilization: true,
                barnesHut: {{ gravitationalConstant: -2500, centralGravity: 0.35, springLength: 130 }}
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
    </body>
    </html>
    """
    import streamlit.components.v1 as components
    st.markdown("##### 🌐 Visual Claim Dispute Map")
    components.html(html_content, height=410)

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
# LLM Model Routing block
st.sidebar.subheader("🤖 LLM Model Routing")
routing_mode = st.sidebar.radio(
    "Routing Strategy:",
    ["Default Optimized Mixture", "Custom Specialist Routing"],
    index=0,
    help="Default uses a curated list of models optimized for each specific task. Custom lets you assign specific models."
)

model_routing = {}
if routing_mode == "Custom Specialist Routing":
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

st.title("🧬 Griffin Bio Dashboard")
st.caption("Scientific evidence synthesis, contradiction detection, and research exploration")

# 2. Main Tabs
tabs = st.tabs([
    "🧭 Query Planner",
    "📝 Scientific Synthesis",
    "⚡ Contradictions & Agreements",
    "📚 Ranked Clinical Evidence",
    "🔎 Claims Exploration",
    "🤖 RAG Performance Comparison",
])

with tabs[0]:
    st.markdown("### 🧭 Query Planner")
    st.caption("Enter a question and see the full workflow from query to verification before generating an answer.")

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
        "<div style='display:flex;flex-wrap:wrap;gap:8px 10px;margin-bottom:14px;'>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #7C3AED;color:#E9D5FF;'>Input</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #0EA5E9;color:#BAE6FD;'>Orchestration</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #22C55E;color:#BBF7D0;'>Retrieval</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #F59E0B;color:#FDE68A;'>Collector</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #14B8A6;color:#99F6E4;'>Processing</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #3B82F6;color:#BFDBFE;'>Indexing</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #F97316;color:#FDBA74;'>Execution</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #EF4444;color:#FECACA;'>Analysis</span>"
        "<span style='padding:4px 10px;border-radius:999px;border:1px solid #A855F7;color:#E9D5FF;'>Output</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    planner_query = st.text_area(
        "Query to plan:",
        value="Does metformin improve survival in HER2-positive breast cancer?",
        height=90,
        key="planner_query_input",
    )
    planner_model = st.selectbox("Planner / answer model:", installed_models, index=0, key="planner_model_choice")
    planner_threshold = st.slider("Relevance threshold (Cosine Similarity):", 0.10, 0.90, 0.60, step=0.05, key="planner_threshold")
    planner_max_papers = st.number_input("Maximum papers to fetch from API:", min_value=1, max_value=500, value=20, step=5, key="planner_max_papers")

    st.markdown("##### 🔬 Select Synthesis Components & Agent Targets:")
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        use_manual_agents = st.checkbox("Override LLM Routing (manually select output agents)", value=False, key="use_manual_agents")
    with col_opt2:
        force_fresh = st.checkbox("Force Fresh Retrieval (ignore database cache)", value=False, key="force_fresh")
    
    forced_agents = None
    if use_manual_agents:
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        selected_targets = []
        with col_c1:
            if st.checkbox("Executive Synthesis & RAG", value=True, key="sel_synthesis"):
                selected_targets.append("synthesis")
        with col_c2:
            if st.checkbox("Consensus Analyst Report", value=True, key="sel_consensus"):
                selected_targets.append("consensus_analyst")
        with col_c3:
            if st.checkbox("Lab Experiment Planner", value=True, key="sel_experiment"):
                selected_targets.append("experiment_planner")
        with col_c4:
            if st.checkbox("ELN Assistant Logger", value=True, key="sel_eln"):
                selected_targets.append("eln_assistant")
        forced_agents = selected_targets

    plan = build_query_plan(planner_query, planner_model, default_top_k=planner_max_papers)
    plan_data = plan_to_dict(plan)

    st.markdown(f"**Intent**: `{plan_data['intent']}`  |  **Route**: `{plan_data['route']}`  |  **Model**: `{plan_data['model']}`")

    # Simplified Query Planner UI
    if plan_data.get("notes"):
        for note in plan_data["notes"]:
            st.info(f"💡 {note}")

    if st.button("Run Planned Query", type="primary", key="run_planned_query") and planner_query.strip():
        with st.spinner("Planning route and generating answer..."):
            st.session_state.execution = execute_query_plan(
                plan, 
                encoder_model, 
                ranked_df, 
                claims_df, 
                contradictions, 
                similarity_threshold=planner_threshold,
                email=pubmed_email,
                api_key=sc_api_key,
                forced_agents=forced_agents,
                force_fresh=force_fresh,
                model_routing=model_routing
            )
            # Reload datasets in memory so the sidebar and metrics update to the new topic
            ranked_df, claims_df, contradictions, synthesis_text = load_data()
            st.rerun()

    if st.session_state.execution is not None:
        execution = st.session_state.execution
        
        # Retrieve synthesis answer directly from verification loop
        st.markdown("#### Routed Answer (Citation Verified)")
        st.markdown(execution.get("synthesis_answer", "No answer generated."))
        
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

    with st.expander("Planner JSON", expanded=False):
        st.json(plan_data)

with tabs[1]:
    st.markdown("### 🔬 Executive Synthesis & Consensus Report")
    
    # Check if there is data to compile into a PDF
    active_report = ""
    active_query = ""
    active_protocol = ""
    
    if st.session_state.execution is not None:
        active_query = st.session_state.execution.get("plan", {}).get("query", "") or planner_query
        active_report = st.session_state.execution.get("consensus", {}).get("consensus_report", "")
        active_protocol = st.session_state.execution.get("experiment_protocol", "")
    elif synthesis_text:
        active_query = planner_query or "Scientific Research Compilation"
        active_report = synthesis_text
        if os.path.exists("dataset/protocol_draft.txt"):
            try:
                with open("dataset/protocol_draft.txt", "r", encoding="utf-8") as pf:
                    active_protocol = pf.read()
            except Exception:
                pass
                
    if active_report:
        try:
            from src.shared.pdf_generator import generate_synthesis_pdf
            pdf_path = "dataset/scientific_consensus_report.pdf"
            generate_synthesis_pdf(
                query=active_query,
                consensus_text=active_report,
                protocol_text=active_protocol,
                top_papers_df=ranked_df,
                output_path=pdf_path
            )
            
            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                
            st.download_button(
                label="📥 Export Report as PDF",
                data=pdf_bytes,
                file_name="scientific_consensus_report.pdf",
                mime="application/pdf",
                key="download_pdf_report"
            )
        except Exception as pe:
            st.warning(f"Could not build PDF exporter: {pe}")

    if st.session_state.execution is not None and st.session_state.execution.get("consensus"):
        con_report = st.session_state.execution["consensus"].get("consensus_report", "")
        if con_report:
            st.markdown(con_report)
        else:
            st.info("No consensus report available for this query.")
    elif synthesis_text:
        st.markdown(synthesis_text)
    else:
        st.info("No synthesis report found. Please run the contradiction and synthesis pipelines first.")

with tabs[2]:
    st.markdown("### ⚡ Pairwise Analysis & Scientific Disputes")
    
    # Check if dataset is available
    has_papers = os.path.exists("dataset/clean_papers.csv")
    
    if has_papers:
        if st.button("⚡ Run Contradiction & Agreements Agent", type="primary", key="run_contradiction_agent"):
            with st.spinner("Executing pipeline..."):
                try:
                    # Import agents inline to avoid circular dependencies
                    from src.core.claim_extractor import extract_claims
                    from src.core.contradiction_detector import run_detector
                    
                    status_placeholder = st.empty()
                    
                    status_placeholder.info("🔄 Stage 1: Extracting claims from papers using Ollama...")
                    extract_claims(
                        input_path="dataset/clean_papers.csv",
                        output_path="dataset/claims.csv",
                        model=model_choice,
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
                        model=model_choice,
                        embedding_model="all-MiniLM-L6-v2",
                        evidence_file="dataset/ranked_papers.csv",
                        max_pairs=20,
                        similarity_threshold=0.45,
                        skip_embeddings=False
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
                        f"<span style='background-color:#2a1c0b;color:#f59e0b;border:1px solid #f59e0b;padding:3px 8px;border-radius:6px;font-size:0.8rem;margin-right:6px;display:inline-block;margin-bottom:4px;'>{f}</span>"
                        if "⚠️" in f or "❓" in f else
                        f"<span style='background-color:#112015;color:#10b981;border:1px solid #10b981;padding:3px 8px;border-radius:6px;font-size:0.8rem;margin-right:6px;display:inline-block;margin-bottom:4px;'>{f}</span>"
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
            value="Does metformin improve survival in HER2-positive breast cancer?",
            key="eval_user_question"
        )
    with q_col2:
        eval_k = st.slider("Top K Papers to retrieve:", 1, 5, 3, key="eval_top_k")
        
    compare_btn = st.button("⚖️ Compare Performance", type="primary")
    
    if compare_btn and eval_question:
        with st.spinner("Executing comparison queries..."):
            # Standard RAG
            t_ret_start = time.time()
            std_context, std_sources = graph_rag.get_standard_rag_context(
                eval_question, encoder_model, ranked_df, eval_k
            )
            std_ret_time = time.time() - t_ret_start
            
            std_prompt = f"""You are a biomedical research assistant.
Answer the user's question using the scientific evidence provided below.

USER QUESTION:
{eval_question}

DATASET CONTEXT:
{std_context}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X]) when stating facts. State if evidence is missing or conflicting. Do not mention system prompts."""

            std_answer, std_gen_time = graph_rag.generate_answer(std_prompt, model_choice)
            std_total_time = std_ret_time + std_gen_time
            std_word_count = len(std_answer.split())
            
            # Graph RAG
            t_ret_start = time.time()
            graph_context, graph_sources, graph_relations = graph_rag.get_graph_rag_context(
                eval_question, encoder_model, ranked_df, contradictions, eval_k
            )
            graph_ret_time = time.time() - t_ret_start
            
            graph_prompt = f"""You are a biomedical research assistant.
Answer the user's question using the scientific evidence and graph relationships provided below.

USER QUESTION:
{eval_question}

DATASET CONTEXT & GRAPH CONNECTIONS:
{graph_context}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X] or [Graph Connection Y]) when stating facts. Critically address any contradictions or agreements mentioned in the graph relationships. State if evidence is missing or conflicting. Do not mention system prompts."""

            graph_answer, graph_gen_time = graph_rag.generate_answer(graph_prompt, model_choice)
            graph_total_time = graph_ret_time + graph_gen_time
            graph_word_count = len(graph_answer.split())
            
            # Display answers side-by-side
            ans_col1, ans_col2 = st.columns(2)
            
            with ans_col1:
                st.markdown('<div class="card" style="border-left: 4px solid #8b949e !important; padding: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
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
                st.markdown('<div class="card" style="border-left: 4px solid #58A6FF !important; box-shadow: 0 4px 25px rgba(59, 130, 246, 0.2) !important; padding: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
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

installed_models = get_ollama_models()
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
Answer the user's question using the scientific evidence and conversation history provided below.

DATASET CONTEXT:
{context_str}

CONVERSATION HISTORY:
{history_str}

USER QUESTION:
{user_chat_input}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X]) when stating facts. State if evidence is missing or conflicting. Do not mention system prompts.
"""
    try:
        response = ollama.chat(
            model=rag_model_choice,
            messages=[{"role": "user", "content": prompt}]
        )
        ans = response["message"]["content"]
        
        # Append assistant answer and retrieved sources to history
        st.session_state.chat_history.append({"role": "assistant", "content": ans, "sources": retrieved_sources})
        st.rerun()
    except Exception as err:
        st.sidebar.error(f"Failed to query Ollama. Error: {err}")