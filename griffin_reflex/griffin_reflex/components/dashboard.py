import reflex as rx
from griffin_reflex.components.ui import metric, glass_card


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
    """Research command center — values come from live dataset metrics."""
    return rx.vstack(
        rx.heading("Research Command Center", size="9"),
        rx.text("Live metrics from your latest pipeline run (dataset/)", color="gray"),
        rx.grid(
            metric("Papers Analysed", papers, "📚"),
            metric("Evidence Score", evidence_score, "⭐"),
            metric("Contradictions", contradictions, "⚡"),
            metric("Agents (last run)", agents, "🧬"),
            columns="4",
            spacing="5",
            width="100%",
        ),
        rx.grid(
            metric("Claims extracted", claims, "🔎"),
            metric("Agreements / partial", agreements, "✅"),
            columns="2",
            spacing="5",
            width="100%",
        ),
        glass_card(
            rx.vstack(
                rx.heading("Current Research", size="5"),
                rx.text(goal, size="3"),
                rx.progress(value=progress),
                rx.text(pipeline_status, size="2", color="gray"),
                rx.link(
                    rx.button("Open Planner →", color_scheme="indigo"),
                    href="/",
                ),
                spacing="3",
                width="100%",
            )
        ),
        width="100%",
        spacing="6",
    )
