import reflex as rx

class AgentState(rx.State):
    logs: list[str] = [
        "Planner started",
        "Searching literature",
        "Ranking evidence",
        "Generating synthesis"
    ]

def live_agents():
    return rx.vstack(
        rx.heading("Live AI Scientists Execution Stream", size="5"),
        rx.foreach(
            AgentState.logs,
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
