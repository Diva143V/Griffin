import reflex as rx

from griffin_reflex.components.sidebar import sidebar

def settings():
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.vstack(
                rx.heading("System Configuration & Settings", size="9"),
                rx.text("Configure global LLM models, API keys, and database backends.", color="gray"),
                rx.card(
                    rx.vstack(
                        rx.heading("Models Routing & Priority", size="4"),
                        rx.text("Planner Model: llama3.1:8b"),
                        rx.text("Reasoner Model: qwen3.5:9b"),
                        rx.text("Writer Model: koesn/llama3-openbiollm-8b"),
                        spacing="2"
                    )
                ),
                spacing="6",
                width="100%"
            ),
            padding="40px",
            width="100%",
            height="100vh",
            overflow="auto"
        ),
        width="100%",
        background="""
        radial-gradient(
        ellipse at top,
        #111827,
        #020617
        )
        """
    )
