import reflex as rx
from griffin_reflex.components.ui import metric, glass_card

def dashboard():
    return rx.vstack(
        rx.heading(
            "Research Command Center",
            size="9"
        ),
        rx.text(
            "Your autonomous scientific workspace",
            color="gray"
        ),
        rx.grid(
            metric("Papers Analysed", "250", "📚"),
            metric("Evidence Score", "92%", "⭐"),
            metric("Contradictions", "18", "⚡"),
            metric("Agents", "7", "🧬"),
            columns="4",
            spacing="5",
            width="100%"
        ),
        glass_card(
            rx.vstack(
                rx.heading(
                    "Current Research"
                ),
                rx.text(
                    "Metformin effect on cancer recurrence"
                ),
                rx.progress(
                    value=72
                ),
                rx.text(
                    "Pipeline: Evidence synthesis running"
                )
            )
        ),
        width="100%",
        spacing="6"
    )
