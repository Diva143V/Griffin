import reflex as rx

def activity_feed():
    from griffin_reflex.griffin_reflex import State
    return rx.vstack(
        rx.foreach(
            State.logs.reverse()[:5],
            lambda event: rx.box(
                event,
                padding="15px",
                border_radius="15px",
                background="rgba(255,255,255,0.05)"
            )
        ),
        spacing="3",
        width="100%"
    )
