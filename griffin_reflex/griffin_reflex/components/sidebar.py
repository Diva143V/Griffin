import reflex as rx

# Unified navigation for all V2 shell pages + link into the real Planner workbench
MENU = [
    ("🏠", "Dashboard", "/dashboard"),
    ("🧭", "Planner", "/"),
    ("🧬", "Workspace", "/workspace"),
    ("🧪", "Labs", "/projects"),
    ("⚙️", "Settings", "/settings"),
]


def sidebar(active: str = ""):
    """Shared app sidebar. `active` is the current route path for highlight."""
    return rx.box(
        rx.vstack(
            rx.heading("🧬 Griffin AI", size="7"),
            rx.text("Scientific Intelligence Platform", color="gray", size="2"),
            rx.divider(),
            rx.vstack(
                *[
                    rx.link(
                        rx.button(
                            f"{icon}  {name}",
                            width="100%",
                            variant="solid" if path == active else "ghost",
                            color_scheme="indigo" if path == active else "gray",
                            justify_content="start",
                        ),
                        href=path,
                        width="100%",
                        text_decoration="none",
                    )
                    for icon, name, path in MENU
                ],
                width="100%",
                spacing="2",
            ),
            rx.spacer(),
            rx.box(
                rx.text("Pipeline", weight="bold", size="2", color="var(--green-11)"),
                rx.text(
                    "Use Planner to run agents. Dashboard & Workspace read live dataset files.",
                    size="1",
                    color="gray",
                ),
                padding="15px",
                border_radius="15px",
                background="rgba(34,197,94,.1)",
                width="100%",
            ),
            height="100%",
            width="100%",
            spacing="3",
        ),
        width="280px",
        min_width="280px",
        height="100vh",
        padding="25px",
        background="rgba(5,8,22,.9)",
        border_right="1px solid rgba(255,255,255,.08)",
    )
