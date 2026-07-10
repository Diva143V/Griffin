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
    ranked_df, contradictions = graph_rag.load_data()
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
    import ollama
    messages = [{"role": "user", "content": prompt}]
    res = ollama.chat(model=model, messages=messages, options=options)
    return res['message']['content']

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
        env["GRIFFIN_ROUTING"] = json.dumps(self.get_actual_model_routing)
        env["GRIFFIN_LLM_OPTS"] = json.dumps({"temperature": self.llm_temperature, "num_ctx": int(self.llm_num_ctx), "think": self.llm_think})
        
        cmd = [sys.executable, cli_path, self.query, self.email, self.api_key, self.sc_api_key]
        
        try:
            subprocess.run(cmd, cwd=root_dir, check=True, env=env)
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


def sidebar():
    return rx.vstack(
        rx.heading("Griffin Bio Controls", size="6", color="var(--accent-9)"),
        rx.divider(),
        rx.scroll_area(
            rx.vstack(
                rx.text("🔑 Credentials & Settings", weight="bold"),
                rx.input(placeholder="PubMed Email", default_value="test@example.com", on_change=State.set_email, width="100%"),
                rx.input(placeholder="Semantic Scholar Key", type="password", on_change=State.set_sc_api_key, width="100%"),
                rx.input(placeholder="Google API Key (Gemini)", type="password", on_change=State.set_api_key, width="100%"),
                rx.select(State.gemini_model_list, value=State.gemini_model_choice, on_change=State.set_gemini_model_choice, width="100%"),
                
                rx.divider(),
                rx.text("🤖 LLM Model Routing", weight="bold"),
                rx.checkbox("Global Model", checked=State.use_global_model, on_change=State.set_use_global_model),
                rx.cond(State.use_global_model,
                    rx.select(State.installed_models, value=State.global_model_choice, on_change=State.set_global_model_choice, width="100%"),
                    rx.vstack(
                        rx.checkbox("Custom Specialist Routing", checked=State.use_custom_routing, on_change=State.set_use_custom_routing),
                        rx.cond(State.use_custom_routing,
                            rx.vstack(
                                rx.text("Planner:", size="1"), rx.select(State.installed_models, value=State.model_routing["planner"], on_change=State.set_route_planner),
                                rx.text("Extractor:", size="1"), rx.select(State.installed_models, value=State.model_routing["claim_extractor"], on_change=State.set_route_claim_extractor),
                                rx.text("Detector:", size="1"), rx.select(State.installed_models, value=State.model_routing["contradiction_detector"], on_change=State.set_route_contradiction_detector),
                                rx.text("Consensus:", size="1"), rx.select(State.installed_models, value=State.model_routing["consensus_analyst"], on_change=State.set_route_consensus_analyst),
                                rx.text("Synthesis:", size="1"), rx.select(State.installed_models, value=State.model_routing["synthesis"], on_change=State.set_route_synthesis),
                                rx.text("Experiment:", size="1"), rx.select(State.installed_models, value=State.model_routing["experiment_planner"], on_change=State.set_route_experiment_planner),
                            )
                        )
                    )
                ),
                
                rx.divider(),
                rx.text("⚙️ LLM Options", weight="bold"),
                rx.text(f"Temperature: {State.llm_temperature}"),
                rx.slider(default_value=[0.7], min=0.0, max=2.0, step=0.1, on_change=State.set_llm_temperature),
                rx.select(["2048", "4096", "8192", "16384", "32768", "65536"], value=State.llm_num_ctx, on_change=State.set_llm_num_ctx),
                rx.checkbox("Enable Thinking Mode", checked=State.llm_think, on_change=State.set_llm_think),
                rx.select(["Display in Expander", "Strip Completely", "Raw Text"], value=State.llm_reasoning_mode, on_change=State.set_llm_reasoning_mode),
                
                rx.divider(),
                rx.text("💬 Ask the Dataset (RAG Chat)", weight="bold"),
                rx.select(State.installed_models, value=State.rag_model_choice, on_change=State.set_rag_model_choice),
                rx.button("🗑️ Clear", on_click=State.clear_chat_history, size="1"),
                rx.scroll_area(
                    rx.vstack(
                        rx.foreach(State.chat_history, lambda msg: 
                            rx.box(
                                rx.text(msg.role, weight="bold", size="1"),
                                rx.markdown(msg.content),
                                rx.cond(msg.sources.length() > 0,
                                    rx.vstack(
                                        rx.text("Sources:", size="1", weight="bold"),
                                        rx.foreach(msg.sources, lambda src: rx.text(f"[{src.index}] {src.title}", size="1"))
                                    )
                                ),
                                bg=rx.cond(msg.role == "user", "var(--gray-3)", "var(--accent-3)"),
                                padding="2", border_radius="md", width="100%"
                            )
                        )
                    ), height="300px", width="100%", bg="var(--gray-2)"
                ),
                rx.hstack(
                    rx.input(placeholder="Ask...", value=State.rag_chat_input, on_change=State.set_rag_chat_input),
                    rx.button("Send", on_click=State.run_rag_chat, loading=State.is_chat_running)
                ),
            ),
            padding="4", width="300px", height="100vh", bg="var(--gray-2)", border_right="1px solid var(--gray-5)"
        )
    )

def tab0_content():
    return rx.vstack(
        rx.heading("Scientific Query Planner", size="8"),
        rx.text("Build research datasets and execute autonomous scientific agents.", color="var(--gray-11)"),
        
        rx.text_area(placeholder="Enter scientific query...", on_change=State.set_query, width="100%", height="100px"),
        
        rx.text("📥 Max Papers to Fetch per Source:", weight="bold"),
        rx.hstack(
            rx.vstack(rx.text("PubMed"), rx.input(type="number", default_value="20", on_change=State.set_limit_pubmed)),
            rx.vstack(rx.text("PMC"), rx.input(type="number", default_value="20", on_change=State.set_limit_pmc)),
            rx.vstack(rx.text("SemanticScholar"), rx.input(type="number", default_value="20", on_change=State.set_limit_semanticscholar)),
            rx.vstack(rx.text("OpenAlex"), rx.input(type="number", default_value="20", on_change=State.set_limit_openalex)),
            rx.vstack(rx.text("ClinicalTrials"), rx.input(type="number", default_value="20", on_change=State.set_limit_clinicaltrials)),
            rx.vstack(rx.text("bioRxiv"), rx.input(type="number", default_value="20", on_change=State.set_limit_biorxiv)),
            rx.vstack(rx.text("ChEMBL"), rx.input(type="number", default_value="20", on_change=State.set_limit_chembl)),
            rx.vstack(rx.text("UniProt"), rx.input(type="number", default_value="20", on_change=State.set_limit_uniprot)),
            rx.vstack(rx.text("PubChem"), rx.input(type="number", default_value="20", on_change=State.set_limit_pubchem)),
            rx.vstack(rx.text("dbSNP"), rx.input(type="number", default_value="20", on_change=State.set_limit_dbsnp)),
            wrap="wrap",
            spacing="4"
        ),
        
        rx.text("🔬 Select Synthesis Components & Agent Targets:", weight="bold"),
        rx.hstack(
            rx.checkbox("Override LLM Routing (manually select agents)", checked=State.use_manual_agents, on_change=State.set_use_manual_agents),
            rx.checkbox("Force Fresh Retrieval", checked=State.force_fresh, on_change=State.set_force_fresh)
        ),
        rx.cond(State.use_manual_agents,
            rx.hstack(
                rx.vstack(rx.checkbox("Claim Extractor", checked=State.sel_claim_extractor, on_change=State.set_sel_claim_extractor), rx.checkbox("Consensus", checked=State.sel_consensus, on_change=State.set_sel_consensus)),
                rx.vstack(rx.checkbox("Evidence Ranker", checked=State.sel_evidence, on_change=State.set_sel_evidence), rx.checkbox("Lab Experiment", checked=State.sel_experiment, on_change=State.set_sel_experiment)),
                rx.vstack(rx.checkbox("Contradiction", checked=State.sel_contradiction, on_change=State.set_sel_contradiction), rx.checkbox("ELN Assistant", checked=State.sel_eln, on_change=State.set_sel_eln)),
                rx.vstack(rx.checkbox("Synthesis", checked=State.sel_synthesis, on_change=State.set_sel_synthesis))
            )
        ),
        
        rx.button("Run Planned Query", on_click=State.prepare_query_planner, loading=State.is_running, size="3", type="submit"),
        
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("🧬 Verify Research Intent & Routing"),
                rx.dialog.description(
                    rx.vstack(
                        rx.text("Does this match what you intended to search? You can refine the query below:"),
                        rx.input(placeholder="Refinement (e.g. focus on clinical evidence)", on_change=State.set_refinement_instruction),
                        rx.hstack(
                            rx.dialog.close(rx.button("Cancel & Edit", on_click=State.close_confirm_dialog)),
                            rx.dialog.close(rx.button("Proceed & Execute", on_click=State.run_query_planner)),
                        )
                    )
                )
            ),
            open=State.show_confirm_dialog,
        ),
        
        rx.cond(State.logs.length() > 0,
            rx.card(
                rx.vstack(
                    rx.text("Terminal Output", weight="bold"),
                    rx.scroll_area(rx.foreach(State.logs, lambda log: rx.code(log, display="block", margin_bottom="2px", bg="transparent")), height="300px", width="100%", bg="var(--gray-2)", padding="3", border_radius="md")
                ), width="100%", margin_top="6"
            )
        ),
        
        rx.cond(State.pipeline_trace_visible,
            rx.vstack(
                rx.heading("Routed Answer (Citation Verified)", size="4"),
                rx.markdown(State.consensus_report),
                
                rx.heading("Verification Status", size="4"),
                rx.text(State.verification_status, weight="bold"),
                
                rx.heading("🤖 LLM Routing & Performance Summary", size="4"),
                rx.data_table(data=State.routing_stats, columns=["Stage", "Requested", "Resolved", "Latency", "Status"], width="100%"),
                
                rx.heading("🧪 Experiment Protocol Draft", size="4"),
                rx.markdown(State.experiment_protocol),
                
                rx.heading("📓 ELN Lab Record Log", size="4"),
                rx.markdown(State.eln_entry)
            )
        ),
        
        padding="8", width="100%", max_width="1000px"
    )

def tab1_content():
    return rx.vstack(
        rx.heading("Scientific Synthesis", size="8"),
        rx.hstack(
            rx.button("Load Synthesis Report", on_click=State.load_synthesis, margin_bottom="4"),
            rx.button("🔬 Run Scientific Synthesis Agent", on_click=State.run_synthesis_agent, loading=State.is_synthesis_running)
        ),
        rx.card(rx.markdown(State.synthesis_report), width="100%", padding="5"),
        rx.divider(margin_y="6"),
        rx.heading("Devil's Advocate Peer Review", size="6"),
        rx.input(value=State.peer_review_focus, on_change=State.set_peer_review_focus, width="100%"),
        rx.button("Run Peer Review", on_click=State.run_peer_review, loading=State.is_peer_review_running),
        rx.cond(State.peer_review_critique != "", rx.card(rx.markdown(State.peer_review_critique), width="100%", bg="var(--gray-3)", margin_top="4")), 
        padding="8", width="100%", max_width="1000px"
    )

def tab2_content():
    return rx.vstack(
        rx.heading("Contradictions", size="8"),
        rx.hstack(
            rx.button("Load Contradictions", on_click=State.load_contradictions, margin_bottom="4"),
            rx.button("⚡ Run Contradiction & Agreements Agent", on_click=State.run_contradiction_agent, loading=State.is_contradiction_running)
        ),
        
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Contradictions", value="con"),
                rx.tabs.trigger("Agreements", value="agr"),
                rx.tabs.trigger("Partial Agreements", value="par"),
            ),
            rx.tabs.content(
                rx.data_table(data=State.contradictions_data, columns=["Claim A", "Claim B", "Similarity", "Explanation"], pagination=True, search=True, sort=True, width="100%"), 
                value="con"
            ),
            rx.tabs.content(
                rx.data_table(data=State.agreements_data, columns=["Claim A", "Claim B", "Similarity", "Explanation"], pagination=True, search=True, sort=True, width="100%"), 
                value="agr"
            ),
            rx.tabs.content(
                rx.data_table(data=State.partial_agreements_data, columns=["Claim A", "Claim B", "Similarity", "Explanation"], pagination=True, search=True, sort=True, width="100%"), 
                value="par"
            ),
            default_value="con", width="100%"
        ),
        padding="8", width="100%", max_width="1000px"
    )

def tab3_content():
    return rx.vstack(
        rx.heading("GraphRAG Explorer", size="8"),
        rx.text("Interactive Plotly Network Graph visualization of knowledge domains.", color="var(--gray-11)"),
        rx.button("Load Knowledge Graph", on_click=State.load_knowledge_graph, loading=State.is_graph_running, margin_bottom="4"),
        rx.cond(
            State.graph_figure,
            rx.card(rx.plotly(data=State.graph_figure, height="600px", width="100%"), width="100%", bg="var(--gray-2)", margin_top="4"),
            rx.card(rx.vstack(rx.icon(tag="network", size=64, color="var(--accent-9)"), rx.text("Click 'Load Knowledge Graph' to visualize.", weight="bold"), align_items="center", justify_content="center", height="400px"), width="100%", bg="var(--gray-2)", margin_top="4")
        ), padding="8", width="100%", max_width="1200px"
    )

def tab4_content():
    return rx.vstack(
        rx.heading("Ranked Clinical Evidence", size="8"),
        rx.button("Load Ranked Evidence", on_click=State.load_ranked_evidence, margin_bottom="4"),
        rx.hstack(
            rx.text("Filter by Evidence Score (Oxford Level):"),
            rx.slider(default_value=[1], min=1, max=10, on_change=State.set_min_evidence_score, width="300px"),
            rx.text(State.min_evidence_score), align_items="center", spacing="4", margin_bottom="4"
        ),
        rx.foreach(State.filtered_ranked_papers, lambda paper:
            rx.card(
                rx.vstack(
                    rx.text(paper["title"], weight="bold", size="4"),
                    rx.text(f"Score: {paper['score']} | Design: {paper['study_design']} | N: {paper['sample_size']}"),
                    rx.markdown(paper["flags"]),
                    rx.text(paper["abstract"], size="2")
                ), margin_bottom="4", width="100%"
            )
        ), padding="8", width="100%", max_width="1200px"
    )

def tab5_content():
    return rx.vstack(
        rx.heading("Claim & Stance Exploration", size="8"),
        rx.button("Load Claims", on_click=State.load_claims, margin_bottom="4"),
        rx.hstack(
            rx.input(placeholder="Filter claims by keyword...", on_change=State.set_claims_search, width="300px"),
            rx.checkbox("Support", checked=State.show_support, on_change=State.set_show_support),
            rx.checkbox("Contradict", checked=State.show_contradict, on_change=State.set_show_contradict),
            rx.checkbox("Neutral", checked=State.show_neutral, on_change=State.set_show_neutral),
            align_items="center", spacing="4", margin_bottom="4"
        ),
        rx.data_table(data=State.filtered_claims, columns=["Title", "Claim", "Stance", "Reason"], pagination=True, search=True, sort=True, width="100%"), 
        padding="8", width="100%", max_width="1200px"
    )

def tab_eval_content():
    return rx.vstack(
        rx.heading("RAG vs GraphRAG Performance", size="8"),
        rx.text("Compare generation latency and accuracy across models.", color="var(--gray-11)", margin_bottom="4"),
        rx.hstack(rx.input(placeholder="Enter evaluation query...", on_change=State.set_eval_question, width="400px"), rx.button("Run Benchmark", on_click=State.run_benchmark, loading=State.eval_running), align_items="center", spacing="4"),
        rx.hstack(
            rx.card(
                rx.vstack(
                    rx.heading("Vector RAG", size="5"), 
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.std_latency}", weight="bold")),
                    rx.hstack(rx.icon(tag="file-text", size=18, color="var(--accent-9)"), rx.text(f"Citations: {State.std_citations} | Words: {State.std_words}", weight="bold")),
                    rx.markdown(State.std_ans),
                ), width="100%", bg="var(--gray-2)", padding="4"
            ),
            rx.card(
                rx.vstack(
                    rx.heading("Graph RAG", size="5"), 
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.graph_latency}", weight="bold")),
                    rx.hstack(rx.icon(tag="file-text", size=18, color="var(--accent-9)"), rx.text(f"Citations: {State.graph_citations} | Words: {State.graph_words}", weight="bold")),
                    rx.markdown(State.graph_ans),
                ), width="100%", bg="var(--gray-2)", padding="4"
            ), spacing="4", width="100%", margin_top="6"
        ), padding="8", width="100%", max_width="1000px"
    )

def tab6_content():
    return rx.hstack(
        rx.vstack(
            rx.heading("Grounded Overseer Command Center", size="8"),
            rx.text_area(placeholder="Custom instructions...", on_change=State.set_overseer_custom_inst, width="100%"),
            rx.button("Generate Overseer Report", on_click=State.run_overseer, loading=State.is_overseer_running, margin_bottom="4"),
            rx.card(rx.markdown(State.overseer_report), width="100%", padding="5", bg="var(--gray-2)"),
            width="60%"
        ),
        rx.vstack(
            rx.card(
                rx.vstack(
                    rx.heading("🛡️ QA Auditor", size="5"),
                    rx.button("Run Validation Audit", on_click=State.run_qa_audit, loading=State.is_qa_running),
                    rx.cond(State.qa_score >= 0, rx.vstack(rx.text(f"Credibility Score: {State.qa_score}/100", weight="bold"), rx.text(State.qa_feedback, style={"fontStyle": "italic"}), rx.divider(), rx.text("Issues Identified:", weight="bold"), rx.foreach(State.qa_issues, lambda issue: rx.text(f"• {issue}"))))
                ), width="100%", padding="4", bg="var(--gray-3)"
            ),
            rx.card(
                rx.vstack(
                    rx.heading("✍️ Iterative Refiner", size="5"),
                    rx.text_area(placeholder="Refinement Instructions...", on_change=State.set_refine_instruction, width="100%"),
                    rx.button("Refine Report", on_click=State.run_refinement, loading=State.is_refine_running)
                ), width="100%", padding="4", bg="var(--gray-3)"
            ), width="40%", spacing="4"
        ), width="100%", align_items="flex-start", spacing="6", padding="8", max_width="1400px"
    )

def main_content():
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("🧭 Planner", value="tab0"), rx.tabs.trigger("📝 Synthesis", value="tab1"),
            rx.tabs.trigger("⚡ Contradictions", value="tab2"), rx.tabs.trigger("📚 Evidence", value="tab4"),
            rx.tabs.trigger("🔎 Claims", value="tab5"), rx.tabs.trigger("🤖 Benchmark", value="eval"),
            rx.tabs.trigger("🧐 Overseer", value="tab6"), rx.tabs.trigger("🕸️ GraphRAG", value="tab3"),
            wrap="wrap"
        ),
        rx.tabs.content(tab0_content(), value="tab0"), rx.tabs.content(tab1_content(), value="tab1"),
        rx.tabs.content(tab2_content(), value="tab2"), rx.tabs.content(tab3_content(), value="tab3"),
        rx.tabs.content(tab4_content(), value="tab4"), rx.tabs.content(tab5_content(), value="tab5"),
        rx.tabs.content(tab_eval_content(), value="eval"), rx.tabs.content(tab6_content(), value="tab6"),
        default_value="tab0", margin_top="4", width="100%"
    )

def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(main_content(), width="100%", overflow_y="auto"),
        width="100vw", height="100vh", spacing="0", bg="var(--gray-1)"
    )

app = rx.App()
app.add_page(index, title="Griffin Bio Reflex", on_load=State.on_load)
