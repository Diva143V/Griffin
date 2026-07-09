import sys
import os
import asyncio
import json
import reflex as rx
import plotly.graph_objects as go
import networkx as nx

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

class State(rx.State):
    """The app state."""
    query: str = ""
    api_key: str = ""
    email: str = "test@example.com"
    logs: list[str] = []
    is_running: bool = False
    
    # Phase 3/4 State
    synthesis_report: str = "Click 'Load Synthesis' to view."
    peer_review_critique: str = ""
    is_peer_review_running: bool = False
    contradictions_data: list[list[str]] = []
    
    overseer_report: str = "Click 'Generate Report' to run the Grounded Overseer."
    is_overseer_running: bool = False
    
    # Phase 5/6 State
    ranked_papers_data: list[list[str]] = []
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
    graph_latency: str = "--"
    graph_citations: str = "--"

    qa_score: int = -1
    qa_feedback: str = ""
    qa_issues: list[str] = []
    is_qa_running: bool = False
    
    refine_instruction: str = ""
    is_refine_running: bool = False
    
    # Phase 7 State
    is_graph_running: bool = False
    graph_figure: rx.Field[go.Figure] = None
    
    def set_query(self, val: str): self.query = val
    def set_api_key(self, val: str): self.api_key = val
    def set_email(self, val: str): self.email = val
    def set_min_evidence_score(self, val: list[int]): self.min_evidence_score = val[0]
    def set_claims_search(self, val: str): self.claims_search = val
    def set_show_support(self, val: bool): self.show_support = val
    def set_show_contradict(self, val: bool): self.show_contradict = val
    def set_show_neutral(self, val: bool): self.show_neutral = val
    def set_eval_question(self, val: str): self.eval_question = val
    def set_refine_instruction(self, val: str): self.refine_instruction = val

    @rx.var
    def filtered_ranked_papers(self) -> list[list[str]]:
        try:
            return [row for row in self.ranked_papers_data if float(row[1]) >= float(self.min_evidence_score)]
        except:
            return self.ranked_papers_data

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

    async def run_query_planner(self):
        if not self.query:
            self.logs = ["Error: Please enter a query first."]
            return
        self.is_running = True
        self.logs = [f"Starting Query Planner for: {self.query}", "Initializing Agents..."]
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_backend_pipeline)
        log_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "terminal.log"))
        last_pos = 0
        while not task.done():
            if os.path.exists(log_file_path):
                with open(log_file_path, "r", encoding="utf-8") as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()
                    if new_lines:
                        for line in new_lines:
                            self.logs.append(line.strip())
                        yield
            await asyncio.sleep(0.5)
        self.is_running = False
        self.logs.append("Execution Complete!")
        yield
        
    def execute_backend_pipeline(self):
        import subprocess
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cli_path = os.path.join(root_dir, "run_pipeline_cli.py")
        try:
            subprocess.run([sys.executable, cli_path, self.query, self.email, self.api_key], cwd=root_dir, check=True)
        except Exception as e:
            with open(os.path.join(root_dir, "dataset", "terminal.log"), "a", encoding="utf-8") as f:
                f.write(f"\nPipeline Error: {str(e)}\n")

    def load_synthesis(self):
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(root_dir, "dataset", "synthesis_report.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.synthesis_report = f.read()
        else:
            self.synthesis_report = "Report not found. Did you run the pipeline yet?"

    async def run_peer_review(self):
        self.is_peer_review_running = True
        self.peer_review_critique = "Running Devil's Advocate Peer Review..."
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_peer_review)
        await task
        self.is_peer_review_running = False
        yield
        
    def execute_peer_review(self):
        try:
            from src.agents.peer_review_agent import run_peer_review
            self.peer_review_critique = run_peer_review(self.api_key, self.synthesis_report, "General Scientific Rigor", "gemini-2.5-flash")
        except Exception as e:
            self.peer_review_critique = f"Error: {e}"

    def load_contradictions(self):
        import json
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(root_dir, "dataset", "contradictions.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                rows = []
                for c in data.get("contradictions", []):
                    rows.append([c.get("claim_a_title", "")[:30], c.get("claim_b_title", "")[:30], str(c.get("cosine_similarity", 0)), c.get("explanation", "")[:100]])
                self.contradictions_data = rows

    async def run_overseer(self):
        self.is_overseer_running = True
        self.overseer_report = "Generating full Grounded Overseer report..."
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_overseer)
        await task
        self.is_overseer_running = False
        yield
        
    def execute_overseer(self):
        try:
            from src.agents.report_agent import generate_overseer_report
            import pandas as pd
            import json
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            ranked_path = os.path.join(root_dir, "dataset", "clean_papers_with_embeddings.csv")
            con_path = os.path.join(root_dir, "dataset", "contradictions.json")
            ranked_df = pd.read_csv(ranked_path) if os.path.exists(ranked_path) else pd.DataFrame()
            try:
                with open(con_path, "r", encoding="utf-8") as f:
                    contradictions = json.load(f)
            except:
                contradictions = {}
            self.overseer_report = generate_overseer_report(self.api_key, self.synthesis_report, ranked_df, contradictions, "gemini-2.5-flash")
        except Exception as e:
            self.overseer_report = f"Error: {e}"

    def load_ranked_evidence(self):
        import pandas as pd
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(root_dir, "dataset", "clean_papers_with_embeddings.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                cols = ["title", "evidence_score", "study_design", "sample_size", "source", "year"]
                rows = []
                for _, row in df.iterrows():
                    r = []
                    for c in cols:
                        r.append(str(row.get(c, "")))
                    rows.append(r)
                self.ranked_papers_data = rows
            except Exception as e:
                print(e)
                
    def load_claims(self):
        import pandas as pd
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        path = os.path.join(root_dir, "dataset", "claims_dataset.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                cols = ["title", "claim", "stance", "reason"]
                rows = []
                for _, row in df.iterrows():
                    r = []
                    for c in cols:
                        r.append(str(row.get(c, "")))
                    rows.append(r)
                self.claims_data = rows
            except Exception as e:
                print(e)
                
    async def run_qa_audit(self):
        self.is_qa_running = True
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_qa_audit)
        await task
        self.is_qa_running = False
        yield

    def execute_qa_audit(self):
        try:
            from src.agents.validation_agent import run_qa_audit
            res = run_qa_audit(self.api_key, self.overseer_report, "gemini-2.5-flash")
            self.qa_score = res.get("score", 0)
            self.qa_feedback = res.get("feedback", "")
            self.qa_issues = res.get("issues", [])
        except Exception as e:
            self.qa_feedback = f"Error: {e}"

    async def run_refinement(self):
        self.is_refine_running = True
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_refinement)
        await task
        self.is_refine_running = False
        yield
        
    def execute_refinement(self):
        try:
            from src.agents.refinement_agent import refine_report_section
            self.overseer_report = refine_report_section(self.api_key, self.overseer_report, "General", self.refine_instruction, "gemini-2.5-flash")
        except Exception as e:
            self.overseer_report += f"\n\nError refining: {e}"

    async def run_benchmark(self):
        self.eval_running = True
        self.std_latency = "--"
        self.graph_latency = "--"
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_benchmark)
        await task
        self.eval_running = False
        yield
        
    def execute_benchmark(self):
        import time
        from src.core import graph_rag
        from sentence_transformers import SentenceTransformer
        import pandas as pd
        import json
        
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        ranked_path = os.path.join(root_dir, "dataset", "clean_papers_with_embeddings.csv")
        con_path = os.path.join(root_dir, "dataset", "contradictions.json")
        try:
            ranked_df = pd.read_csv(ranked_path)
            with open(con_path, "r", encoding="utf-8") as f:
                contradictions = json.load(f)
        except:
            ranked_df = pd.DataFrame()
            contradictions = {}
            
        try:
            encoder_model = SentenceTransformer('all-MiniLM-L6-v2')
            eval_k = 3
            model_choice = "gemini-2.5-flash"
    
            # Standard RAG
            t_ret_start = time.time()
            std_context, std_sources = graph_rag.get_standard_rag_context(self.eval_question, encoder_model, ranked_df, eval_k)
            std_ret_time = time.time() - t_ret_start
            std_prompt = f"Answer using: {std_context}"
            std_answer, std_gen_time = graph_rag.generate_answer(std_prompt, model_choice)
            self.std_latency = f"{std_ret_time + std_gen_time:.1f}s"
            self.std_citations = str(len(std_sources))
    
            # Graph RAG
            t_ret_start = time.time()
            graph_context, graph_sources, graph_relations = graph_rag.get_graph_rag_context(self.eval_question, encoder_model, ranked_df, contradictions, eval_k)
            graph_ret_time = time.time() - t_ret_start
            graph_prompt = f"Answer using: {graph_context}"
            graph_answer, graph_gen_time = graph_rag.generate_answer(graph_prompt, model_choice)
            self.graph_latency = f"{graph_ret_time + graph_gen_time:.1f}s"
            self.graph_citations = str(len(graph_sources))
        except Exception as e:
            self.std_latency = f"Error"
            self.graph_latency = f"{e}"

    async def load_knowledge_graph(self):
        self.is_graph_running = True
        yield
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(None, self.execute_graph_build)
        await task
        self.is_graph_running = False
        yield
        
    def execute_graph_build(self):
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            con_path = os.path.join(root_dir, "dataset", "contradictions.json")
            if not os.path.exists(con_path):
                return
                
            with open(con_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            G = nx.Graph()
            
            # Helper to add edge
            def add_edges(items, color):
                for item in items[:50]: # Limit to 50 per category for performance
                    a = item.get("claim_a_title", "Unknown A")[:40] + "..."
                    b = item.get("claim_b_title", "Unknown B")[:40] + "..."
                    G.add_node(a)
                    G.add_node(b)
                    G.add_edge(a, b, color=color)
                    
            add_edges(data.get("agreements", []), "green")
            add_edges(data.get("partial_agreements", []), "orange")
            add_edges(data.get("contradictions", []), "red")
            
            if len(G.nodes) == 0:
                G.add_node("No Data Found")
                
            pos = nx.spring_layout(G, k=0.5, iterations=50)
            
            edge_traces = []
            for edge in G.edges(data=True):
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                color = edge[2].get('color', '#888')
                
                edge_trace = go.Scatter(
                    x=[x0, x1, None], y=[y0, y1, None],
                    line=dict(width=1.5, color=color),
                    hoverinfo='none', mode='lines'
                )
                edge_traces.append(edge_trace)

            node_x = []
            node_y = []
            node_text = []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                node_text.append(str(node))

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text',
                hoverinfo='text',
                text=node_text,
                textposition="bottom center",
                textfont=dict(size=9, color="var(--gray-11)"),
                marker=dict(
                    showscale=False, color='var(--accent-9)',
                    size=12, line_width=2, line_color='white'
                )
            )
            
            fig = go.Figure(data=edge_traces + [node_trace],
                 layout=go.Layout(
                    title='Knowledge Graph Topology (Live)',
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                ))
            
            self.graph_figure = fig
        except Exception as e:
            print("Graph Error:", e)


def sidebar():
    return rx.vstack(
        rx.heading("Griffin Bio", size="6", color="var(--accent-9)"),
        rx.divider(),
        rx.text("Settings", weight="bold", size="2", color="var(--gray-11)"),
        rx.input(placeholder="Google API Key", type="password", on_change=State.set_api_key, width="100%"),
        rx.input(placeholder="Email", on_change=State.set_email, width="100%"),
        padding="4", width="250px", height="100vh", bg="var(--gray-2)", border_right="1px solid var(--gray-5)",
    )

def tab0_content():
    return rx.vstack(
        rx.heading("Scientific Query Planner", size="8"),
        rx.text("Build research datasets and execute autonomous scientific agents.", color="var(--gray-11)"),
        rx.hstack(
            rx.input(placeholder="Enter scientific query...", on_change=State.set_query, width="60%", size="3"),
            rx.button("Run Pipeline", on_click=State.run_query_planner, loading=State.is_running, size="3"),
            width="100%", spacing="4", margin_top="4"
        ),
        rx.cond(State.is_running | (State.logs.length() > 0),
            rx.card(
                rx.vstack(
                    rx.text("Terminal Output", weight="bold"),
                    rx.scroll_area(rx.foreach(State.logs, lambda log: rx.code(log, display="block", margin_bottom="2px", bg="transparent")), height="300px", width="100%", bg="var(--gray-2)", padding="3", border_radius="md")
                ), width="100%", margin_top="6"
            )
        ), padding="8", width="100%", max_width="1000px"
    )

def tab1_content():
    return rx.vstack(
        rx.heading("Scientific Synthesis", size="8"),
        rx.button("Load Synthesis Report", on_click=State.load_synthesis, margin_bottom="4"),
        rx.card(rx.markdown(State.synthesis_report), width="100%", padding="5"),
        rx.divider(margin_y="6"),
        rx.heading("Devil's Advocate Peer Review", size="6"),
        rx.button("Run Peer Review", on_click=State.run_peer_review, loading=State.is_peer_review_running),
        rx.cond(State.peer_review_critique != "", rx.card(rx.markdown(State.peer_review_critique), width="100%", bg="var(--gray-3)", margin_top="4")), 
        padding="8", width="100%", max_width="1000px"
    )

def tab2_content():
    return rx.vstack(
        rx.heading("Contradictions", size="8"),
        rx.button("Load Contradictions", on_click=State.load_contradictions, margin_bottom="4"),
        rx.data_table(data=State.contradictions_data, columns=["Claim A", "Claim B", "Similarity", "Explanation"], pagination=True, search=True, sort=True, width="100%"), 
        padding="8", width="100%", max_width="1000px"
    )

def tab3_content():
    return rx.vstack(
        rx.heading("GraphRAG Explorer", size="8"),
        rx.text("Interactive Plotly Network Graph visualization of knowledge domains.", color="var(--gray-11)"),
        rx.button("Load Knowledge Graph", on_click=State.load_knowledge_graph, loading=State.is_graph_running, margin_bottom="4"),
        rx.cond(
            State.graph_figure,
            rx.card(
                rx.plotly(data=State.graph_figure, height="600px", width="100%"),
                width="100%", bg="var(--gray-2)", margin_top="4"
            ),
            rx.card(
                rx.vstack(
                    rx.icon(tag="network", size=64, color="var(--accent-9)"),
                    rx.text("Click 'Load Knowledge Graph' to visualize the relationships.", weight="bold"),
                    align_items="center", justify_content="center", height="400px"
                ), width="100%", bg="var(--gray-2)", margin_top="4"
            )
        ),
        padding="8", width="100%", max_width="1200px"
    )

def tab4_content():
    return rx.vstack(
        rx.heading("Ranked Clinical Evidence", size="8"),
        rx.button("Load Ranked Evidence", on_click=State.load_ranked_evidence, margin_bottom="4"),
        rx.hstack(
            rx.text("Filter by Evidence Score (Oxford Level):"),
            rx.slider(default_value=[1], min=1, max=10, on_change=State.set_min_evidence_score, width="300px"),
            rx.text(State.min_evidence_score),
            align_items="center", spacing="4", margin_bottom="4"
        ),
        rx.data_table(
            data=State.filtered_ranked_papers,
            columns=["Title", "Score", "Study Design", "Sample Size", "Source", "Year"],
            pagination=True, search=True, sort=True, width="100%"
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
        rx.data_table(
            data=State.filtered_claims,
            columns=["Title", "Claim", "Stance", "Reason"],
            pagination=True, search=True, sort=True, width="100%"
        ), padding="8", width="100%", max_width="1200px"
    )

def tab_eval_content():
    return rx.vstack(
        rx.heading("RAG vs GraphRAG Performance", size="8"),
        rx.text("Compare generation latency and accuracy across models.", color="var(--gray-11)", margin_bottom="4"),
        rx.hstack(
            rx.input(placeholder="Enter evaluation query...", on_change=State.set_eval_question, width="400px"),
            rx.button("Run Benchmark", on_click=State.run_benchmark, loading=State.eval_running),
            align_items="center", spacing="4"
        ),
        rx.hstack(
            rx.card(
                rx.vstack(
                    rx.heading("Vector RAG", size="5"), 
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.std_latency}", weight="bold")),
                    rx.hstack(rx.icon(tag="file-text", size=18, color="var(--accent-9)"), rx.text(f"Citations: {State.std_citations}", weight="bold"))
                ), width="100%", bg="var(--gray-2)", padding="4"
            ),
            rx.card(
                rx.vstack(
                    rx.heading("Graph RAG", size="5"), 
                    rx.hstack(rx.icon(tag="clock", size=18, color="var(--accent-9)"), rx.text(f"Latency: {State.graph_latency}", weight="bold")),
                    rx.hstack(rx.icon(tag="file-text", size=18, color="var(--accent-9)"), rx.text(f"Citations: {State.graph_citations}", weight="bold"))
                ), width="100%", bg="var(--gray-2)", padding="4"
            ),
            spacing="4", width="100%", margin_top="6"
        ), padding="8", width="100%", max_width="1000px"
    )

def tab6_content():
    return rx.hstack(
        rx.vstack(
            rx.heading("Grounded Overseer Command Center", size="8"),
            rx.button("Generate Overseer Report", on_click=State.run_overseer, loading=State.is_overseer_running, margin_bottom="4"),
            rx.card(rx.markdown(State.overseer_report), width="100%", padding="5", bg="var(--gray-2)"),
            width="60%"
        ),
        rx.vstack(
            rx.card(
                rx.vstack(
                    rx.heading("🛡️ QA Auditor", size="5"),
                    rx.button("Run Validation Audit", on_click=State.run_qa_audit, loading=State.is_qa_running),
                    rx.cond(
                        State.qa_score >= 0,
                        rx.vstack(
                            rx.text(f"Credibility Score: {State.qa_score}/100", weight="bold"),
                            rx.text(State.qa_feedback, style={"fontStyle": "italic"}),
                            rx.divider(),
                            rx.text("Issues Identified:", weight="bold"),
                            rx.foreach(State.qa_issues, lambda issue: rx.text(f"• {issue}"))
                        )
                    )
                ), width="100%", padding="4", bg="var(--gray-3)"
            ),
            rx.card(
                rx.vstack(
                    rx.heading("✍️ Iterative Refiner", size="5"),
                    rx.text_area(placeholder="Refinement Instructions...", on_change=State.set_refine_instruction, width="100%"),
                    rx.button("Refine Report", on_click=State.run_refinement, loading=State.is_refine_running)
                ), width="100%", padding="4", bg="var(--gray-3)"
            ),
            width="40%", spacing="4"
        ),
        width="100%", align_items="flex-start", spacing="6", padding="8", max_width="1400px"
    )


def main_content():
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("🧭 Planner", value="tab0"),
            rx.tabs.trigger("📝 Synthesis", value="tab1"),
            rx.tabs.trigger("⚡ Contradictions", value="tab2"),
            rx.tabs.trigger("📚 Evidence", value="tab4"),
            rx.tabs.trigger("🔎 Claims", value="tab5"),
            rx.tabs.trigger("🤖 Benchmark", value="eval"),
            rx.tabs.trigger("🧐 Overseer", value="tab6"),
            rx.tabs.trigger("🕸️ GraphRAG", value="tab3"),
            wrap="wrap"
        ),
        rx.tabs.content(tab0_content(), value="tab0"),
        rx.tabs.content(tab1_content(), value="tab1"),
        rx.tabs.content(tab2_content(), value="tab2"),
        rx.tabs.content(tab3_content(), value="tab3"),
        rx.tabs.content(tab4_content(), value="tab4"),
        rx.tabs.content(tab5_content(), value="tab5"),
        rx.tabs.content(tab_eval_content(), value="eval"),
        rx.tabs.content(tab6_content(), value="tab6"),
        default_value="tab0", margin_top="4", width="100%"
    )

def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(main_content(), width="100%", overflow_y="auto"),
        width="100vw", height="100vh", spacing="0", bg="var(--gray-1)"
    )

app = rx.App()
app.add_page(index, title="Griffin Bio Reflex")
