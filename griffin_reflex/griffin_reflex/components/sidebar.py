import reflex as rx

def sidebar():
    menu = [
        ("🏠", "Dashboard", "/"),
        ("🧬", "Research", "/workspace"),
        ("🧬", "Agents", "/workspace"),
        ("🕸️", "Knowledge Graph", "/workspace"),
        ("📚", "Evidence", "/workspace"),
        ("🧬", "Reports", "/workspace"),
        ("⚙️", "Settings", "/workspace")
    ]
    return rx.box(
        rx.vstack(
            rx.heading(
                "🧬 Griffin AI",
                size="7"
            ),
            rx.text(
                "Scientific Intelligence Platform",
                color="gray"
            ),
            rx.divider(),
            rx.vstack(
                *[
                    rx.button(
                        icon + "  " + name,
                        width="100%",
                        variant="ghost",
                        justify_content="start",
                        on_click=rx.redirect(path)
                    )
                    for icon, name, path in menu
                ],
                width="100%",
                spacing="3"
            ),
            rx.spacer(),
            rx.box(
                rx.text(
                    "AI Scientist Online",
                    color="green"
                ),
                rx.text(
                    "7 Agents Active",
                    size="2"
                ),
                padding="15px",
                border_radius="15px",
                background="rgba(34,197,94,.1)"
            ),
            height="100%",
            width="100%",
        ),
        width="280px",
        height="100vh",
        padding="25px",
        background="rgba(5,8,22,.9)",
        border_right="1px solid rgba(255,255,255,.08)"
    )
