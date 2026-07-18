import reflex as rx
import os
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.ui import page_shell, premium_card, section_header
from griffin_reflex.data_layer import DATASET_DIR, get_dashboard_metrics, load_research_goal

class ProjectsState(rx.State):
    goal: str = ""
    papers: str = "0"
    contradictions: str = "0"
    status: str = "No local run yet"
    has_trace: bool = False

    @rx.event
    def load_projects(self):
        from griffin_reflex.griffin_reflex import State
        parent = self.get_state(State)
        run_dir_path = parent.run_dir
        m = get_dashboard_metrics(run_dir_path)
        self.goal = load_research_goal(run_dir_path) or m.get("goal", "")
        self.papers = m["papers"]
        self.contradictions = m["contradictions"]
        self.status = m["pipeline_status"]
        self.has_trace = os.path.exists(os.path.join(run_dir_path, "execution_trace.json"))

def projects():
    """Redesigned local scientific lab workspaces list view"""
    return page_shell(
        sidebar(active="/projects"),
        rx.vstack(
            # Page Header with refresh button
            section_header(
                "Scientific Research Laboratories",
                "Local single-user workspace. Connect and analyze runs from disk.",
                action=rx.button(
                    rx.hstack(
                        rx.icon(tag="refresh-cw", size=16),
                        rx.text("Refresh Labs"),
                        spacing="2",
                    ),
                    on_click=ProjectsState.load_projects,
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
            
            # Laboratory Card
            premium_card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("Griffin Local Lab Workspace", size="5", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                            rx.text(f"Query Objective: {ProjectsState.goal}", size="2", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                            spacing="1",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        rx.badge("Local SaaS Mode", color_scheme="indigo", variant="solid", radius="full"),
                        align_items="flex-start",
                        width="100%",
                    ),
                    
                    rx.box(
                        height="1px",
                        width="100%",
                        background=f"linear-gradient(90deg, {COLORS['border_highlight']}, transparent)",
                        margin_y="2",
                    ),
                    
                    # Lab Stat Badges
                    rx.flex(
                        rx.badge(
                            rx.hstack(
                                rx.icon(tag="file-text", size=14),
                                rx.text(f"{ProjectsState.papers} Papers Indexed"),
                                spacing="2",
                            ),
                            size="2",
                            style={
                                "background": f"{COLORS['primary']}15",
                                "border": f"1px solid {COLORS['primary']}40",
                                "color": COLORS["primary"],
                                "fontFamily": FONTS["body"],
                                "padding": "4px 12px",
                                "borderRadius": "999px",
                            }
                        ),
                        rx.badge(
                            rx.hstack(
                                rx.icon(tag="git-pull-request-draft", size=14),
                                rx.text(f"{ProjectsState.contradictions} Contradictions"),
                                spacing="2",
                            ),
                            size="2",
                            style={
                                "background": f"{COLORS['warning']}15",
                                "border": f"1px solid {COLORS['warning']}40",
                                "color": COLORS["warning"],
                                "fontFamily": FONTS["body"],
                                "padding": "4px 12px",
                                "borderRadius": "999px",
                            }
                        ),
                        rx.cond(
                            ProjectsState.has_trace,
                            rx.badge(
                                rx.hstack(
                                    rx.icon(tag="check-check", size=14),
                                    rx.text("Execution Trace Present"),
                                    spacing="2",
                                ),
                                size="2",
                                style={
                                    "background": f"{COLORS['success']}15",
                                    "border": f"1px solid {COLORS['success']}40",
                                    "color": COLORS["success"],
                                    "fontFamily": FONTS["body"],
                                    "padding": "4px 12px",
                                    "borderRadius": "999px",
                                }
                            ),
                            rx.badge(
                                rx.hstack(
                                    rx.icon(tag="triangle-alert", size=14),
                                    rx.text("No Execution Trace Found"),
                                    spacing="2",
                                ),
                                size="2",
                                style={
                                    "background": f"{COLORS['text_muted']}15",
                                    "border": f"1px solid {COLORS['border']}",
                                    "color": COLORS["text_secondary"],
                                    "fontFamily": FONTS["body"],
                                    "padding": "4px 12px",
                                    "borderRadius": "999px",
                                }
                            ),
                        ),
                        gap="3",
                        wrap="wrap",
                    ),
                    
                    rx.text(f"Status: {ProjectsState.status}", size="2", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                    
                    # Planner Link button
                    rx.link(
                        rx.button(
                            rx.hstack(
                                rx.text("Launch Research Planner"),
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
                    spacing="5",
                    width="100%",
                    align_items="flex-start",
                ),
                variant="accent"
            ),
            spacing="8",
            width="100%",
        ),
    )
