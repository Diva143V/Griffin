import reflex as rx

def live_agents():
    from griffin_reflex.griffin_reflex import State
    return rx.vstack(
        rx.heading("Live AI Scientists Execution Stream", size="5"),
        rx.foreach(
            State.logs,
            lambda log:
            rx.box(
                rx.text(log, size="2", font_family="monospace"),
                padding="10px",
                border_radius="8px",
                background="rgba(255,255,255,0.05)",
                border="1px solid rgba(255,255,255,0.05)",
                width="100%"
            )
        ),
        spacing="3",
        width="100%"
    )
