import reflex as rx

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.knowledge_graph import knowledge_graph_view
from griffin_reflex.components.timeline import research_timeline_view
from griffin_reflex.components.paper_explorer import paper_explorer_view
from griffin_reflex.components.ui import page_shell
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
    return page_shell(
        sidebar(active="/workspace"),
        rx.vstack(
            rx.hstack(
                rx.heading("Scientific Workspace", size="9"),
                rx.spacer(),
                rx.button(
                    "↻ Reload dataset",
                    on_click=WorkspaceState.load_workspace,
                    color_scheme="indigo",
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "Live view of papers, claim graph, and timeline from dataset/ artifacts.",
                color="gray",
            ),
            knowledge_graph_view(WorkspaceState.kg_nodes, WorkspaceState.kg_edges),
            research_timeline_view(WorkspaceState.timeline),
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
