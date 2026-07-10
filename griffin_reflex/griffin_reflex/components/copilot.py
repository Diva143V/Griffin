import reflex as rx

def copilot():
    return rx.box(
        rx.vstack(
            rx.heading("🧬 AI Copilot", size="4"),
            rx.text("Ask questions on evidence or draft protocols.", size="1", color="gray"),
            rx.scroll_area(
                rx.vstack(
                    rx.box(
                        rx.text("Assistant", weight="bold", size="1", color="indigo"),
                        rx.text("How can I assist you with tumor metabolism analysis today?", size="2"),
                        padding="10px",
                        border_radius="10px",
                        background="rgba(255,255,255,0.05)"
                    )
                ),
                height="200px",
                width="100%"
            ),
            rx.hstack(
                rx.input(placeholder="Ask copilot...", size="1", style={"flex": 1}),
                rx.button("Send", size="1")
            ),
            spacing="3"
        ),
        padding="20px",
        border_radius="20px",
        background="rgba(15,23,42,0.85)",
        border="1px solid rgba(255,255,255,0.08)",
        width="300px"
    )
