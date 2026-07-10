import reflex as rx

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.dashboard import dashboard as dashboard_comp
from griffin_reflex.components.ui import page_shell
from griffin_reflex.data_layer import get_dashboard_metrics


class DashboardState(rx.State):
    papers: str = "0"
    evidence_score: str = "—"
    contradictions: str = "0"
    agents: str = "—"
    goal: str = "No active research run yet"
    pipeline_status: str = "Idle"
    progress: int = 0
    claims: str = "0"
    agreements: str = "0"

    @rx.event
    def load_metrics(self):
        m = get_dashboard_metrics()
        self.papers = m["papers"]
        self.evidence_score = m["evidence_score"]
        self.contradictions = m["contradictions"]
        self.agents = m["agents"]
        self.goal = m["goal"]
        self.pipeline_status = m["pipeline_status"]
        try:
            self.progress = int(m["progress"])
        except Exception:
            self.progress = 0
        self.claims = m["claims"]
        self.agreements = m["agreements"]


def dashboard():
    return page_shell(
        sidebar(active="/dashboard"),
        rx.vstack(
            rx.hstack(
                rx.spacer(),
                rx.button(
                    "↻ Refresh metrics",
                    on_click=DashboardState.load_metrics,
                    variant="soft",
                    color_scheme="indigo",
                ),
                width="100%",
            ),
            dashboard_comp(
                papers=DashboardState.papers,
                evidence_score=DashboardState.evidence_score,
                contradictions=DashboardState.contradictions,
                agents=DashboardState.agents,
                goal=DashboardState.goal,
                pipeline_status=DashboardState.pipeline_status,
                progress=DashboardState.progress,
                claims=DashboardState.claims,
                agreements=DashboardState.agreements,
            ),
            spacing="4",
            width="100%",
        ),
    )
