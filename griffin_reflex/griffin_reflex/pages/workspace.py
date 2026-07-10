import reflex as rx

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.knowledge_graph import knowledge_graph
from griffin_reflex.components.timeline import research_timeline
from griffin_reflex.components.paper_explorer import paper_explorer

def workspace():
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.vstack(
                rx.heading(
                    "Scientific Workspace",
                    size="9"
                ),
                knowledge_graph(),
                research_timeline(),
                paper_explorer(),
                spacing="8",
                width="100%"
            ),
            padding="40px",
            width="100%",
            height="100vh",
            overflow="auto"
        ),
        width="100%",
        background="""
        radial-gradient(
        ellipse at top,
        #111827,
        #020617
        )
        """
    )
