import reflex as rx


def node_card(node: dict):
    return rx.box(
        rx.vstack(
            rx.text(node["label"], weight="bold", size="2"),
            rx.badge(node["type"], color_scheme="indigo", variant="soft"),
            spacing="2",
            align_items="flex-start",
        ),
        padding="15px",
        border_radius="15px",
        background="rgba(99,102,241,.15)",
        border="1px solid rgba(255,255,255,.1)",
        width="100%",
    )


def knowledge_graph():
    """Plotly knowledge graph from main State (used by main workbench integrations)."""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        rx.heading("Knowledge Graph Explorer", size="7"),
        rx.text(
            "Explore scientific relationships between claims, papers, and evidence",
            color="gray",
        ),
        rx.cond(
            State.graph_loaded,
            rx.plotly(
                data=State.graph_figure,
                layout={"height": "600px", "width": "100%"},
            ),
            rx.box(
                rx.text(
                    "Knowledge Graph not generated yet. Load it from the GraphRAG tab or run the pipeline.",
                    color="gray",
                ),
                padding="40px",
                border="1px dashed rgba(255,255,255,0.2)",
                border_radius="10px",
                width="100%",
                text_align="center",
            ),
        ),
        width="100%",
        spacing="6",
    )


def knowledge_graph_view(nodes_var, edges_var):
    """State-driven claim graph for Workspace (nodes/edges as list[dict])."""
    return rx.vstack(
        rx.heading("Knowledge Graph Explorer", size="7"),
        rx.text(
            "Claim relationships from contradiction detection (live dataset).",
            color="gray",
        ),
        rx.cond(
            nodes_var.length() == 0,
            rx.box(
                rx.text(
                    "No graph data yet. Run Planner + contradiction analysis to populate dataset/contradictions.json.",
                    color="gray",
                ),
                padding="20px",
                border_radius="15px",
                background="rgba(255,255,255,0.04)",
                width="100%",
            ),
            rx.vstack(
                rx.grid(
                    rx.foreach(nodes_var, node_card),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                rx.divider(),
                rx.heading("Relationships", size="5"),
                rx.foreach(
                    edges_var,
                    lambda e: rx.text(
                        e["source"] + " → " + e["target"] + "  (" + e["label"] + ")",
                        size="2",
                    ),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        width="100%",
        spacing="5",
    )
