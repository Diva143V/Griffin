import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.knowledge_graph import knowledge_graph_view
from griffin_reflex.components.timeline import research_timeline_view
from griffin_reflex.components.paper_explorer import paper_explorer_view
from griffin_reflex.components.ui import page_shell, section_header
from griffin_reflex.data_layer import (
    get_papers,
    get_knowledge_graph,
    get_timeline_events,
)

class WorkspaceState(rx.State):
    paper_search: str = ""
    papers: list[dict[str, str]] = []
    kg_nodes: list[dict[str, str]] = []
    kg_edges: list[dict[str, str]] = []
    timeline: list[dict[str, str]] = []

    @rx.event
    def set_paper_search(self, val: str):
        self.paper_search = val

    @rx.event
    def load_workspace(self):
        self.papers = get_papers(limit=24, search=self.paper_search)
        nodes, edges = get_knowledge_graph()
        self.kg_nodes = nodes
        self.kg_edges = edges
        self.timeline = get_timeline_events()

    @rx.event
    def search_papers(self):
        self.papers = get_papers(limit=24, search=self.paper_search)

def workspace():
    """Premium workspace dashboard page layout"""
    return page_shell(
        sidebar(active="/workspace"),
        rx.vstack(
            # Top Section Header with glowing reload action button
            section_header(
                "Scientific Workspace",
                "Live view of claim relationships, chronology milestones, and curated paper lists.",
                action=rx.button(
                    rx.hstack(
                        rx.icon(tag="rotate-cw", size=16),
                        rx.text("Reload Dataset"),
                        spacing="2",
                    ),
                    on_click=WorkspaceState.load_workspace,
                    size="3",
                    style={
                        "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                        "boxShadow": f"0 4px 15px {COLORS['primary_glow']}",
                        "border": "none",
                        "color": "white",
                        "borderRadius": "12px",
                        "padding": "0 22px",
                        "minHeight": "40px",
                        "cursor": "pointer",
                        "transition": "all 0.3s ease",
                        "_hover": {
                            "transform": "translateY(-2px)",
                            "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                        }
                    }
                )
            ),
            
            # Interactive Knowledge Graph Visualizer
            knowledge_graph_view(WorkspaceState.kg_nodes, WorkspaceState.kg_edges),
            
            # Chronological Discovery Timeline Dot-and-Line layout
            research_timeline_view(WorkspaceState.timeline),
            
            # Literature Search & Explorer view
            paper_explorer_view(
                WorkspaceState.papers,
                WorkspaceState.paper_search,
                WorkspaceState.set_paper_search,
                WorkspaceState.search_papers,
            ),
            spacing="8",
            width="100%",
        ),
    )
