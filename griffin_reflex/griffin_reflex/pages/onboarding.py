import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS, gradient_background
from griffin_reflex.data_layer import save_research_goal
from griffin_reflex.components.ui import input_field, premium_card

class OnboardingState(rx.State):
    research_goal: str = ""

    @rx.event
    def set_research_goal(self, value: str):
        self.research_goal = value

    @rx.event
    def start(self):
        goal = (self.research_goal or "").strip()
        if goal:
            save_research_goal(goal)
        # Redirect to the main planner workspace route
        return rx.redirect("/")

def onboarding():
    """Redesigned premium scientific onboarding page"""
    return rx.center(
        rx.vstack(
            # Logo and Welcome Header Block
            rx.vstack(
                rx.center(
                    rx.text(
                        "🧬",
                        font_size="64px",
                        style={"filter": f"drop-shadow(0 0 24px {COLORS['primary_glow']})"}
                    ),
                    width="100px",
                    height="100px",
                    border_radius="24px",
                    background=f"rgba(99, 102, 241, 0.08)",
                    border=f"1px solid {COLORS['primary']}20",
                    margin_bottom="4",
                ),
                rx.heading(
                    "Welcome to Griffin AI",
                    size="9",
                    color=COLORS["text_primary"],
                    font_family=FONTS["heading"],
                    style={
                        "letterSpacing": "-0.03em",
                        "fontWeight": "800",
                        "background": f"linear-gradient(135deg, {COLORS['text_primary']} 30%, {COLORS['primary']} 80%, {COLORS['accent']} 100%)",
                        "WebkitBackgroundClip": "text",
                        "WebkitTextFillColor": "transparent",
                    }
                ),
                rx.text(
                    "Your autonomous scientific research agent & intelligence partner",
                    size="4",
                    color=COLORS["text_secondary"],
                    font_family=FONTS["body"],
                    text_align="center",
                ),
                spacing="3",
                align_items="center",
            ),
            
            # Interactive Setup Card
            premium_card(
                rx.vstack(
                    rx.text(
                        "Define Research Objective",
                        size="4",
                        color=COLORS["text_primary"],
                        font_family=FONTS["heading"],
                        weight="bold",
                    ),
                    rx.text(
                        "Enter your query or research goal. Our multi-agent system will gather papers, extract claims, search for contradictions, and synthesis findings.",
                        size="2",
                        color=COLORS["text_secondary"],
                        font_family=FONTS["body"],
                        line_height="1.5",
                    ),
                    input_field(
                        "e.g. Compare mechanism of action of metformin and berberine in AMPK activation...",
                        OnboardingState.research_goal,
                        OnboardingState.set_research_goal,
                    ),
                    rx.text(
                        "Goal files are saved live on disk (dataset/) and can be edited anytime inside the Planner tab.",
                        size="1",
                        color=COLORS["text_muted"],
                        font_family=FONTS["body"],
                    ),
                    rx.button(
                        rx.hstack(
                            rx.text("Initialize AI Scientist"),
                            rx.icon(tag="arrow-right", size=18),
                            spacing="2",
                        ),
                        on_click=OnboardingState.start,
                        size="3",
                        width="100%",
                        style={
                            "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                            "boxShadow": f"0 6px 25px {COLORS['primary_glow']}",
                            "border": "none",
                            "color": "white",
                            "borderRadius": "14px",
                            "padding": "16px 24px",
                            "minHeight": "48px",
                            "cursor": "pointer",
                            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                            "_hover": {
                                "transform": "translateY(-3px)",
                                "boxShadow": f"0 10px 30px {COLORS['primary_glow']}",
                                "filter": "brightness(1.1)",
                            }
                        }
                    ),
                    spacing="4",
                    width="100%",
                    align_items="flex-start",
                ),
                variant="accent"
            ),
            
            # Action Skip Link
            rx.link(
                rx.hstack(
                    rx.text("Skip setup and view dashboard"),
                    rx.icon(tag="chevron-right", size=14),
                    spacing="1",
                ),
                href="/dashboard",
                size="2",
                color=COLORS["text_secondary"],
                font_family=FONTS["body"],
                style={
                    "transition": "all 0.2s ease",
                    "_hover": {
                        "color": COLORS["primary"],
                    }
                }
            ),
            
            spacing="6",
            width="100%",
            max_width="620px",
            align_items="center",
        ),
        height="100vh",
        background=gradient_background(),
        style={
            "padding": "40px",
            "overflow": "hidden",
        },
    )
