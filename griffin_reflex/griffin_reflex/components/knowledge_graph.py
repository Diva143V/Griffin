import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.ui import section_header, premium_card

def node_card(node: dict):
    """Premium node card with hover glows and type-specific badges"""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(node["label"], weight="bold", size="3", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                rx.spacer(),
                rx.box(
                    width="8px",
                    height="8px",
                    border_radius="50%",
                    background=COLORS["accent"],
                    style={"boxShadow": f"0 0 10px {COLORS['accent']}"}
                ),
                width="100%",
                align_items="center",
            ),
            rx.badge(
                node["type"],
                color_scheme="indigo",
                variant="soft",
                size="1",
                style={
                    "background": f"{COLORS['primary']}15",
                    "border": f"1px solid {COLORS['primary']}40",
                    "color": COLORS["primary"],
                    "fontFamily": FONTS["body"],
                    "padding": "2px 8px",
                    "borderRadius": "6px",
                }
            ),
            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        padding="22px",
        border_radius="18px",
        background=f"rgba(99, 102, 241, 0.04)",
        border=f"1px solid {COLORS['border']}",
        width="100%",
        style={
            "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            "backdropFilter": "blur(12px)",
            "_hover": {
                "transform": "translateY(-4px)",
                "borderColor": COLORS["primary"],
                "boxShadow": f"0 12px 30px {COLORS['primary_glow']}",
                "background": "rgba(99, 102, 241, 0.08)",
            }
        }
    )

def knowledge_graph():
    """Premium Plotly knowledge graph from main State"""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        section_header(
            "Knowledge Graph Explorer",
            "Explore claims, literature linkages, and contradictions inside an interactive space.",
        ),
        rx.cond(
            State.graph_loaded,
            premium_card(
                rx.plotly(
                    data=State.graph_figure,
                    layout={"height": "600px", "width": "100%"},
                ),
                variant="glass"
            ),
            premium_card(
                rx.vstack(
                    rx.text(
                        "Knowledge graph not populated yet. Load it from the GraphRAG tab or execute planner runs first.",
                        color=COLORS["text_secondary"],
                        font_family=FONTS["body"],
                        size="3",
                        text_align="center",
                    ),
                    rx.button(
                        rx.hstack(
                            rx.icon(tag="git-fork", size=16),
                            rx.text("Generate Graph Visualization"),
                            spacing="2",
                        ),
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
                    ),
                    spacing="4",
                    align_items="center",
                    width="100%",
                    padding="24px",
                ),
                variant="default"
            ),
        ),
        spacing="6",
        width="100%",
    )

def knowledge_graph_view(nodes_var, edges_var):
    """Premium state-driven claim graph view for Workspace"""
    return rx.vstack(
        section_header(
            "Knowledge Graph Explorer",
            "Claim network models extracted from contradiction pipeline detection.",
        ),
        rx.cond(
            nodes_var.length() == 0,
            premium_card(
                rx.vstack(
                    rx.text(
                        "No claim graph elements loaded. Run contradiction checks from the planner to output data.",
                        color=COLORS["text_secondary"],
                        font_family=FONTS["body"],
                        size="3",
                        text_align="center",
                    ),
                    spacing="2",
                    align_items="center",
                    width="100%",
                    padding="16px",
                ),
                variant="default"
            ),
            rx.vstack(
                # Node entity grids
                rx.grid(
                    rx.foreach(nodes_var, node_card),
                    columns="3",
                    spacing="4",
                    width="100%",
                ),
                rx.box(
                    height="1px",
                    width="100%",
                    background=f"linear-gradient(90deg, transparent, {COLORS['border_highlight']}, transparent)",
                    margin_y="6",
                ),
                rx.heading("Interactive Edge Relationships", size="5", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                
                # Relational edge cards
                rx.grid(
                    rx.foreach(
                        edges_var,
                        lambda e: rx.box(
                            rx.hstack(
                                rx.text(e["source"], size="1", color=COLORS["text_primary"], font_family=FONTS["mono"], line_height="1.4", flex="1"),
                                rx.badge(
                                    rx.hstack(
                                        rx.icon(tag="arrow-right-left", size=12),
                                        rx.text(e["label"]),
                                        spacing="1",
                                    ),
                                    color_scheme="indigo",
                                    variant="soft",
                                    size="1"
                                ),
                                rx.text(e["target"], size="1", color=COLORS["text_primary"], font_family=FONTS["mono"], line_height="1.4", flex="1", text_align="right"),
                                spacing="3",
                                align_items="center",
                                width="100%",
                            ),
                            padding="14px 18px",
                            border_radius="14px",
                            background=f"rgba(15, 23, 42, 0.4)",
                            border=f"1px solid {COLORS['border']}",
                            width="100%",
                            style={
                                "transition": "all 0.25s ease",
                                "_hover": {
                                    "borderColor": COLORS["border_highlight"],
                                    "background": "rgba(20, 30, 55, 0.45)",
                                }
                            }
                        ),
                    ),
                    columns="2",
                    spacing="3",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
        ),
        spacing="6",
        width="100%",
    )
