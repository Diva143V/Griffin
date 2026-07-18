import reflex as rx
from griffin_reflex.components.ui import premium_card, metric, section_header, divider
from griffin_reflex.styles.theme import COLORS, FONTS

def dashboard(
    papers="0",
    evidence_score="—",
    contradictions="0",
    agents="—",
    goal="No active research run yet",
    pipeline_status="Idle",
    progress=0,
    claims="0",
    agreements="0",
):
    """Premium research command center dashboard component"""
    return rx.vstack(
        # Page Header block
        section_header(
            "Research Command Center",
            "Live system metrics and execution states from your latest agent runs.",
            action=None
        ),
        
        # Primary Metrics Grid
        rx.grid(
            metric("Papers Analyzed", papers, "📚", color="primary"),
            metric("Evidence Quality", evidence_score, "⭐", color="accent"),
            metric("Contradictions", contradictions, "⚡", color="warning"),
            metric("Deployed Agents", agents, "🧬", color="success"),
            columns="4",
            spacing="5",
            width="100%",
        ),
        
        # Secondary Metrics Grid
        rx.grid(
            metric("Claims Extracted", claims, "🔎", color="primary"),
            metric("Claims Agreed / Partial", agreements, "✅", color="success"),
            columns="2",
            spacing="5",
            width="100%",
        ),
        
        divider("6"),
        
        # Current Active Research Card
        premium_card(
            rx.vstack(
                rx.hstack(
                    rx.hstack(
                        rx.icon(tag="microscope", size=22, color=COLORS["primary"]),
                        rx.heading("Active Research Mission", size="5", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                        spacing="3",
                        align_items="center",
                    ),
                    rx.spacer(),
                    rx.badge(
                        pipeline_status,
                        color_scheme="green",
                        variant="soft",
                        size="2",
                        style={
                            "padding": "4px 12px",
                            "borderRadius": "999px",
                            "border": f"1px solid {COLORS['success']}40",
                            "color": COLORS["success"],
                            "background": f"{COLORS['success']}12",
                        }
                    ),
                    width="100%",
                    align_items="center",
                ),
                rx.text(
                    goal,
                    size="3",
                    color=COLORS["text_primary"],
                    font_family=FONTS["body"],
                    line_height="1.6",
                    style={"opacity": 0.95}
                ),
                
                # Dynamic Progress Bar section
                rx.vstack(
                    rx.hstack(
                        rx.text("Pipeline Progress", size="2", color=COLORS["text_secondary"]),
                        rx.text(f"{progress}%", size="2", color=COLORS["primary"], font_family=FONTS["mono"], font_weight="700"),
                        spacing="2",
                        width="100%",
                        justify_content="space-between",
                    ),
                    rx.progress(
                        value=progress,
                        color_scheme="indigo",
                        style={
                            "height": "8px",
                            "borderRadius": "6px",
                            "background": "rgba(255, 255, 255, 0.05)",
                            "border": f"1px solid {COLORS['border']}",
                        }
                    ),
                    spacing="2",
                    width="100%",
                ),
                
                # Redirect button
                rx.link(
                    rx.button(
                        rx.hstack(
                            rx.text("Open Research Planner"),
                            rx.icon(tag="arrow-right", size=16),
                            spacing="2",
                        ),
                        size="3",
                        style={
                            "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                            "boxShadow": f"0 4px 15px {COLORS['primary_glow']}",
                            "border": "none",
                            "color": "white",
                            "borderRadius": "12px",
                            "padding": "0 24px",
                            "minHeight": "44px",
                            "cursor": "pointer",
                            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                            "_hover": {
                                "transform": "translateY(-2px)",
                                "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                            }
                        }
                    ),
                    href="/",
                    text_decoration="none",
                ),
                spacing="5",
                width="100%",
                align_items="flex-start",
            ),
            variant="accent"
        ),
        
        width="100%",
        spacing="6",
    )
