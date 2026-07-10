import reflex as rx

def agent_monitor():
    from griffin_reflex.griffin_reflex import State
    return rx.box(
        rx.vstack(
            rx.heading("Agent Status Monitor", size="5"),
            rx.foreach(
                State.agent_statuses,
                lambda agent: rx.hstack(
                    rx.text(agent["name"], weight="medium"),
                    rx.spacer(),
                    rx.badge(agent["status"], color_scheme=agent["color"], variant="solid"),
                    width="100%",
                    align_items="center"
                )
            ),
            spacing="3",
            width="100%"
        ),
        padding="20px",
        border_radius="18px",
        background="rgba(17,24,39,0.75)",
        border="1px solid rgba(255,255,255,0.08)",
        width="100%"
    )
