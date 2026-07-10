import reflex as rx

def graph():
    return rx.box(
        rx.vstack(
            rx.heading("Scientific Interaction Map", size="5"),
            rx.text("Interactive visual map showing target relationships.", size="2", color="gray"),
            rx.center(
                rx.vstack(
                    rx.text("🧬", font_size="50px"),
                    rx.text("[Metformin] ──(activates)──> [AMPK] ──(inhibits)──> [mTOR]", size="2"),
                    spacing="3"
                ),
                height="250px",
                width="100%",
                background="rgba(10,15,30,0.5)",
                border_radius="15px",
                border="1px dashed rgba(255,255,255,0.1)"
            )
        ),
        padding="20px",
        border_radius="18px",
        background="rgba(17,24,39,0.75)",
        border="1px solid rgba(255,255,255,0.08)",
        width="100%"
    )
