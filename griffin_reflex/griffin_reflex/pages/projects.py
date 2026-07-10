import reflex as rx
import os

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.ui import page_shell, glass_card
from griffin_reflex.data_layer import DATASET_DIR, get_dashboard_metrics, load_research_goal


class ProjectsState(rx.State):
    goal: str = ""
    papers: str = "0"
    contradictions: str = "0"
    status: str = "No local run yet"
    has_trace: bool = False

    @rx.event
    def load_projects(self):
        m = get_dashboard_metrics()
        self.goal = load_research_goal() or m.get("goal", "")
        self.papers = m["papers"]
        self.contradictions = m["contradictions"]
        self.status = m["pipeline_status"]
        self.has_trace = os.path.exists(os.path.join(DATASET_DIR, "execution_trace.json"))


def projects():
    return page_shell(
        sidebar(active="/projects"),
        rx.vstack(
            rx.hstack(
                rx.heading("Research Projects & Laboratories", size="9"),
                rx.spacer(),
                rx.button(
                    "↻ Refresh",
                    on_click=ProjectsState.load_projects,
                    variant="soft",
                    color_scheme="indigo",
                ),
                width="100%",
            ),
            rx.text(
                "Local single-user workspace (multi-lab SaaS is not enabled yet). "
                "This view reflects your last pipeline run on disk.",
                color="gray",
            ),
            glass_card(
                rx.vstack(
                    rx.heading("Active local lab", size="5"),
                    rx.text("Griffin Local Workspace", weight="bold"),
                    rx.text(f"Goal: {ProjectsState.goal}", size="2"),
                    rx.hstack(
                        rx.badge(f"{ProjectsState.papers} papers", color_scheme="indigo"),
                        rx.badge(f"{ProjectsState.contradictions} contradictions", color_scheme="orange"),
                        spacing="2",
                    ),
                    rx.text(ProjectsState.status, size="2", color="gray"),
                    rx.cond(
                        ProjectsState.has_trace,
                        rx.badge("execution_trace.json present", color_scheme="green"),
                        rx.badge("No execution_trace.json yet", color_scheme="gray"),
                    ),
                    rx.link(
                        rx.button("Continue in Planner →", color_scheme="indigo"),
                        href="/",
                    ),
                    spacing="3",
                    width="100%",
                )
            ),
            spacing="6",
            width="100%",
        ),
    )
