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


def knowledge_graph(nodes: list | None = None, edges: list | None = None):
    """Static helper kept for simple mocks; prefer knowledge_graph_view with state."""
    nodes = nodes or []
    edges = edges or []
    if not nodes:
        return rx.vstack(
            rx.heading("Knowledge Graph Explorer", size="7"),
            rx.text(
                "No graph data yet. Run the Planner (and contradiction stage) to populate dataset/contradictions.json.",
                color="gray",
            ),
            width="100%",
            spacing="4",
        )
    return rx.vstack(
        rx.heading("Knowledge Graph Explorer", size="7"),
        rx.text(
            "Claim relationships from contradiction detection (live dataset).",
            color="gray",
        ),
        rx.grid(
            *[node_card(n) for n in nodes[:12]],
            columns="3",
            spacing="4",
            width="100%",
        ),
        rx.divider(),
        rx.vstack(
            rx.heading("Relationships", size="5"),
            *[
                rx.text(f"{e['source']} → {e['target']}  ({e['label']})", size="2")
                for e in edges[:20]
            ],
            spacing="2",
            width="100%",
        ),
        width="100%",
        spacing="6",
    )


def knowledge_graph_view(nodes_var, edges_var):
    """Reflex-state-driven knowledge graph (nodes/edges as list[dict])."""
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
