import reflex as rx

def thinking_agent(name: str, status: str):
    return rx.box(
        rx.vstack(
            rx.text(
                "🧬",
                font_size="45px"
            ),
            rx.heading(name),
            rx.text(status)
        ),
        padding="30px",
        border_radius="25px",
        background="rgba(99,102,241,0.15)"
    )
