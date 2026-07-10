import reflex as rx

from griffin_reflex.components.sidebar import sidebar

def projects():
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.vstack(
                rx.heading("Research Projects & Laboratories", size="9"),
                rx.text("Collaborative and persistent multi-user workspaces.", color="gray"),
                rx.grid(
                    rx.card(
                        rx.vstack(
                            rx.heading("Oncology Lab A", size="5"),
                            rx.text("Owner: Dr. Smith"),
                            rx.badge("3 Members", color_scheme="indigo"),
                            spacing="3"
                        )
                    ),
                    rx.card(
                        rx.vstack(
                            rx.heading("Metabolism Lab B", size="5"),
                            rx.text("Owner: Dr. Watson"),
                            rx.badge("5 Members", color_scheme="green"),
                            spacing="3"
                        )
                    ),
                    columns="2",
                    spacing="5",
                    width="100%"
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
