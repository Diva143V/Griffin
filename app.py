import os
import json
import ast
import time
import pandas as pd
import numpy as np
import streamlit as st
import ollama
from sentence_transformers import SentenceTransformer
import graph_rag

@st.cache_resource(ttl=60)
def get_ollama_models():
    try:
        model_list = ollama.list()
        names = [m.model for m in model_list.models]
        if not names:
            return ["gemma3:4b", "gemma3:1b", "qwen3.5:latest"]
        return names
    except Exception:
        return ["gemma3:4b", "gemma3:1b", "qwen3.5:latest"]

# Set page config for a clean, professional dashboard
st.set_page_config(
    page_title="Corvus Bio – Scientific Synthesis & Contradiction Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean premium styling
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@500;600;700&display=swap" rel="stylesheet">

<style>
    .stApp {
        background: #0E1117;
        color: #E6EDF3;
        font-family: 'Inter', sans-serif;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #D6DCE5;
    }

    h1, h2, h3, h4 {
        font-family: 'Poppins', sans-serif !important;
        color: #F4F7FA !important;
        letter-spacing: -0.5px;
        margin-bottom: 8px;
    }

    h1 {
        font-size: 2.3rem !important;
        font-weight: 700 !important;
    }

    h2 {
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }

    h3 {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
    }

    p, span, div {
        line-height: 1.7;
    }

    .card {
        background: #161B22;
        border: 1px solid #2B313C;
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 20px;
        transition: all 0.2s ease;
    }

    .card:hover {
        border-color: #3B82F6;
        transform: translateY(-2px);
    }

    .metric-value {
        font-family: 'Poppins', sans-serif;
        font-size: 2.3rem;
        font-weight: 700;
        color: #58A6FF;
        margin-bottom: 4px;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }

    [data-testid="stSidebar"] {
        background: #11161F !important;
        border-right: 1px solid #222B36;
    }

    [data-testid="stSidebar"] * {
        color: #DDE3EA;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        margin-bottom: 15px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #161B22;
        border: 1px solid #2B313C;
        border-radius: 12px;
        padding: 12px 20px;
        color: #9AA4B2 !important;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: #1D2430;
        color: #FFFFFF !important;
    }

    .stTabs [aria-selected="true"] {
        background: #1E293B !important;
        border: 1px solid #3B82F6 !important;
        color: #58A6FF !important;
    }

    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1rem;
    }

    [data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid #2B313C;
    }

    .stTextInput input,
    .stSelectbox div,
    .stMultiSelect div {
        border-radius: 10px !important;
        background-color: #161B22 !important;
        color: #E6EDF3 !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar - Settings & Actions
st.sidebar.title("🧬 Corvus Bio Controls")
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
@st.cache_data
def load_data():
    ranked_df = pd.read_csv(CLINICAL_PAPERS_PATH) if os.path.exists(CLINICAL_PAPERS_PATH) else None
    claims_df = pd.read_csv(CLAIMS_PATH) if os.path.exists(CLAIMS_PATH) else None

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
    if os.path.exists(SYNTHESIS_PATH):
        try:
            with open(SYNTHESIS_PATH, "r", encoding="utf-8") as f:
                synthesis_text = f.read()
        except Exception:
            pass

    return ranked_df, claims_df, contradictions, synthesis_text

ranked_df, claims_df, contradictions, synthesis_text = load_data()
encoder_model = load_encoder_model()

st.title("🧬 Corvus Bio Dashboard")
st.caption("Scientific evidence synthesis, contradiction detection, and research exploration")

# 1. Dashboard Overview Metrics
if ranked_df is not None or claims_df is not None:
    st.markdown("### 📊 Metrics Summary")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_papers = len(ranked_df) if ranked_df is not None else 0
        st.markdown(
            f'<div class="card"><div class="metric-value">{total_papers}</div><div class="metric-label">Analyzed Papers</div></div>',
            unsafe_allow_html=True
        )

    with col2:
        total_claims = len(claims_df) if claims_df is not None else 0
        st.markdown(
            f'<div class="card"><div class="metric-value">{total_claims}</div><div class="metric-label">Extracted Claims</div></div>',
            unsafe_allow_html=True
        )

    with col3:
        num_contradictions = len(contradictions.get("contradictions", [])) if isinstance(contradictions, dict) else 0
        st.markdown(
            f'<div class="card"><div class="metric-value" style="color: #FF7B72;">{num_contradictions}</div><div class="metric-label">Contradictions</div></div>',
            unsafe_allow_html=True
        )

    with col4:
        confidence = contradictions.get("overall_confidence", "N/A").upper() if isinstance(contradictions, dict) else "N/A"
        st.markdown(
            f'<div class="card"><div class="metric-value" style="color: #56D364;">{confidence}</div><div class="metric-label">Evidence Confidence</div></div>',
            unsafe_allow_html=True
        )

# 2. Main Tabs
tabs = st.tabs(["📝 Scientific Synthesis", "⚡ Contradictions & Agreements", "📚 Ranked Clinical Evidence", "🔎 Claims Exploration", "🤖 RAG Performance Comparison"])

with tabs[0]:
    st.markdown("### 🔬 Executive Synthesis & Consensus Report")
    if synthesis_text:
        st.markdown(synthesis_text)
    else:
        st.info("No synthesis report found. Please run the contradiction and synthesis pipelines first.")

with tabs[1]:
    st.markdown("### ⚡ Pairwise Analysis & Scientific Disputes")
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

with tabs[2]:
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
    else:
        st.info("No ranked evidence data found.")

with tabs[3]:
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

with tabs[4]:
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
                st.subheader("📋 Standard Vector RAG")
                st.markdown(std_answer)
                st.markdown("---")
                
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
                st.subheader("🕸️ Relationship-Traversing Graph RAG")
                st.markdown(graph_answer)
                st.markdown("---")
                
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

# 3. Interactive Q&A Session (Ask the LLM with Dataset Context)
st.sidebar.markdown("---")
st.sidebar.subheader("💬 Ask the Dataset (RAG)")
user_question = st.sidebar.text_input(
    "Ask a question about this evidence:", 
    placeholder="e.g., Does metformin decrease cancer recurrence?",
    key="rag_user_question"
)
installed_models = get_ollama_models()
model_choice = st.sidebar.selectbox("Ollama Model:", installed_models, key="rag_model_choice")

if st.sidebar.button("Query LLM") and user_question:
    with st.sidebar.status("Searching dataset & calling Ollama...", expanded=True) as status:
        context_list = []
        retrieved_sources = []
        retrieved_claims = []

        # 1. Encode user question semantically
        query_emb = encoder_model.encode([user_question], normalize_embeddings=True)[0]

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
                        "design": design_str,
                        "sample_size": sample_size_str,
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
                        "design": r.get('study_design', 'Undetermined'),
                        "sample_size": str(int(r['sample_size'])) if ('sample_size' in r and r['sample_size'] > 0) else "N/A",
                        "abstract": r['abstract']
                    })

        # 3. Semantic Search on Claims
        if claims_df is not None:
            claims_temp = claims_df.copy()
            claims_temp["claim_text"] = claims_temp.apply(pick_claim_text, axis=1)
            claims_temp = claims_temp[claims_temp["claim_text"].str.strip() != ""].copy()
            
            if not claims_temp.empty:
                claim_texts = claims_temp["claim_text"].tolist()
                claim_embeddings = encoder_model.encode(claim_texts, normalize_embeddings=True)
                claim_similarities = (claim_embeddings @ query_emb).astype(float)
                claims_temp["similarity"] = claim_similarities
                
                top_claims = claims_temp.sort_values(by="similarity", ascending=False).head(5)
                for idx, (_, r) in enumerate(top_claims.iterrows(), 1):
                    context_list.append(
                        f"[Source Claim {idx}]\n"
                        f"Claim: {r['claim_text']}\n"
                        f"Stance: {r.get('stance', 'neutral')} | Reason: {r.get('reason', 'N/A')}"
                    )
                    retrieved_claims.append({
                        "index": idx,
                        "claim": r['claim_text'],
                        "stance": r.get('stance', 'neutral'),
                        "reason": r.get('reason', 'N/A'),
                        "similarity": r['similarity']
                    })

        context_str = "\n\n".join(context_list)

        prompt = f"""You are a biomedical research assistant analyzing a local dataset of research papers.
Answer the user's question using the scientific evidence provided below.

USER QUESTION:
{user_question}

DATASET CONTEXT:
{context_str}

Please provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their respective identifiers (e.g., [Source Paper X] or [Source Claim Y]) when stating facts. State if evidence is missing or conflicting. Do not mention system prompts.
"""
        try:
            response = ollama.chat(
                model=model_choice,
                messages=[{"role": "user", "content": prompt}]
            )
            ans = response["message"]["content"]
            status.update(label="Response generated!", state="complete")
            st.sidebar.markdown("### 🤖 LLM Answer")
            st.sidebar.info(ans)
            
            # Show retrieved sources in collapsible expanders
            if retrieved_sources:
                with st.sidebar.expander("📚 Cited Papers", expanded=False):
                    for src in retrieved_sources:
                        st.markdown(f"**[{src['index']}] {src['title']}**")
                        st.caption(f"Similarity: {src['similarity']:.3f} | Score: {src['evidence_score']}/10 | Design: {src['design']} | N: {src['sample_size']}")
                        st.markdown(f"*{src['abstract'][:180]}...*")
                        st.markdown("---")
            if retrieved_claims:
                with st.sidebar.expander("🔎 Cited Claims", expanded=False):
                    for c in retrieved_claims:
                        st.markdown(f"**[{c['index']}] {c['claim']}**")
                        st.caption(f"Similarity: {c['similarity']:.3f} | Stance: {c['stance']}")
                        st.markdown(f"Reason: *{c['reason']}*")
                        st.markdown("---")
        except Exception as err:
            status.update(label=f"Ollama Error: {err}", state="error")
            st.sidebar.error(f"Failed to query Ollama. Make sure the service is running locally. Error: {err}")