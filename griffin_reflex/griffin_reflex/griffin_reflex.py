import sys
import os
import asyncio
import json
import ast
import reflex as rx
import plotly.graph_objects as go
import networkx as nx
import pandas as pd
import numpy as np
import subprocess

from griffin_reflex.pages.onboarding import onboarding
from griffin_reflex.pages.workspace import workspace
from griffin_reflex.pages.dashboard import dashboard
from griffin_reflex.pages.projects import projects
from griffin_reflex.pages.settings import settings

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from typing import Any, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATASET_DIR = os.path.join(ROOT_DIR, "dataset")

from src.shared.ui_helpers import format_reasoning_text, parse_embedding, audit_methodology, get_ollama_model_names, get_gemini_model_names

def _peer_review_sync(api_key, report, focus_area, gemini_model):
    from src.agents.peer_review_agent import run_peer_review
    return run_peer_review(api_key, report, focus_area, gemini_model)

def _overseer_sync(api_key, report, custom_inst, gemini_model):
    from src.agents.report_agent import generate_overseer_report
    extra=""
    rp=os.path.join(DATASET_DIR,"clean_papers_with_embeddings.csv")
    cp=os.path.join(DATASET_DIR,"contradictions.json")
    if os.path.exists(rp):
        try: extra+=pd.read_csv(rp).head(10).to_string()
        except Exception: pass
    if os.path.exists(cp):
        try: extra+=json.dumps(json.load(open(cp)), indent=2)[:4000]
        except Exception: pass
    return generate_overseer_report(api_key, report, extra, custom_inst, gemini_model)

def _qa_sync(api_key, report, gemini_model):
    from src.agents.validation_agent import run_qa_audit
    return run_qa_audit(api_key, report, gemini_model)

def _refine_sync(api_key, report, instr, gemini_model):
    from src.agents.refinement_agent import refine_report_section
    return refine_report_section(api_key, report, instr, gemini_model)

def _benchmark_sync(question, model_choice):
    import time
    from src.core import graph_rag
    from sentence_transformers import SentenceTransformer
    ranked_df, contradictions = graph_rag.load_data(
        ranked_path=os.path.join(DATASET_DIR, "ranked_papers.csv"),
        embeddings_path=os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv"),
        contradictions_path=os.path.join(DATASET_DIR, "contradictions.json")
    )
    enc=SentenceTransformer('BAAI/bge-small-en-v1.5')
    
    t=time.time()
    std_ctx, std_src = graph_rag.get_standard_rag_context(question, enc, ranked_df, 3)
    std_rt=time.time()-t
    std_ans, std_gen = graph_rag.generate_answer(f"Answer using: {std_ctx}\nQ:{question}", model_choice)
    t2=time.time()
    graph_ctx, graph_src, graph_rel = graph_rag.get_graph_rag_context(question, enc, ranked_df, contradictions, 3)
    graph_rt=time.time()-t2
    graph_ans, graph_gen = graph_rag.generate_answer(f"Answer using: {graph_ctx}\nQ:{question}", model_choice)
    return {
        "std_ans": std_ans, "std_lat": f"{std_rt+std_gen:.1f}s", "std_cit": str(len(std_src)), "std_words": str(len(std_ans.split())), "std_sources_data": std_src,
        "graph_ans": graph_ans, "graph_lat": f"{graph_rt+graph_gen:.1f}s", "graph_cit": str(len(graph_src)), "graph_words": str(len(graph_ans.split())), "graph_sources_data": graph_src, "graph_relations_data": graph_rel
    }

def _graph_sync():
    con_path=os.path.join(DATASET_DIR,"contradictions.json")
    if not os.path.exists(con_path): return None
    data=json.load(open(con_path))
    G=nx.Graph()
    def add(items,color):
        for it in items[:50]:
            a=(it.get("claim_a_title","Unknown A")[:40]+"...").strip()
            b=(it.get("claim_b_title","Unknown B")[:40]+"...").strip()
            G.add_node(a); G.add_node(b)
            G.add_edge(a,b,color=color)
    add(data.get("agreements",[]),"green")
    add(data.get("partial_agreements",[]),"orange")
    add(data.get("contradictions",[]),"red")
    if len(G.nodes)==0: G.add_node("No Data")
    pos=nx.spring_layout(G,k=0.5,iterations=50)
    traces=[]
    for u,v,d in G.edges(data=True):
        x0,y0=pos[u]; x1,y1=pos[v]
        traces.append(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],line=dict(width=1.5,color=d.get('color','#888')),mode='lines',hoverinfo='none'))
    nx_,ny_,nt=[],[],[]
    for n in G.nodes():
        x,y=pos[n]; nx_.append(x); ny_.append(y); nt.append(str(n))
    traces.append(go.Scatter(x=nx_,y=ny_,mode='markers+text',text=nt,textposition="bottom center",textfont=dict(size=9,color="#c9d1d9"),marker=dict(size=12,color="#4F46E5",line_width=2,line_color="white")))
    fig=go.Figure(data=traces,layout=go.Layout(title='Knowledge Graph',showlegend=False,hovermode='closest',margin=dict(b=20,l=5,r=5,t=40),xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)'))
    return fig

def _run_synthesis_sync(query, model_name, options):
    from src.agents.consensus_agent import analyze_consensus
    ranked_path=os.path.join(DATASET_DIR,"ranked_papers.csv")
    con_path=os.path.join(DATASET_DIR,"contradictions.json")
    
    temp_sources = []
    if os.path.exists(ranked_path):
        temp_sources = pd.read_csv(ranked_path).to_dict(orient="records")
    
    temp_relations = []
    if os.path.exists(con_path):
        try:
            with open(con_path, "r", encoding="utf-8") as f:
                temp_contr = json.load(f)
            for r in temp_contr.get("contradictions", []): temp_relations.append(dict(r, type="contradicts"))
            for r in temp_contr.get("agreements", []): temp_relations.append(dict(r, type="agrees"))
            for r in temp_contr.get("partial_agreements", []): temp_relations.append(dict(r, type="partial_agrees"))
        except Exception: pass
        
    res = analyze_consensus(query, temp_sources, temp_relations, model_name, options)
    os.makedirs(DATASET_DIR, exist_ok=True)
    with open(os.path.join(DATASET_DIR, "consensus_report.md"), "w", encoding="utf-8") as f:
        f.write(res.get("consensus_report", ""))
    return res

def _run_contradiction_pipeline_sync(extractor, detector):
    from src.core.claim_extractor import extract_claims
    from src.core.contradiction_detector import run_detector
    extract_claims(
        input_path=os.path.join(DATASET_DIR, "clean_papers.csv"),
        output_path=os.path.join(DATASET_DIR, "claims.csv"),
        model=extractor,
        limit=50,
        resume=False
    )
    run_detector(
        input_path=os.path.join(DATASET_DIR, "claims.csv"),
        output_text=os.path.join(DATASET_DIR, "contradictions.txt"),
        output_csv=os.path.join(DATASET_DIR, "contradictions.csv"),
        output_json=os.path.join(DATASET_DIR, "contradictions.json"),
        output_report=os.path.join(DATASET_DIR, "contradiction_report.md"),
        model=detector,
        embedding_model="BAAI/bge-small-en-v1.5",
        evidence_file=os.path.join(DATASET_DIR, "ranked_papers.csv"),
        max_pairs=20,
        similarity_threshold=0.45,
        skip_embeddings=False
    )
    return True

def _rag_chat_sync(user_input):
    from sentence_transformers import SentenceTransformer
    encoder_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    query_emb = encoder_model.encode([user_input], normalize_embeddings=True)[0]
    
    retrieved_sources = []
    emb_path = os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv")
    if os.path.exists(emb_path):
        ranked_df = pd.read_csv(emb_path)
        ranked_df["embedding"] = ranked_df["embedding"].apply(lambda x: parse_embedding(x) if pd.notna(x) else np.array([0.0]*384, dtype=np.float32))
        
        emb_list = list(ranked_df["embedding"])
        if emb_list:
            embeddings_matrix = np.vstack(emb_list)
            similarities = (embeddings_matrix @ query_emb).astype(float)
            search_df = ranked_df.copy()
            search_df["similarity"] = similarities
            top_papers = search_df.sort_values(by="similarity", ascending=False).head(5)
            for idx, (_, r) in enumerate(top_papers.iterrows(), 1):
                retrieved_sources.append({
                    "index": idx,
                    "title": str(r.get("title", "")),
                    "similarity": float(r.get("similarity", 0.0)),
                    "evidence_score": float(r.get('evidence_score', 0)),
                    "abstract": str(r.get('abstract', ''))
                })
    return retrieved_sources

def _ollama_generate_sync(prompt, model, options):
    from src.shared.llm import chat as llm_chat
    messages = [{"role": "user", "content": prompt}]
    res = llm_chat(
        model,
        messages=messages,
        task="chat",
        user_options=options,
    )
    return res["message"]["content"]

from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class ChatSource:
    index: int
    title: str
    similarity: float
    evidence_score: float
    abstract: str

@dataclass
class ChatMessage:
    role: str
    content: str
    sources: list[ChatSource]

class State(rx.State):
    """The app state."""
    # Sidebar Settings
    query: str = ""
    api_key: str = ""
    sc_api_key: str = ""
    email: str = "test@example.com"
    
    gemini_model_list: list[str] = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-pro-latest", "gemini-1.5-flash-latest"]
    gemini_model_choice: str = "gemini-1.5-pro"
    
    installed_models: list[str] = ["gemma4:e4b", "koesn/llama3-openbiollm-8b:latest", "llama3.1:8b", "gemma3:4b", "gemma3:1b", "qwen3.5:9b"]
    
    use_global_model: bool = False
    global_model_choice: str = "llama3.1:8b"
    use_custom_routing: bool = False
    model_routing: dict[str, str] = {
        "planner": "llama3.1:8b",
        "claim_extractor": "llama3.1:8b",
        "contradiction_detector": "qwen3.5:9b",
        "consensus_analyst": "koesn/llama3-openbiollm-8b:latest",
        "synthesis": "llama3.1:8b",
        "experiment_planner": "llama3.1:8b"
    }
    
    llm_temperature: float = 0.7
    llm_num_ctx: str = "8192"
    llm_num_predict: str = "4096"
    llm_think: bool = True
    llm_reasoning_mode: str = "Display in Expander"
    
    rag_model_choice: str = "llama3.1:8b"
    rag_chat_input: str = ""
    chat_history: list[ChatMessage] = []
    is_chat_running: bool = False

    # Tab 0 Settings
    logs: list[str] = []
    is_running: bool = False
    show_confirm_dialog: bool = False
    force_fresh: bool = False
    use_manual_agents: bool = False
    sel_claim_extractor: bool = True
    sel_consensus: bool = True
    sel_evidence: bool = True
    sel_experiment: bool = True
    sel_contradiction: bool = True
    sel_eln: bool = True
    sel_synthesis: bool = True
    
    collector_limits: dict[str, int] = {
        "PubMed": 20, "PMC": 20, "SemanticScholar": 20, "OpenAlex": 20,
        "ClinicalTrials": 20, "bioRxiv": 20, "ChEMBL": 20, "UniProt": 20,
        "PubChem": 20, "dbSNP": 20
    }
    refinement_instruction: str = ""
    
    # Phase 3/4 State
    synthesis_report: str = "Click 'Load Synthesis' to view."
    peer_review_critique: str = ""
    is_peer_review_running: bool = False
    peer_review_focus: str = "Methodological flaws, logical gaps, and unsupported claims"
    is_synthesis_running: bool = False
    
    contradictions_data: list[list[str]] = []
    agreements_data: list[list[str]] = []
    partial_agreements_data: list[list[str]] = []
    is_contradiction_running: bool = False
    
    overseer_report: str = "Click 'Generate Report' to run the Grounded Overseer."
    overseer_custom_inst: str = ""
    is_overseer_running: bool = False
    
    # Phase 5/6 State
    ranked_papers_data: list[dict[str, str]] = []
    min_evidence_score: int = 1
    paper_search_query: str = ""
    
    claims_data: list[list[str]] = []
    claims_search: str = ""
    show_support: bool = True
    show_contradict: bool = True
    show_neutral: bool = True

    eval_question: str = ""
    eval_running: bool = False
    std_latency: str = "--"
    std_citations: str = "--"
    std_words: str = "--"
    std_ans: str = ""
    std_sources_data: list[dict[str, Any]] = []
    graph_latency: str = "--"
    graph_citations: str = "--"
    graph_words: str = "--"
    graph_ans: str = ""
    graph_sources_data: list[dict[str, Any]] = []
    graph_relations_data: list[dict[str, Any]] = []

    qa_score: int = -1
    qa_feedback: str = ""
    qa_issues: list[str] = []
    is_qa_running: bool = False
    
    refine_instruction: str = ""
    is_refine_running: bool = False
    
    # Phase 7 State
    is_graph_running: bool = False
    graph_figure: go.Figure = go.Figure()
    
    # Trace output UI
    pipeline_trace_visible: bool = False
    verification_status: str = ""
    verification_trace: list[dict[str, Any]] = []
    routing_stats: list[dict[str, Any]] = []
    fallback_warnings: list[str] = []
    consensus_report: str = ""
    experiment_protocol: str = ""
    eln_entry: str = ""
    fetched_sources: list[dict[str, Any]] = []
    matched_claims: list[dict[str, Any]] = []
    graph_relations_trace: list[dict[str, Any]] = []

    @rx.event
    async def on_load(self):
        loop=asyncio.get_running_loop()
        self.installed_models = await loop.run_in_executor(None, get_ollama_model_names)
        self.gemini_model_list = await loop.run_in_executor(None, get_gemini_model_names, self.api_key)

    @rx.event
    async def set_api_key(self, val: str): 
        self.api_key = val
        loop=asyncio.get_running_loop()
        self.gemini_model_list = await loop.run_in_executor(None, get_gemini_model_names, self.api_key)
        
    @rx.event
    def set_sc_api_key(self, val: str): self.sc_api_key = val
    @rx.event
    def set_query(self, val: str): self.query = val
    @rx.event
    def set_email(self, val: str): self.email = val
    @rx.event
    def set_gemini_model_choice(self, val: str): self.gemini_model_choice = val
    @rx.event
    def set_use_global_model(self, val: bool): self.use_global_model = val
    @rx.event
    def set_global_model_choice(self, val: str): self.global_model_choice = val
    @rx.event
    def set_use_custom_routing(self, val: bool): self.use_custom_routing = val
    
    @rx.event
    def set_route_planner(self, val: str): self.model_routing["planner"] = val
    @rx.event
    def set_route_claim_extractor(self, val: str): self.model_routing["claim_extractor"] = val
    @rx.event
    def set_route_contradiction_detector(self, val: str): self.model_routing["contradiction_detector"] = val
    @rx.event
    def set_route_consensus_analyst(self, val: str): self.model_routing["consensus_analyst"] = val
    @rx.event
    def set_route_synthesis(self, val: str): self.model_routing["synthesis"] = val
    @rx.event
    def set_route_experiment_planner(self, val: str): self.model_routing["experiment_planner"] = val

    @rx.event
    def set_llm_temperature(self, val: list[float]): self.llm_temperature = val[0]
    @rx.event
    def set_llm_num_ctx(self, val: str): self.llm_num_ctx = val
    @rx.event
    def set_llm_num_predict(self, val: str): self.llm_num_predict = val
    @rx.event
    def set_llm_think(self, val: bool): self.llm_think = val
    @rx.event
    def set_llm_reasoning_mode(self, val: str): self.llm_reasoning_mode = val
    @rx.event
    def set_rag_model_choice(self, val: str): self.rag_model_choice = val
    @rx.event
    def set_rag_chat_input(self, val: str): self.rag_chat_input = val
    @rx.event
    def clear_chat_history(self): self.chat_history = []
    
    @rx.event
    def set_collector_limit(self, k: str, val: int): self.collector_limits[k] = val
    @rx.event
    def set_limit_pubmed(self, val: str):
        try: self.collector_limits["PubMed"] = int(val)
        except: pass
    @rx.event
    def set_limit_pmc(self, val: str):
        try: self.collector_limits["PMC"] = int(val)
        except: pass
    @rx.event
    def set_limit_semanticscholar(self, val: str):
        try: self.collector_limits["SemanticScholar"] = int(val)
        except: pass
    @rx.event
    def set_limit_openalex(self, val: str):
        try: self.collector_limits["OpenAlex"] = int(val)
        except: pass
    @rx.event
    def set_limit_clinicaltrials(self, val: str):
        try: self.collector_limits["ClinicalTrials"] = int(val)
        except: pass
    @rx.event
    def set_limit_biorxiv(self, val: str):
        try: self.collector_limits["bioRxiv"] = int(val)
        except: pass
    @rx.event
    def set_limit_chembl(self, val: str):
        try: self.collector_limits["ChEMBL"] = int(val)
        except: pass
    @rx.event
    def set_limit_uniprot(self, val: str):
        try: self.collector_limits["UniProt"] = int(val)
        except: pass
    @rx.event
    def set_limit_pubchem(self, val: str):
        try: self.collector_limits["PubChem"] = int(val)
        except: pass
    @rx.event
    def set_limit_dbsnp(self, val: str):
        try: self.collector_limits["dbSNP"] = int(val)
        except: pass
    @rx.event
    def set_force_fresh(self, val: bool): self.force_fresh = val
    @rx.event
    def set_use_manual_agents(self, val: bool): self.use_manual_agents = val
    @rx.event
    def set_sel_claim_extractor(self, val: bool): self.sel_claim_extractor = val
    @rx.event
    def set_sel_consensus(self, val: bool): self.sel_consensus = val
    @rx.event
    def set_sel_evidence(self, val: bool): self.sel_evidence = val
    @rx.event
    def set_sel_experiment(self, val: bool): self.sel_experiment = val
    @rx.event
    def set_sel_contradiction(self, val: bool): self.sel_contradiction = val
    @rx.event
    def set_sel_eln(self, val: bool): self.sel_eln = val
    @rx.event
    def set_sel_synthesis(self, val: bool): self.sel_synthesis = val
    @rx.event
    def set_refinement_instruction(self, val: str): self.refinement_instruction = val
    @rx.event
    def close_confirm_dialog(self): self.show_confirm_dialog = False

    @rx.event
    def set_min_evidence_score(self, val: list[int]): self.min_evidence_score = val[0]
    @rx.event
    def set_paper_search_query(self, val: str): self.paper_search_query = val
    @rx.event
    def set_claims_search(self, val: str): self.claims_search = val
    @rx.event
    def set_show_support(self, val: bool): self.show_support = val
    @rx.event
    def set_show_contradict(self, val: bool): self.show_contradict = val
    @rx.event
    def set_show_neutral(self, val: bool): self.show_neutral = val
    @rx.event
    def set_eval_question(self, val: str): self.eval_question = val
    @rx.event
    def set_refine_instruction(self, val: str): self.refine_instruction = val
    @rx.event
    def set_peer_review_focus(self, val: str): self.peer_review_focus = val
    @rx.event
    def set_overseer_custom_inst(self, val: str): self.overseer_custom_inst = val

    @rx.var
    def filtered_ranked_papers(self) -> list[dict[str, str]]:
        out=[]
        for row in self.ranked_papers_data:
            try:
                if float(row["score"]) < float(self.min_evidence_score): continue
            except Exception: pass
            
            if self.paper_search_query:
                query = self.paper_search_query.lower()
                title = str(row.get("title", "")).lower()
                abstract = str(row.get("abstract", "")).lower()
                if query not in title and query not in abstract:
                    continue
                    
            out.append(row)
        return out

    @rx.var
    def filtered_claims(self) -> list[list[str]]:
        res = []
        for row in self.claims_data:
            stance = row[2].lower()
            if not self.show_support and "support" in stance: continue
            if not self.show_contradict and "contradict" in stance: continue
            if not self.show_neutral and "neutral" in stance: continue
            if self.claims_search and self.claims_search.lower() not in row[1].lower(): continue
            res.append(row)
        return res
        
    @rx.var
    def agent_statuses(self) -> list[dict[str, str]]:
        return [
            {"name": "Planner Agent", "status": "ACTIVE" if self.is_running else "IDLE", "color": "green" if self.is_running else "gray"},
            {"name": "Synthesis Agent", "status": "ACTIVE" if self.is_synthesis_running else "IDLE", "color": "green" if self.is_synthesis_running else "gray"},
            {"name": "Peer Review Agent", "status": "ACTIVE" if self.is_peer_review_running else "IDLE", "color": "green" if self.is_peer_review_running else "gray"},
            {"name": "Contradiction Agent", "status": "ACTIVE" if self.is_contradiction_running else "IDLE", "color": "green" if self.is_contradiction_running else "gray"},
            {"name": "Overseer Agent", "status": "ACTIVE" if self.is_overseer_running else "IDLE", "color": "green" if self.is_overseer_running else "gray"},
            {"name": "QA Agent", "status": "ACTIVE" if self.is_qa_running else "IDLE", "color": "green" if self.is_qa_running else "gray"},
            {"name": "Refinement Agent", "status": "ACTIVE" if self.is_refine_running else "IDLE", "color": "green" if self.is_refine_running else "gray"},
        ]

    @rx.var
    def timeline_events(self) -> list[dict[str, str]]:
        events = []
        for row in self.ranked_papers_data:
            year = str(row.get("year", ""))
            title = str(row.get("title", ""))
            if year and year != "nan":
                events.append({"year": year, "title": title[:70] + "..." if len(title) > 70 else title})
        events.sort(key=lambda x: x["year"])
        return events
        
    @rx.var
    def get_actual_model_routing(self) -> dict[str, str]:
        if self.use_global_model:
            return {
                "planner": self.global_model_choice,
                "claim_extractor": self.global_model_choice,
                "contradiction_detector": self.global_model_choice,
                "consensus_analyst": self.global_model_choice,
                "synthesis": self.global_model_choice,
                "experiment_planner": self.global_model_choice
            }
        elif self.use_custom_routing:
            return self.model_routing
        else:
            return {
                "planner": "llama3.1:8b", "claim_extractor": "llama3.1:8b", "contradiction_detector": "qwen3.5:9b",
                "consensus_analyst": "koesn/llama3-openbiollm-8b:latest", "synthesis": "llama3.1:8b", "experiment_planner": "llama3.1:8b"
            }

    async def run_rag_chat(self):
        if not self.rag_chat_input.strip(): return
        msg = ChatMessage(role="user", content=self.rag_chat_input, sources=[])
        self.chat_history.append(msg)
        prompt = self.rag_chat_input
        self.rag_chat_input = ""
        self.is_chat_running = True
        yield
        
        loop = asyncio.get_running_loop()
        retrieved_sources = await loop.run_in_executor(None, _rag_chat_sync, prompt)
        
        context_list = []
        for src in retrieved_sources:
            context_list.append(f"[Source Paper {src['index']}]\nTitle: {src['title']}\nEvidence Score: {src['evidence_score']}/10\nAbstract: {src['abstract']}")
        
        full_prompt = f"You are a biomedical research assistant.\nAnswer the user's question using the scientific evidence provided below.\n\nUSER QUESTION:\n{prompt}\n\nDATASET CONTEXT:\n{chr(10).join(context_list)}\n\nPlease provide a structured, concise response backed by the contextual evidence above. Cite the specific sources using their identifiers."
        
        llm_opts = {"temperature": self.llm_temperature, "num_ctx": int(self.llm_num_ctx)}
        answer = await loop.run_in_executor(None, _ollama_generate_sync, full_prompt, self.rag_model_choice, llm_opts)
        
        typed_sources = [ChatSource(**src) for src in retrieved_sources]
        self.chat_history.append(ChatMessage(role="assistant", content=answer, sources=typed_sources))
        self.is_chat_running = False
        yield

    async def prepare_query_planner(self):
        if not self.query:
            self.logs = ["Error: Please enter a query first."]
            return
        self.show_confirm_dialog = True
        
    async def run_query_planner(self):
        self.show_confirm_dialog = False
        self.is_running = True
        self.pipeline_trace_visible = False
        self.logs = [f"Starting Query Planner for: {self.query}"]
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_backend_pipeline)
        log_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "terminal.log"))
        last_pos = 0
        while not task.done():
            if os.path.exists(log_file_path):
                if os.path.getsize(log_file_path) < last_pos:
                    last_pos = 0
                with open(log_file_path, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()
                    if new_lines:
                        for line in new_lines: self.logs.append(line.strip())
                        yield
            await asyncio.sleep(0.5)
            
        self.is_running = False
        self.logs.append("Execution Complete!")
        
        # Load execution trace
        trace_path = os.path.join(DATASET_DIR, "execution_trace.json")
        if os.path.exists(trace_path):
            try:
                trace_data = json.load(open(trace_path, "r", encoding="utf-8"))
                self.verification_status = trace_data.get("verification", {}).get("status", "review").upper()
                self.verification_trace = trace_data.get("verification_trace", [])
                
                # Transform routing_stats dict to list of dicts for data_table
                rs_list = []
                for k, v in trace_data.get("routing_stats", {}).items():
                    rs_list.append({
                        "Stage": k.replace("_", " ").title(),
                        "Requested": v.get("requested", ""),
                        "Resolved": v.get("resolved", ""),
                        "Latency": f"{v.get('duration_sec', 0.0):.2f}s",
                        "Status": "⚠️ Fallback" if v.get("fallback_logs") else "✅ OK"
                    })
                self.routing_stats = rs_list
                
                self.consensus_report = trace_data.get("consensus", {}).get("consensus_report", "")
                self.experiment_protocol = trace_data.get("experiment_protocol", "")
                self.eln_entry = trace_data.get("eln_entry", "")
                self.fetched_sources = trace_data.get("sources", [])
                self.matched_claims = trace_data.get("claims", [])
                self.graph_relations_trace = trace_data.get("relations", [])
                
                # Render <think> tags correctly for consensus report
                self.consensus_report = format_reasoning_text(self.consensus_report, self.llm_reasoning_mode)
                
                self.pipeline_trace_visible = True
            except Exception as e:
                self.logs.append(f"Failed to load execution trace: {e}")
        yield
        
    def execute_backend_pipeline(self):
        import subprocess
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cli_path = os.path.join(root_dir, "run_pipeline_cli.py")
        
        forced_agents = ""
        if self.use_manual_agents:
            fa = []
            if self.sel_claim_extractor: fa.append("claim_extractor")
            if self.sel_consensus: fa.append("consensus_analyst")
            if self.sel_evidence: fa.append("evidence_ranker")
            if self.sel_experiment: fa.append("experiment_planner")
            if self.sel_contradiction: fa.append("contradiction_detector")
            if self.sel_eln: fa.append("eln_assistant")
            if self.sel_synthesis: fa.append("synthesis")
            forced_agents = ",".join(fa)
            
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["GRIFFIN_ROUTING"] = json.dumps(self.get_actual_model_routing)
        env["GRIFFIN_LLM_OPTS"] = json.dumps({"temperature": self.llm_temperature, "num_ctx": int(self.llm_num_ctx), "num_predict": int(self.llm_num_predict)})
        
        cmd = [sys.executable, cli_path, self.query, self.email, self.api_key, self.sc_api_key]
        
        try:
            with open(os.path.join(root_dir, "dataset", "terminal.log"), "a", encoding="utf-8") as log_file:
                subprocess.run(cmd, cwd=root_dir, check=True, env=env, stdout=log_file, stderr=subprocess.STDOUT)
        except Exception as e:
            with open(os.path.join(root_dir, "dataset", "terminal.log"), "a", encoding="utf-8") as f:
                f.write(f"\nPipeline Error: {str(e)}\n")

    def load_synthesis(self):
        path = os.path.join(DATASET_DIR, "consensus_report.md")
        if not os.path.exists(path): path = os.path.join(DATASET_DIR, "final_synthesis.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()
                self.synthesis_report = format_reasoning_text(raw_text, self.llm_reasoning_mode)
        else:
            self.synthesis_report = "Report not found. Did you run the pipeline yet?"
            
    async def run_synthesis_agent(self):
        self.is_synthesis_running=True; yield
        loop=asyncio.get_running_loop()
        opts = {"temperature": self.llm_temperature, "num_ctx": int(self.llm_num_ctx)}
        res = await loop.run_in_executor(None, _run_synthesis_sync, self.query, self.get_actual_model_routing.get("consensus_analyst", "llama3.1:8b"), opts)
        self.synthesis_report = format_reasoning_text(res.get("consensus_report", ""), self.llm_reasoning_mode)
        self.is_synthesis_running=False; yield

    async def run_peer_review(self):
        self.is_peer_review_running=True; yield
        loop=asyncio.get_running_loop()
        res=await loop.run_in_executor(None, _peer_review_sync, self.api_key, self.synthesis_report, self.peer_review_focus, self.gemini_model_choice)
        self.peer_review_critique=res
        self.is_peer_review_running=False; yield

    def load_contradictions(self):
        path = os.path.join(DATASET_DIR, "contradictions.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                c_rows, a_rows, p_rows = [], [], []
                for c in data.get("contradictions", []): c_rows.append([c.get("claim_a_title", "")[:100], c.get("claim_b_title", "")[:100], str(c.get("cosine_similarity", 0)), c.get("explanation", "")])
                for a in data.get("agreements", []): a_rows.append([a.get("claim_a_title", "")[:100], a.get("claim_b_title", "")[:100], "N/A", a.get("explanation", "")])
                for p in data.get("partial_agreements", []): p_rows.append([p.get("claim_a_title", "")[:100], p.get("claim_b_title", "")[:100], "N/A", p.get("explanation", "")])
                self.contradictions_data = c_rows
                self.agreements_data = a_rows
                self.partial_agreements_data = p_rows

    async def run_contradiction_agent(self):
        self.is_contradiction_running=True; yield
        loop=asyncio.get_running_loop()
        ext = self.get_actual_model_routing.get("claim_extractor", "llama3.1:8b")
        det = self.get_actual_model_routing.get("contradiction_detector", "qwen3.5:9b")
        await loop.run_in_executor(None, _run_contradiction_pipeline_sync, ext, det)
        self.load_contradictions()
        self.is_contradiction_running=False; yield

    async def run_overseer(self):
        self.is_overseer_running=True; yield
        loop=asyncio.get_running_loop()
        res=await loop.run_in_executor(None, _overseer_sync, self.api_key, self.synthesis_report, self.overseer_custom_inst, self.gemini_model_choice)
        self.overseer_report=res
        self.is_overseer_running=False; yield

    def load_ranked_evidence(self):
        path = os.path.join(DATASET_DIR, "clean_papers_with_embeddings.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                rows = []
                for _, row in df.iterrows():
                    flags = audit_methodology(row)
                    r = {
                        "title": str(row.get("title", "")),
                        "score": str(row.get("evidence_score", "")),
                        "study_design": str(row.get("study_design", "")),
                        "sample_size": str(row.get("sample_size", "")),
                        "source": str(row.get("source", "")),
                        "year": str(row.get("year", "")),
                        "flags": " ".join([f"🔴 {f}" if "⚠️" in f or "❓" in f else f"🟢 {f}" for f in flags]),
                        "abstract": str(row.get("abstract", ""))
                    }
                    rows.append(r)
                self.ranked_papers_data = rows
            except Exception as e:
                print(e)
                
    def load_claims(self):
        path = os.path.join(DATASET_DIR, "claims.csv")
        if not os.path.exists(path): path = os.path.join(DATASET_DIR, "claims_dataset.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                cols = ["title", "claim", "stance", "reason"]
                rows = []
                for _, row in df.iterrows():
                    r = []
                    for c in cols: r.append(str(row.get(c, "")))
                    rows.append(r)
                self.claims_data = rows
            except Exception as e:
                print(e)
                
    async def run_qa_audit(self):
        self.is_qa_running=True; yield
        loop=asyncio.get_running_loop()
        res=await loop.run_in_executor(None, _qa_sync, self.api_key, self.overseer_report, self.gemini_model_choice)
        self.qa_score=res.get("score",0)
        self.qa_feedback=res.get("feedback","")
        self.qa_issues=res.get("issues",[])
        self.is_qa_running=False; yield

    async def run_refinement(self):
        self.is_refine_running=True; yield
        loop=asyncio.get_running_loop()
        res=await loop.run_in_executor(None, _refine_sync, self.api_key, self.overseer_report, self.refine_instruction, self.gemini_model_choice)
        self.overseer_report=res
        self.is_refine_running=False; yield

    async def run_benchmark(self):
        self.eval_running=True; self.std_latency="--"; self.graph_latency="--"; yield
        loop=asyncio.get_running_loop()
        mc = self.global_model_choice if self.use_global_model else self.get_actual_model_routing.get("synthesis", "llama3.1:8b")
        res=await loop.run_in_executor(None, _benchmark_sync, self.eval_question, mc)
        self.std_latency=res["std_lat"]; self.std_citations=res["std_cit"]
        self.std_ans=format_reasoning_text(res["std_ans"], self.llm_reasoning_mode)
        self.std_words=res["std_words"]; self.std_sources_data=res["std_sources_data"]
        
        self.graph_latency=res["graph_lat"]; self.graph_citations=res["graph_cit"]
        self.graph_ans=format_reasoning_text(res["graph_ans"], self.llm_reasoning_mode)
        self.graph_words=res["graph_words"]; self.graph_sources_data=res["graph_sources_data"]
        self.graph_relations_data=res["graph_relations_data"]
        self.eval_running=False; yield

    async def load_knowledge_graph(self):
        self.is_graph_running=True; yield
        loop=asyncio.get_running_loop()
        fig=await loop.run_in_executor(None, _graph_sync)
        self.graph_figure=fig
        self.is_graph_running=False; yield


# ── Design tokens (shared style helpers) ──────────────────────────────────────
_FONT = "'DM Sans', system-ui, -apple-system, sans-serif"
_FONT_DISPLAY = "'Outfit', 'DM Sans', system-ui, sans-serif"
_FONT_MONO = "'JetBrains Mono', ui-monospace, monospace"

_SIDEBAR_BG = "linear-gradient(180deg, rgba(11,16,32,0.98) 0%, rgba(7,10,18,0.99) 100%)"
_PAGE_BG = (
    "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(99,102,241,0.16) 0%, transparent 55%),"
    "radial-gradient(ellipse 60% 40% at 90% 10%, rgba(56,189,248,0.10) 0%, transparent 50%),"
    "linear-gradient(180deg, #070a12 0%, #0b1020 100%)"
)
_CARD_BG = "linear-gradient(145deg, rgba(17,24,39,0.88) 0%, rgba(11,16,32,0.78) 100%)"
_CARD_BORDER = "1px solid rgba(148,163,184,0.14)"
_EASE = "cubic-bezier(0.22, 1, 0.36, 1)"

_section_label = dict(
    size="2",
    weight="bold",
    color="var(--accent-11)",
    letter_spacing="0.08em",
    style={"textTransform": "uppercase", "fontFamily": _FONT_DISPLAY},
)

_input_style = dict(
    width="100%",
    size="3",
    radius="large",
    style={"fontFamily": _FONT, "minHeight": "42px"},
)

_btn_primary = dict(
    size="3",
    radius="large",
    variant="solid",
    color_scheme="indigo",
    style={
        "fontFamily": _FONT_DISPLAY,
        "fontWeight": "600",
        "minHeight": "44px",
        "padding": "0 22px",
        "boxShadow": "0 6px 20px rgba(99,102,241,0.35)",
        "transition": f"all 0.28s {_EASE}",
        "cursor": "pointer",
    },
)

_btn_ghost = dict(
    size="2",
    radius="large",
    variant="soft",
    color_scheme="gray",
    style={
        "fontFamily": _FONT_DISPLAY,
        "fontWeight": "600",
        "minHeight": "40px",
        "transition": f"all 0.25s {_EASE}",
        "cursor": "pointer",
    },
)

_card_style = dict(
    width="100%",
    padding="5",
    radius="large",
    style={
        "background": _CARD_BG,
        "border": _CARD_BORDER,
        "backdropFilter": "blur(16px)",
        "boxShadow": "0 8px 32px rgba(0,0,0,0.3)",
        "transition": f"transform 0.35s {_EASE}, box-shadow 0.35s {_EASE}, border-color 0.3s ease",
        "animation": f"gxFadeInUp 0.5s {_EASE} both",
    },
)

_heading_display = dict(
    style={
        "fontFamily": _FONT_DISPLAY,
        "letterSpacing": "-0.03em",
        "background": "linear-gradient(120deg, #e0e7ff 0%, #818cf8 45%, #38bdf8 100%)",
        "WebkitBackgroundClip": "text",
        "WebkitTextFillColor": "transparent",
        "backgroundClip": "text",
    },
)

_tab_trigger = dict(
    style={
        "fontFamily": _FONT,
        "fontWeight": "500",
        "fontSize": "0.92rem",
        "padding": "12px 18px",
        "minHeight": "44px",
        "borderRadius": "999px",
        "transition": f"all 0.28s {_EASE}",
        "cursor": "pointer",
    },
)


def sidebar():
    return rx.box(
        rx.vstack(
            # Brand header
            rx.hstack(
                rx.box(
                    rx.text("🧬", size="5"),
                    padding="2",
                    border_radius="12px",
                    style={
                        "background": "linear-gradient(135deg, rgba(99,102,241,0.3), rgba(56,189,248,0.2))",
                        "border": "1px solid rgba(129,140,248,0.35)",
                        "boxShadow": "0 0 20px rgba(99,102,241,0.25)",
                    },
                ),
                rx.vstack(
                    rx.heading("Griffin Bio", size="5", style={"fontFamily": _FONT_DISPLAY, "letterSpacing": "-0.02em"}),
                    rx.text("Controls", size="1", color="var(--gray-10)", weight="medium"),
                    spacing="0",
                    align_items="flex-start",
                ),
                spacing="3",
                align_items="center",
                width="100%",
                padding_bottom="3",
            ),
            rx.divider(style={"opacity": "0.4"}),
            rx.scroll_area(
                rx.vstack(
                    rx.text("🔑 Credentials & Settings", **_section_label),
                    rx.input(placeholder="PubMed Email", default_value="test@example.com", on_change=State.set_email, **_input_style),
                    rx.input(placeholder="Semantic Scholar Key", type="password", on_change=State.set_sc_api_key, **_input_style),
                    rx.input(placeholder="Google API Key (Gemini)", type="password", on_change=State.set_api_key, **_input_style),
                    rx.select(State.gemini_model_list, value=State.gemini_model_choice, on_change=State.set_gemini_model_choice, width="100%", size="3"),

                    rx.divider(margin_y="3", style={"opacity": "0.35"}),
                    rx.text("🤖 LLM Model Routing", **_section_label),
                    rx.checkbox("Global Model", checked=State.use_global_model, on_change=State.set_use_global_model),
                    rx.cond(
                        State.use_global_model,
                        rx.select(State.installed_models, value=State.global_model_choice, on_change=State.set_global_model_choice, width="100%", size="3"),
                        rx.vstack(
                            rx.checkbox("Custom Specialist Routing", checked=State.use_custom_routing, on_change=State.set_use_custom_routing),
                            rx.cond(
                                State.use_custom_routing,
                                rx.vstack(
                                    rx.text("Planner:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["planner"], on_change=State.set_route_planner, width="100%"),
                                    rx.text("Extractor:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["claim_extractor"], on_change=State.set_route_claim_extractor, width="100%"),
                                    rx.text("Detector:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["contradiction_detector"], on_change=State.set_route_contradiction_detector, width="100%"),
                                    rx.text("Consensus:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["consensus_analyst"], on_change=State.set_route_consensus_analyst, width="100%"),
                                    rx.text("Synthesis:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["synthesis"], on_change=State.set_route_synthesis, width="100%"),
                                    rx.text("Experiment:", size="1", color="var(--gray-11)"),
                                    rx.select(State.installed_models, value=State.model_routing["experiment_planner"], on_change=State.set_route_experiment_planner, width="100%"),
                                    spacing="2",
                                    width="100%",
                                ),
                            ),
                            spacing="2",
                            width="100%",
                        ),
                    ),

                    rx.divider(margin_y="3", style={"opacity": "0.35"}),
                    rx.text("⚙️ LLM Options", **_section_label),
                    rx.text(f"Temperature: {State.llm_temperature}", size="2", color="var(--gray-11)"),
                    rx.slider(default_value=[0.7], min=0.0, max=2.0, step=0.1, on_change=State.set_llm_temperature, width="100%"),
                    rx.select(["2048", "4096", "8192", "16384", "32768", "65536"], value=State.llm_num_ctx, on_change=State.set_llm_num_ctx, width="100%", size="3"),
                    rx.text("Max output tokens (num_predict)", size="2", weight="bold", color="var(--gray-11)"),
                    rx.select(
                        ["1024", "2048", "3072", "4096", "8192"],
                        value=State.llm_num_predict,
                        on_change=State.set_llm_num_predict,
                        width="100%",
                        size="3",
                    ),
                    rx.checkbox("Enable Thinking Mode (/set think)", checked=State.llm_think, on_change=State.set_llm_think),
                    rx.select(
                        ["Display in Expander", "Strip Completely", "Raw Text"],
                        value=State.llm_reasoning_mode,
                        on_change=State.set_llm_reasoning_mode,
                        width="100%",
                        size="3",
                    ),

                    rx.divider(margin_y="3", style={"opacity": "0.35"}),
                    rx.text("💬 Ask the Dataset", **_section_label),
                    rx.select(State.installed_models, value=State.rag_model_choice, on_change=State.set_rag_model_choice, width="100%", size="3"),
                    rx.button("🗑️ Clear Chat", on_click=State.clear_chat_history, **_btn_ghost, width="100%"),
                    rx.scroll_area(
                        rx.vstack(
                            rx.foreach(
                                State.chat_history,
                                lambda msg: rx.box(
                                    rx.text(
                                        msg.role,
                                        weight="bold",
                                        size="1",
                                        color=rx.cond(msg.role == "user", "var(--accent-11)", "var(--green-11)"),
                                        style={"textTransform": "uppercase", "letterSpacing": "0.06em"},
                                    ),
                                    rx.markdown(msg.content),
                                    rx.cond(
                                        msg.sources.length() > 0,
                                        rx.vstack(
                                            rx.text("Sources:", size="1", weight="bold", color="var(--gray-11)"),
                                            rx.foreach(msg.sources, lambda src: rx.text(f"[{src.index}] {src.title}", size="1", color="var(--gray-10)")),
                                            spacing="1",
                                            margin_top="2",
                                        ),
                                    ),
                                    bg=rx.cond(msg.role == "user", "rgba(99,102,241,0.12)", "rgba(15,23,42,0.7)"),
                                    padding="3",
                                    border_radius="12px",
                                    width="100%",
                                    style={
                                        "border": "1px solid rgba(148,163,184,0.12)",
                                        "animation": f"gxFadeInUp 0.35s {_EASE} both",
                                        "transition": "border-color 0.2s ease",
                                    },
                                ),
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        height="300px",
                        width="100%",
                        style={
                            "background": "rgba(7,10,18,0.5)",
                            "borderRadius": "14px",
                            "border": "1px solid rgba(148,163,184,0.12)",
                            "padding": "10px",
                        },
                    ),
                    rx.hstack(
                        rx.input(
                            placeholder="Ask about this evidence...",
                            value=State.rag_chat_input,
                            on_change=State.set_rag_chat_input,
                            size="3",
                            radius="large",
                            style={"flex": "1", "minHeight": "42px", "fontFamily": _FONT},
                        ),
                        rx.button("Send", on_click=State.run_rag_chat, loading=State.is_chat_running, **_btn_primary),
                        width="100%",
                        spacing="2",
                        align_items="center",
                    ),
                    spacing="3",
                    width="100%",
                    padding_bottom="6",
                ),
                type="hover",
                scrollbars="vertical",
                style={"height": "calc(100vh - 110px)", "width": "100%"},
            ),
            spacing="3",
            width="100%",
            height="100%",
            padding="5",
        ),
        width="340px",
        min_width="340px",
        height="100vh",
        style={
            "background": _SIDEBAR_BG,
            "borderRight": "1px solid rgba(148,163,184,0.14)",
            "fontFamily": _FONT,
            "animation": f"gxSlideInLeft 0.45s {_EASE} both",
            "overflow": "hidden",
        },
    )

def _page_header(title: str, subtitle: str) -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="8", **_heading_display),
        rx.text(subtitle, color="var(--gray-11)", size="3", style={"lineHeight": "1.6"}),
        spacing="2",
        margin_bottom="5",
        width="100%",
        style={"animation": f"gxFadeInUp 0.5s {_EASE} both"},
    )


def _limit_field(label: str, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", weight="medium", color="var(--gray-11)"),
        rx.input(
            type="number",
            default_value="20",
            on_change=on_change,
            size="2",
            radius="large",
            style={"minWidth": "88px", "minHeight": "40px", "fontFamily": _FONT},
        ),
        spacing="1",
        align_items="flex-start",
    )


def tab0_content():
    return rx.vstack(
        _page_header("Scientific Query Planner", "Build research datasets and execute autonomous scientific agents."),
        rx.text_area(
            placeholder="e.g. Does metformin reduce breast cancer recurrence in diabetic patients?",
            on_change=State.set_query,
            width="100%",
            height="120px",
            size="3",
            radius="large",
            style={"fontFamily": _FONT, "lineHeight": "1.6", "padding": "14px"},
        ),
        rx.text("📥 Max Papers to Fetch per Source", weight="bold", size="3", style={"fontFamily": _FONT_DISPLAY}, margin_top="4"),
        rx.hstack(
            _limit_field("PubMed", State.set_limit_pubmed),
            _limit_field("PMC", State.set_limit_pmc),
            _limit_field("SemanticScholar", State.set_limit_semanticscholar),
            _limit_field("OpenAlex", State.set_limit_openalex),
            _limit_field("ClinicalTrials", State.set_limit_clinicaltrials),
            _limit_field("bioRxiv", State.set_limit_biorxiv),
            _limit_field("ChEMBL", State.set_limit_chembl),
            _limit_field("UniProt", State.set_limit_uniprot),
            _limit_field("PubChem", State.set_limit_pubchem),
            _limit_field("dbSNP", State.set_limit_dbsnp),
            wrap="wrap",
            spacing="4",
            width="100%",
        ),
        rx.text("🔬 Synthesis Components & Agent Targets", weight="bold", size="3", style={"fontFamily": _FONT_DISPLAY}, margin_top="4"),
        rx.hstack(
            rx.checkbox("Override LLM Routing (manually select agents)", checked=State.use_manual_agents, on_change=State.set_use_manual_agents),
            rx.checkbox("Force Fresh Retrieval", checked=State.force_fresh, on_change=State.set_force_fresh),
            spacing="5",
            wrap="wrap",
        ),
        rx.cond(
            State.use_manual_agents,
            rx.box(
                rx.hstack(
                    rx.vstack(
                        rx.checkbox("Claim Extractor", checked=State.sel_claim_extractor, on_change=State.set_sel_claim_extractor),
                        rx.checkbox("Consensus", checked=State.sel_consensus, on_change=State.set_sel_consensus),
                        spacing="2",
                    ),
                    rx.vstack(
                        rx.checkbox("Evidence Ranker", checked=State.sel_evidence, on_change=State.set_sel_evidence),
                        rx.checkbox("Lab Experiment", checked=State.sel_experiment, on_change=State.set_sel_experiment),
                        spacing="2",
                    ),
                    rx.vstack(
                        rx.checkbox("Contradiction", checked=State.sel_contradiction, on_change=State.set_sel_contradiction),
                        rx.checkbox("ELN Assistant", checked=State.sel_eln, on_change=State.set_sel_eln),
                        spacing="2",
                    ),
                    rx.vstack(rx.checkbox("Synthesis", checked=State.sel_synthesis, on_change=State.set_sel_synthesis), spacing="2"),
                    spacing="6",
                    wrap="wrap",
                ),
                padding="4",
                border_radius="14px",
                width="100%",
                style={"background": "rgba(99,102,241,0.08)", "border": "1px solid rgba(129,140,248,0.2)"},
            ),
        ),
        rx.button("Run Planned Query", on_click=State.prepare_query_planner, loading=State.is_running, **_btn_primary, margin_top="3"),
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("🧬 Verify Research Intent & Routing", style={"fontFamily": _FONT_DISPLAY}),
                rx.dialog.description(
                    rx.vstack(
                        rx.text("Does this match what you intended to search? You can refine the query below:", size="2"),
                        rx.input(
                            placeholder="Refinement (e.g. focus on clinical evidence)",
                            on_change=State.set_refinement_instruction,
                            **_input_style,
                        ),
                        rx.hstack(
                            rx.dialog.close(rx.button("Cancel & Edit", on_click=State.close_confirm_dialog, **_btn_ghost)),
                            rx.dialog.close(rx.button("Proceed & Execute", on_click=State.run_query_planner, **_btn_primary)),
                            spacing="3",
                            justify="end",
                            width="100%",
                            margin_top="3",
                        ),
                        spacing="3",
                        width="100%",
                    )
                ),
                style={
                    "background": "linear-gradient(160deg, #111827 0%, #0b1020 100%)",
                    "border": "1px solid rgba(129,140,248,0.25)",
                    "borderRadius": "22px",
                    "boxShadow": "0 24px 80px rgba(0,0,0,0.55)",
                    "padding": "1.5rem",
                    "fontFamily": _FONT,
                },
            ),
            open=State.show_confirm_dialog,
        ),
        rx.cond(
            State.logs.length() > 0,
            rx.card(
                rx.vstack(
                    rx.text("Terminal Output", weight="bold", style={"fontFamily": _FONT_DISPLAY}),
                    rx.scroll_area(
                        rx.foreach(
                            State.logs,
                            lambda log: rx.code(log, display="block", margin_bottom="2px", bg="transparent", style={"fontFamily": _FONT_MONO, "fontSize": "0.82rem"}),
                        ),
                        height="300px",
                        width="100%",
                        style={
                            "background": "rgba(7,10,18,0.65)",
                            "padding": "14px",
                            "borderRadius": "12px",
                            "border": "1px solid rgba(148,163,184,0.12)",
                        },
                    ),
                    spacing="3",
                    width="100%",
                ),
                **_card_style,
                margin_top="5",
            ),
        ),
        rx.cond(
            State.pipeline_trace_visible,
            rx.vstack(
                rx.heading("Routed Answer (Citation Verified)", size="5", style={"fontFamily": _FONT_DISPLAY}),
                rx.card(rx.markdown(State.consensus_report), **_card_style),
                rx.heading("Verification Status", size="5", style={"fontFamily": _FONT_DISPLAY}),
                rx.badge(State.verification_status, size="2", color_scheme="indigo", variant="soft", radius="full"),
                rx.heading("🤖 LLM Routing & Performance Summary", size="5", style={"fontFamily": _FONT_DISPLAY}),
                rx.data_table(
                    data=State.routing_stats,
                    columns=["Stage", "Requested", "Resolved", "Latency", "Status"],
                    width="100%",
                ),
                rx.heading("🧪 Experiment Protocol Draft", size="5", style={"fontFamily": _FONT_DISPLAY}),
                rx.card(rx.markdown(State.experiment_protocol), **_card_style),
                rx.heading("📓 ELN Lab Record Log", size="5", style={"fontFamily": _FONT_DISPLAY}),
                rx.card(rx.markdown(State.eln_entry), **_card_style),
                spacing="4",
                width="100%",
                margin_top="5",
                style={"animation": f"gxFadeInUp 0.45s {_EASE} both"},
            ),
        ),
        spacing="4",
        padding="6",
        width="100%",
        max_width="1080px",
        style={"fontFamily": _FONT},
    )


def tab1_content():
    return rx.vstack(
        _page_header("Scientific Synthesis", "Executive consensus reports and devil's-advocate peer review."),
        rx.hstack(
            rx.button("Load Synthesis Report", on_click=State.load_synthesis, **_btn_ghost),
            rx.button("🔬 Run Scientific Synthesis Agent", on_click=State.run_synthesis_agent, loading=State.is_synthesis_running, **_btn_primary),
            spacing="3",
            wrap="wrap",
            margin_bottom="3",
        ),
        rx.card(rx.markdown(State.synthesis_report), **_card_style),
        rx.divider(margin_y="5", style={"opacity": "0.4"}),
        rx.heading("Devil's Advocate Peer Review", size="6", style={"fontFamily": _FONT_DISPLAY}),
        rx.input(value=State.peer_review_focus, on_change=State.set_peer_review_focus, **_input_style),
        rx.button("Run Peer Review", on_click=State.run_peer_review, loading=State.is_peer_review_running, **_btn_primary),
        rx.cond(
            State.peer_review_critique != "",
            rx.card(rx.markdown(State.peer_review_critique), **_card_style, margin_top="4"),
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1080px",
        style={"fontFamily": _FONT},
    )


def tab2_content():
    return rx.vstack(
        _page_header("Contradictions & Agreements", "Pairwise claim disputes, agreements, and partial alignments."),
        rx.hstack(
            rx.button("Load Contradictions", on_click=State.load_contradictions, **_btn_ghost),
            rx.button("⚡ Run Contradiction & Agreements Agent", on_click=State.run_contradiction_agent, loading=State.is_contradiction_running, **_btn_primary),
            spacing="3",
            wrap="wrap",
            margin_bottom="3",
        ),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Contradictions", value="con", **_tab_trigger),
                rx.tabs.trigger("Agreements", value="agr", **_tab_trigger),
                rx.tabs.trigger("Partial Agreements", value="par", **_tab_trigger),
                style={
                    "gap": "8px",
                    "padding": "6px",
                    "background": "rgba(15,23,42,0.55)",
                    "border": "1px solid rgba(148,163,184,0.14)",
                    "borderRadius": "18px",
                    "marginBottom": "18px",
                },
            ),
            rx.tabs.content(
                rx.data_table(
                    data=State.contradictions_data,
                    columns=["Claim A", "Claim B", "Similarity", "Explanation"],
                    pagination=True,
                    search=True,
                    sort=True,
                    width="100%",
                ),
                value="con",
            ),
            rx.tabs.content(
                rx.data_table(
                    data=State.agreements_data,
                    columns=["Claim A", "Claim B", "Similarity", "Explanation"],
                    pagination=True,
                    search=True,
                    sort=True,
                    width="100%",
                ),
                value="agr",
            ),
            rx.tabs.content(
                rx.data_table(
                    data=State.partial_agreements_data,
                    columns=["Claim A", "Claim B", "Similarity", "Explanation"],
                    pagination=True,
                    search=True,
                    sort=True,
                    width="100%",
                ),
                value="par",
            ),
            default_value="con",
            width="100%",
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1080px",
        style={"fontFamily": _FONT},
    )


def tab3_content():
    return rx.vstack(
        _page_header("GraphRAG Explorer", "Interactive Plotly network of knowledge domains and claim relations."),
        rx.button("Load Knowledge Graph", on_click=State.load_knowledge_graph, loading=State.is_graph_running, **_btn_primary, margin_bottom="3"),
        rx.cond(
            State.graph_figure,
            rx.card(rx.plotly(data=State.graph_figure, height="600px", width="100%"), **_card_style),
            rx.card(
                rx.vstack(
                    rx.icon(tag="network", size=64, color="var(--accent-9)"),
                    rx.text("Click 'Load Knowledge Graph' to visualize.", weight="bold", style={"fontFamily": _FONT_DISPLAY}),
                    align_items="center",
                    justify_content="center",
                    height="400px",
                    spacing="4",
                ),
                **_card_style,
            ),
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1200px",
        style={"fontFamily": _FONT},
    )


def tab4_content():
    return rx.vstack(
        _page_header("Ranked Clinical Evidence", "Oxford Levels of Evidence with methodological bias audit."),
        rx.button("Load Ranked Evidence", on_click=State.load_ranked_evidence, **_btn_primary, margin_bottom="3"),
        rx.hstack(
            rx.text("Filter by Evidence Score (Oxford Level):", size="2", color="var(--gray-11)"),
            rx.slider(default_value=[1], min=1, max=10, on_change=State.set_min_evidence_score, width="300px"),
            rx.badge(State.min_evidence_score, size="2", color_scheme="indigo", variant="soft", radius="full"),
            align_items="center",
            spacing="4",
            margin_bottom="4",
            wrap="wrap",
        ),
        rx.foreach(
            State.filtered_ranked_papers,
            lambda paper: rx.card(
                rx.vstack(
                    rx.text(paper["title"], weight="bold", size="4", style={"fontFamily": _FONT_DISPLAY, "letterSpacing": "-0.02em"}),
                    rx.hstack(
                        rx.badge(f"Score {paper['score']}", color_scheme="indigo", variant="soft", radius="full"),
                        rx.badge(paper["study_design"], color_scheme="gray", variant="outline", radius="full"),
                        rx.badge(f"N={paper['sample_size']}", color_scheme="cyan", variant="soft", radius="full"),
                        spacing="2",
                        wrap="wrap",
                    ),
                    rx.markdown(paper["flags"]),
                    rx.text(paper["abstract"], size="2", color="var(--gray-11)", style={"lineHeight": "1.65"}),
                    spacing="3",
                    width="100%",
                ),
                **_card_style,
                margin_bottom="3",
            ),
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1200px",
        style={"fontFamily": _FONT},
    )


def tab5_content():
    return rx.vstack(
        _page_header("Claim & Stance Exploration", "Filter extracted claims by keyword and stance."),
        rx.button("Load Claims", on_click=State.load_claims, **_btn_primary, margin_bottom="3"),
        rx.hstack(
            rx.input(
                placeholder="Filter claims by keyword...",
                on_change=State.set_claims_search,
                size="3",
                radius="large",
                style={"minWidth": "280px", "minHeight": "42px", "fontFamily": _FONT},
            ),
            rx.checkbox("Support", checked=State.show_support, on_change=State.set_show_support),
            rx.checkbox("Contradict", checked=State.show_contradict, on_change=State.set_show_contradict),
            rx.checkbox("Neutral", checked=State.show_neutral, on_change=State.set_show_neutral),
            align_items="center",
            spacing="4",
            margin_bottom="4",
            wrap="wrap",
        ),
        rx.data_table(
            data=State.filtered_claims,
            columns=["Title", "Claim", "Stance", "Reason"],
            pagination=True,
            search=True,
            sort=True,
            width="100%",
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1200px",
        style={"fontFamily": _FONT},
    )


def tab_eval_content():
    return rx.vstack(
        _page_header("RAG vs GraphRAG Performance", "Compare generation latency, citations, and conflict handling."),
        rx.hstack(
            rx.input(
                placeholder="Enter evaluation query...",
                on_change=State.set_eval_question,
                size="3",
                radius="large",
                style={"minWidth": "320px", "flex": "1", "minHeight": "42px", "fontFamily": _FONT},
            ),
            rx.button("Run Benchmark", on_click=State.run_benchmark, loading=State.eval_running, **_btn_primary),
            align_items="center",
            spacing="3",
            width="100%",
            wrap="wrap",
        ),
        rx.hstack(
            rx.card(
                rx.vstack(
                    rx.heading("Vector RAG", size="5", style={"fontFamily": _FONT_DISPLAY}),
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.std_latency}", weight="bold", size="2")),
                    rx.hstack(
                        rx.icon(tag="file-text", size=18, color="var(--accent-9)"),
                        rx.text(f"Citations: {State.std_citations} | Words: {State.std_words}", weight="bold", size="2"),
                    ),
                    rx.markdown(State.std_ans),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
                padding="5",
                radius="large",
                style={
                    **_card_style["style"],
                    "borderLeft": "4px solid #94a3b8",
                },
            ),
            rx.card(
                rx.vstack(
                    rx.heading("Graph RAG", size="5", style={"fontFamily": _FONT_DISPLAY}),
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.graph_latency}", weight="bold", size="2")),
                    rx.hstack(
                        rx.icon(tag="file-text", size=18, color="var(--accent-9)"),
                        rx.text(f"Citations: {State.graph_citations} | Words: {State.graph_words}", weight="bold", size="2"),
                    ),
                    rx.markdown(State.graph_ans),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
                padding="5",
                radius="large",
                style={
                    **_card_style["style"],
                    "borderLeft": "4px solid #818cf8",
                    "boxShadow": "0 8px 32px rgba(99,102,241,0.22)",
                },
            ),
            spacing="4",
            width="100%",
            margin_top="5",
            align_items="stretch",
        ),
        spacing="3",
        padding="6",
        width="100%",
        max_width="1100px",
        style={"fontFamily": _FONT},
    )


def tab6_content():
    return rx.hstack(
        rx.vstack(
            _page_header("Grounded Overseer", "Synthesize findings into an executive report with Gemini grounding."),
            rx.text_area(
                placeholder="Custom instructions...",
                on_change=State.set_overseer_custom_inst,
                width="100%",
                height="100px",
                size="3",
                radius="large",
                style={"fontFamily": _FONT, "lineHeight": "1.6"},
            ),
            rx.button("Generate Overseer Report", on_click=State.run_overseer, loading=State.is_overseer_running, **_btn_primary, margin_bottom="3"),
            rx.card(rx.markdown(State.overseer_report), **_card_style),
            width="60%",
            spacing="3",
            style={"fontFamily": _FONT},
        ),
        rx.vstack(
            rx.card(
                rx.vstack(
                    rx.heading("🛡️ QA Auditor", size="5", style={"fontFamily": _FONT_DISPLAY}),
                    rx.button("Run Validation Audit", on_click=State.run_qa_audit, loading=State.is_qa_running, **_btn_ghost, width="100%"),
                    rx.cond(
                        State.qa_score >= 0,
                        rx.vstack(
                            rx.text(f"Credibility Score: {State.qa_score}/100", weight="bold", size="4", color="var(--accent-11)"),
                            rx.text(State.qa_feedback, style={"fontStyle": "italic"}, color="var(--gray-11)", size="2"),
                            rx.divider(style={"opacity": "0.4"}),
                            rx.text("Issues Identified:", weight="bold", size="2"),
                            rx.foreach(State.qa_issues, lambda issue: rx.text(f"• {issue}", size="2", color="var(--gray-11)")),
                            spacing="2",
                            width="100%",
                            margin_top="3",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                **_card_style,
            ),
            rx.card(
                rx.vstack(
                    rx.heading("✍️ Iterative Refiner", size="5", style={"fontFamily": _FONT_DISPLAY}),
                    rx.text_area(
                        placeholder="Refinement Instructions...",
                        on_change=State.set_refine_instruction,
                        width="100%",
                        height="90px",
                        size="3",
                        radius="large",
                        style={"fontFamily": _FONT},
                    ),
                    rx.button("Refine Report", on_click=State.run_refinement, loading=State.is_refine_running, **_btn_primary, width="100%"),
                    spacing="3",
                    width="100%",
                ),
                **_card_style,
            ),
            width="40%",
            spacing="4",
            style={"fontFamily": _FONT},
        ),
        width="100%",
        align_items="flex-start",
        spacing="6",
        padding="6",
        max_width="1400px",
    )


def main_content():
    return rx.box(
        rx.vstack(
            # Top brand strip
            rx.hstack(
                rx.badge(
                    "Multi-Agent Scientific Workbench",
                    size="2",
                    variant="soft",
                    color_scheme="indigo",
                    radius="full",
                ),
                rx.spacer(),
                rx.text("Griffin Bio", size="2", weight="medium", color="var(--gray-10)", style={"fontFamily": _FONT_DISPLAY}),
                width="100%",
                align_items="center",
                margin_bottom="4",
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("🧭 Planner", value="tab0", **_tab_trigger),
                    rx.tabs.trigger("📝 Synthesis", value="tab1", **_tab_trigger),
                    rx.tabs.trigger("⚡ Contradictions", value="tab2", **_tab_trigger),
                    rx.tabs.trigger("📚 Evidence", value="tab4", **_tab_trigger),
                    rx.tabs.trigger("🔎 Claims", value="tab5", **_tab_trigger),
                    rx.tabs.trigger("🤖 Benchmark", value="eval", **_tab_trigger),
                    rx.tabs.trigger("🧐 Overseer", value="tab6", **_tab_trigger),
                    rx.tabs.trigger("🕸️ GraphRAG", value="tab3", **_tab_trigger),
                    wrap="wrap",
                    style={
                        "gap": "8px",
                        "padding": "8px",
                        "background": "rgba(15,23,42,0.55)",
                        "border": "1px solid rgba(148,163,184,0.14)",
                        "borderRadius": "22px",
                        "backdropFilter": "blur(12px)",
                        "marginBottom": "8px",
                    },
                ),
                rx.tabs.content(tab0_content(), value="tab0"),
                rx.tabs.content(tab1_content(), value="tab1"),
                rx.tabs.content(tab2_content(), value="tab2"),
                rx.tabs.content(tab3_content(), value="tab3"),
                rx.tabs.content(tab4_content(), value="tab4"),
                rx.tabs.content(tab5_content(), value="tab5"),
                rx.tabs.content(tab_eval_content(), value="eval"),
                rx.tabs.content(tab6_content(), value="tab6"),
                default_value="tab0",
                width="100%",
            ),
            spacing="3",
            width="100%",
            align_items="flex-start",
        ),
        width="100%",
        height="100vh",
        overflow_y="auto",
        padding="6",
        style={
            "background": _PAGE_BG,
            "fontFamily": _FONT,
            "animation": f"gxFadeIn 0.55s {_EASE} both",
        },
    )


def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        main_content(),
        width="100vw",
        height="100vh",
        spacing="0",
        style={
            "background": "#070a12",
            "fontFamily": _FONT,
            "overflow": "hidden",
        },
    )


# Global CSS injected into the Reflex head for fonts + keyframes
_GLOBAL_STYLESHEETS = [
    "https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap",
]

_GLOBAL_STYLE = {
    "font_family": _FONT,
    "::selection": {
        "background": "rgba(129,140,248,0.35)",
        "color": "#fff",
    },
}

app = rx.App(
    stylesheets=_GLOBAL_STYLESHEETS,
    style=_GLOBAL_STYLE,
    head_components=[
        rx.el.style(
            """
            @keyframes gxFadeInUp {
                from { opacity: 0; transform: translateY(14px); }
                to   { opacity: 1; transform: translateY(0); }
            }
            @keyframes gxFadeIn {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
            @keyframes gxSlideInLeft {
                from { opacity: 0; transform: translateX(-12px); }
                to   { opacity: 1; transform: translateX(0); }
            }
            * { scrollbar-width: thin; scrollbar-color: rgba(100,116,139,0.45) transparent; }
            ::-webkit-scrollbar { width: 10px; height: 10px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb {
                background: rgba(100,116,139,0.45);
                border-radius: 999px;
                border: 2px solid transparent;
                background-clip: padding-box;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(129,140,248,0.55);
                background-clip: padding-box;
                border: 2px solid transparent;
            }
            button:hover { filter: brightness(1.06); transform: translateY(-1px); }
            button:active { transform: translateY(0) scale(0.98); }
            @media (prefers-reduced-motion: reduce) {
                *, *::before, *::after {
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }
            }
            """
        )
    ],
)
app.add_page(index, title="Griffin Bio Reflex", on_load=State.on_load)
app.add_page(onboarding, route="/onboarding", title="Griffin AI - Onboarding")
app.add_page(workspace, route="/workspace", title="Griffin AI - Research Workspace")
app.add_page(dashboard, route="/dashboard", title="Griffin AI - Dashboard")
app.add_page(projects, route="/projects", title="Griffin AI - Labs")
app.add_page(settings, route="/settings", title="Griffin AI - Configuration")
