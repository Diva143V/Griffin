import reflex as rx

def discovery_card():
    from griffin_reflex.griffin_reflex import State
    return rx.box(
        rx.vstack(
            rx.heading(
                "New Scientific Discovery"
            ),
            rx.cond(
                State.consensus_report,
                rx.text(State.consensus_report[:150] + "...", color="gray"),
                rx.text("Run consensus analysis to generate discoveries.")
            ),
            rx.progress(
                value=92
            ),
            rx.hstack(
                rx.button("Open Report", on_click=rx.redirect("/reports")),
            )
        ),
        padding="25px",
        border_radius="25px",
        background="rgba(15,23,42,0.65)",
        border="1px solid rgba(255,255,255,0.08)"
    )
