import reflex as rx

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.dashboard import dashboard as dashboard_comp

def dashboard():
    return rx.hstack(
        sidebar(),
        rx.box(
            dashboard_comp(),
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
