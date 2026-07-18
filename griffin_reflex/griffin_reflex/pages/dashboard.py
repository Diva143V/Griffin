import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.dashboard import dashboard as dashboard_comp
from griffin_reflex.components.ui import page_shell

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
        from griffin_reflex.griffin_reflex import State
        parent = self.get_state(State)
        m = get_dashboard_metrics(parent.run_dir)
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

def get_dashboard_metrics(dataset_dir: str = None):
    """Import wrapper helper to resolve dynamic imports cleanly"""
    from griffin_reflex.data_layer import get_dashboard_metrics as dm
    return dm(dataset_dir)

def dashboard():
    """Redesigned Research Command Center page view"""
    return page_shell(
        sidebar(active="/dashboard"),
        rx.vstack(
            # Top metrics controls row
            rx.hstack(
                rx.spacer(),
                rx.button(
                    rx.hstack(
                        rx.icon(tag="refresh-cw", size=16),
                        rx.text("Refresh Metrics"),
                        spacing="2",
                    ),
                    on_click=DashboardState.load_metrics,
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
                width="100%",
                padding_bottom="4",
            ),
            
            # The metrics layout block
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
