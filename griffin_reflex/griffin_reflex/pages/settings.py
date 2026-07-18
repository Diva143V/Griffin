import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.ui import page_shell, premium_card, section_header

def settings():
    """Redesigned configurations & settings page view"""
    return page_shell(
        sidebar(active="/settings"),
        rx.vstack(
            # Page Header
            section_header(
                "System Configurations",
                "Model routing, credential variables, and environment settings info."
            ),
            
            # Info Info Card
            premium_card(
                rx.vstack(
                    rx.heading("Interactive Control Panels", size="5", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                    rx.text("Griffin AI utilizes a distributed multi-agent system. Credentials and model parameters are fully adjustable inside the Planner tab sidebar workspace:", size="2", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                    
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="key-round", size=16, color=COLORS["accent"]),
                            rx.text("PubMed Email, Semantic Scholar Key, Gemini Key → Planner left panel", size="2", color=COLORS["text_primary"], font_family=FONTS["body"]),
                            spacing="3",
                        ),
                        rx.hstack(
                            rx.icon(tag="git-branch", size=16, color=COLORS["accent"]),
                            rx.text("Global / Custom Specialist specialist routing → Planner left panel", size="2", color=COLORS["text_primary"], font_family=FONTS["body"]),
                            spacing="3",
                        ),
                        rx.hstack(
                            rx.icon(tag="sliders-horizontal", size=16, color=COLORS["accent"]),
                            rx.text("Temperature, context window, max tokens, thinking mode → Planner left panel", size="2", color=COLORS["text_primary"], font_family=FONTS["body"]),
                            spacing="3",
                        ),
                        rx.hstack(
                            rx.icon(tag="database", size=16, color=COLORS["accent"]),
                            rx.text("Per-source crawler limits and datasets → Planner main tab", size="2", color=COLORS["text_primary"], font_family=FONTS["body"]),
                            spacing="3",
                        ),
                        spacing="3",
                        align_items="flex-start",
                        margin_y="2",
                    ),
                    
                    rx.box(
                        height="1px",
                        width="100%",
                        background=f"linear-gradient(90deg, {COLORS['border_highlight']}, transparent)",
                        margin_y="2",
                    ),
                    
                    rx.link(
                        rx.button(
                            rx.hstack(
                                rx.text("Launch Research Planner Controls"),
                                rx.icon(tag="sliders-horizontal", size=16),
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
                                "transition": "all 0.3s ease",
                                "_hover": {
                                    "transform": "translateY(-2px)",
                                    "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                                }
                            }
                        ),
                        href="/",
                        text_decoration="none",
                    ),
                    spacing="4",
                    width="100%",
                    align_items="flex-start",
                ),
                variant="default"
            ),
            
            # Default Model List Card
            premium_card(
                rx.vstack(
                    rx.heading("Default specialist Mixture (no global override)", size="5", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                    rx.text("When global routing is disabled, specialized micro-agents deploy the following configurations:", size="2", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                    
                    rx.grid(
                        rx.vstack(
                            rx.text("Planner Agent", size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            rx.badge("llama3.1:8b", color_scheme="indigo", variant="soft"),
                            align_items="flex-start",
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Claim Extractor", size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            rx.badge("llama3.1:8b", color_scheme="indigo", variant="soft"),
                            align_items="flex-start",
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Contradiction Detector", size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            rx.badge("qwen3.5:9b", color_scheme="indigo", variant="soft"),
                            align_items="flex-start",
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Consensus Analyst", size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            rx.badge("llama3-openbiollm-8b", color_scheme="indigo", variant="soft"),
                            align_items="flex-start",
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Synthesis & Protocol", size="1", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            rx.badge("llama3.1:8b", color_scheme="indigo", variant="soft"),
                            align_items="flex-start",
                            spacing="1",
                        ),
                        columns="2",
                        spacing="4",
                        width="100%",
                        margin_top="3",
                    ),
                    spacing="3",
                    width="100%",
                    align_items="flex-start",
                ),
                variant="glass"
            ),
            spacing="8",
            width="100%",
        ),
    )
