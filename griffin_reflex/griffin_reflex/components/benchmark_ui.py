import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS

def metric_badge(icon: str, label: str, value: rx.Var, glow_color: str = "primary") -> rx.Component:
    """Helper to render a sleek stat block for dashboard comparisons"""
    return rx.box(
        rx.hstack(
            rx.center(
                rx.text(icon, font_size="16px"),
                width="32px",
                height="32px",
                border_radius="8px",
                background=f"{COLORS[glow_color]}15",
                border=f"1px solid {COLORS[glow_color]}30",
            ),
            rx.vstack(
                rx.text(label, size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                rx.text(value, size="2", weight="bold", color=COLORS["text_primary"], font_family=FONTS["mono"]),
                spacing="0",
                align_items="flex-start",
            ),
            spacing="2",
            align_items="center",
        ),
        padding="10px 14px",
        border_radius="14px",
        background="rgba(255, 255, 255, 0.02)",
        border=f"1px solid {COLORS['border']}",
        flex="1",
        min_width="100px",
    )

def tab_eval_content() -> rx.Component:
    """The main Benchmark evaluation tab content redesigned as a high-end comparison dashboard"""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        # Page Header
        rx.vstack(
            rx.heading(
                "RAG vs GraphRAG Performance",
                size="8",
                style={
                    "fontFamily": FONTS["heading"],
                    "letterSpacing": "-0.03em",
                    "background": f"linear-gradient(120deg, {COLORS['text_primary']} 0%, {COLORS['primary']} 45%, {COLORS['accent']} 100%)",
                    "WebkitBackgroundClip": "text",
                    "WebkitTextFillColor": "transparent",
                    "backgroundClip": "text",
                }
            ),
            rx.text(
                "Compare generation latency, citations accuracy, and relational data structures in real-time.",
                color=COLORS["text_secondary"],
                size="3",
                style={"lineHeight": "1.6"}
            ),
            spacing="2",
            margin_bottom="6",
            width="100%",
        ),

        # Input Control Bar
        rx.hstack(
            rx.input(
                placeholder="Enter evaluation query (e.g. key discoveries, drug interaction discrepancies)...",
                on_change=State.set_eval_question,
                size="3",
                style={
                    "minWidth": "320px",
                    "flex": "1",
                    "minHeight": "46px",
                    "fontFamily": FONTS["body"],
                    "background": "rgba(10, 15, 30, 0.8)",
                    "border": f"1px solid {COLORS['border_highlight']}",
                    "borderRadius": "14px",
                    "color": COLORS["text_primary"],
                    "transition": "all 0.3s ease",
                    "_focus": {
                        "borderColor": COLORS["primary"],
                        "boxShadow": f"0 0 15px {COLORS['primary_glow']}",
                    }
                },
            ),
            rx.hstack(
                rx.checkbox(
                    checked=State.use_tog,
                    on_change=State.set_use_tog,
                    style={"fontFamily": FONTS["body"], "cursor": "pointer"}
                ),
                rx.text("Iterative ToG", size="2", font_family=FONTS["body"], color=COLORS["text_primary"]),
                spacing="2",
                align_items="center",
            ),
            rx.button(
                rx.hstack(
                    rx.icon(tag="play", size=16),
                    rx.text("Run Benchmark", font_weight="600"),
                    spacing="2",
                ),
                on_click=State.run_benchmark,
                loading=State.eval_running,
                size="3",
                style={
                    "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                    "boxShadow": f"0 4px 20px {COLORS['primary_glow']}",
                    "border": "none",
                    "color": "white",
                    "borderRadius": "14px",
                    "minHeight": "46px",
                    "padding": "0 24px",
                    "cursor": "pointer",
                    "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                    "_hover": {
                        "transform": "translateY(-2px)",
                        "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                        "filter": "brightness(1.1)",
                    }
                }
            ),
            align_items="center",
            spacing="4",
            width="100%",
            wrap="wrap",
            background="rgba(15, 23, 42, 0.4)",
            padding="16px",
            border_radius="20px",
            border=f"1px solid {COLORS['border']}",
            margin_bottom="4",
        ),

        # Side-by-Side Dashboard Comparator
        rx.grid(
            # Column 1: Vector RAG Card
            rx.box(
                rx.vstack(
                    # Card Header
                    rx.hstack(
                        rx.hstack(
                            rx.text("💾", font_size="20px"),
                            rx.heading("Vector RAG", size="5", style={"fontFamily": FONTS["heading"], "color": COLORS["text_primary"]}),
                            spacing="2",
                        ),
                        rx.spacer(),
                        rx.badge("Standard", color_scheme="gray", variant="soft", size="1", radius="full"),
                        width="100%",
                        align_items="center",
                    ),
                    rx.box(
                        height="1px",
                        width="100%",
                        background=f"linear-gradient(90deg, {COLORS['border_highlight']}, transparent)",
                        margin_y="2",
                    ),
                    # Metrics Grid
                    rx.hstack(
                        metric_badge("⏱️", "Latency", State.std_latency, "primary"),
                        metric_badge("📄", "Citations", State.std_citations, "primary"),
                        metric_badge("📝", "Words", State.std_words, "primary"),
                        spacing="3",
                        width="100%",
                    ),
                    # Answer Scroll Area (IDE styling)
                    rx.box(
                        rx.scroll_area(
                            rx.markdown(State.std_ans),
                            height="300px",
                            width="100%",
                        ),
                        padding="16px",
                        border_radius="16px",
                        background="rgba(0, 0, 0, 0.25)",
                        border=f"1px solid {COLORS['border']}",
                        width="100%",
                    ),
                    # Sources
                    rx.cond(
                        State.std_sources_data.length() > 0,
                        rx.vstack(
                            rx.text("Retrieved Sources", weight="bold", size="2", color=COLORS["text_secondary"], font_family=FONTS["heading"]),
                            rx.foreach(
                                State.std_sources_data,
                                lambda s: rx.box(
                                    rx.hstack(
                                        rx.text("📚", font_size="14px"),
                                        rx.text(s['title'], size="1", color=COLORS["text_primary"], font_family=FONTS["body"], line_height="1.4"),
                                        align_items="flex-start",
                                        spacing="2",
                                    ),
                                    padding="10px 14px",
                                    border_radius="10px",
                                    background=f"rgba(15, 23, 42, 0.6)",
                                    border=f"1px solid {COLORS['border']}",
                                    width="100%",
                                    style={
                                        "transition": "all 0.2s ease",
                                        "_hover": {
                                            "borderColor": COLORS["border_highlight"],
                                            "transform": "translateX(4px)",
                                        }
                                    }
                                ),
                            ),
                            spacing="2",
                            width="100%",
                            margin_top="3",
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                padding="28px",
                border_radius="24px",
                background="rgba(15, 23, 42, 0.45)",
                border=f"1px solid {COLORS['border']}",
                border_left=f"4px solid {COLORS['text_muted']}",
                width="100%",
                style={
                    "boxShadow": "0 12px 30px rgba(0, 0, 0, 0.35)",
                    "backdropFilter": "blur(16px)",
                }
            ),

            # Column 2: Graph RAG Card
            rx.box(
                rx.vstack(
                    # Card Header
                    rx.hstack(
                        rx.hstack(
                            rx.text("🕸️", font_size="20px"),
                            rx.heading("Graph RAG", size="5", style={"fontFamily": FONTS["heading"], "color": COLORS["text_primary"]}),
                            spacing="2",
                        ),
                        rx.spacer(),
                        rx.badge("ADVANCED", color_scheme="indigo", variant="soft", size="1", radius="full"),
                        width="100%",
                        align_items="center",
                    ),
                    rx.box(
                        height="1px",
                        width="100%",
                        background=f"linear-gradient(90deg, {COLORS['primary']}, transparent)",
                        margin_y="2",
                    ),
                    # Metrics Grid
                    rx.hstack(
                        metric_badge("⏱️", "Latency", State.graph_latency, "accent"),
                        metric_badge("📄", "Citations", State.graph_citations, "accent"),
                        metric_badge("📝", "Words", State.graph_words, "accent"),
                        spacing="3",
                        width="100%",
                    ),
                    # Answer Scroll Area (IDE styling with glow)
                    rx.box(
                        rx.scroll_area(
                            rx.markdown(State.graph_ans),
                            height="300px",
                            width="100%",
                        ),
                        padding="16px",
                        border_radius="16px",
                        background="rgba(0, 0, 0, 0.25)",
                        border=f"1px solid {COLORS['primary']}20",
                        width="100%",
                        style={"boxShadow": f"inset 0 0 15px {COLORS['primary_glow']}10"}
                    ),
                    # Sources
                    rx.cond(
                        State.graph_sources_data.length() > 0,
                        rx.vstack(
                            rx.text("Graph-Ranked Sources", weight="bold", size="2", color=COLORS["text_secondary"], font_family=FONTS["heading"]),
                            rx.foreach(
                                State.graph_sources_data,
                                lambda s: rx.box(
                                    rx.hstack(
                                        rx.text("📚", font_size="14px"),
                                        rx.text(s['title'], size="1", color=COLORS["text_primary"], font_family=FONTS["body"], line_height="1.4"),
                                        align_items="flex-start",
                                        spacing="2",
                                    ),
                                    padding="10px 14px",
                                    border_radius="10px",
                                    background=f"rgba(99, 102, 241, 0.04)",
                                    border=f"1px solid {COLORS['primary']}25",
                                    width="100%",
                                    style={
                                        "transition": "all 0.2s ease",
                                        "_hover": {
                                            "borderColor": COLORS["primary"],
                                            "boxShadow": f"0 0 10px {COLORS['primary_glow']}",
                                            "transform": "translateX(4px)",
                                        }
                                    }
                                ),
                            ),
                            spacing="2",
                            width="100%",
                            margin_top="3",
                        ),
                    ),
                    # Relations
                    rx.cond(
                        State.graph_relations_data.length() > 0,
                        rx.vstack(
                            rx.text("Extracted Graph Relationships", weight="bold", size="2", color=COLORS["text_secondary"], font_family=FONTS["heading"]),
                            rx.foreach(
                                State.graph_relations_data,
                                lambda r: rx.box(
                                    rx.hstack(
                                        rx.text("🔗", font_size="14px"),
                                        rx.text(r['title'], size="1", color=COLORS["accent"], font_family=FONTS["mono"], line_height="1.4"),
                                        align_items="center",
                                        spacing="2",
                                    ),
                                    padding="10px 14px",
                                    border_radius="10px",
                                    background=f"rgba(6, 182, 212, 0.04)",
                                    border=f"1px solid {COLORS['accent']}25",
                                    width="100%",
                                    style={
                                        "transition": "all 0.2s ease",
                                        "_hover": {
                                            "borderColor": COLORS["accent"],
                                            "boxShadow": f"0 0 10px {COLORS['accent_glow']}",
                                            "transform": "translateX(4px)",
                                        }
                                    }
                                ),
                            ),
                            spacing="2",
                            width="100%",
                            margin_top="3",
                        ),
                    ),
                    spacing="4",
                    width="100%",
                ),
                padding="28px",
                border_radius="24px",
                background="rgba(15, 23, 42, 0.45)",
                border=f"1px solid {COLORS['primary']}40",
                border_left=f"4px solid {COLORS['primary']}",
                width="100%",
                style={
                    "boxShadow": f"0 12px 40px -10px {COLORS['primary_glow']}, 0 12px 30px rgba(0, 0, 0, 0.35)",
                    "backdropFilter": "blur(16px)",
                }
            ),
            columns="2",
            spacing="5",
            width="100%",
            margin_top="4",
            align_items="stretch",
        ),
        spacing="4",
        width="100%",
    )
