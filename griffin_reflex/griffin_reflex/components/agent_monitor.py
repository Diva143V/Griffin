import reflex as rx

def agent_monitor():
    agents = [
        ("Planner Agent", "IDLE", "gray"),
        ("Retrieval Agent", "ACTIVE", "green"),
        ("Evidence Agent", "ACTIVE", "green"),
        ("Reasoning Agent", "WAITING", "yellow"),
        ("Hypothesis Agent", "IDLE", "gray"),
        ("Scientific Writer", "IDLE", "gray")
    ]
    return rx.box(
        rx.vstack(
            rx.heading("Agent Status Monitor", size="5"),
            *[
                rx.hstack(
                    rx.text(name, weight="medium"),
                    rx.spacer(),
                    rx.badge(status, color_scheme=color, variant="solid"),
                    width="100%",
                    align_items="center"
                )
                for name, status, color in agents
            ],
            spacing="3",
            width="100%"
        ),
        padding="20px",
        border_radius="18px",
        background="rgba(17,24,39,0.75)",
        border="1px solid rgba(255,255,255,0.08)",
        width="100%"
    )
