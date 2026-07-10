import reflex as rx

FONT = "'Inter', system-ui, sans-serif"

PAGE_BG = """
radial-gradient(
ellipse at top,
rgba(99,102,241,0.18),
transparent 50%
),
linear-gradient(
180deg,
#050816,
#0b1020
)
"""

CARD = {
    "background": "rgba(17,24,39,0.65)",
    "backdropFilter": "blur(20px)",
    "border": "1px solid rgba(255,255,255,0.08)",
    "borderRadius": "22px",
    "padding": "24px",
    "boxShadow": "0 20px 60px rgba(0,0,0,.35)",
}


def glass_card(content, **kwargs):
    style = dict(CARD)
    extra = kwargs.pop("style", None)
    if extra:
        style.update(extra)
    return rx.box(content, style=style, **kwargs)


def metric(title, value, icon):
    return glass_card(
        rx.vstack(
            rx.text(icon, font_size="28px"),
            rx.text(title, color="gray", size="2"),
            rx.heading(value, size="7"),
            spacing="2",
            align_items="flex-start",
        )
    )


def page_shell(sidebar_comp, body, bg: str = PAGE_BG):
    return rx.hstack(
        sidebar_comp,
        rx.box(
            body,
            padding="40px",
            width="100%",
            height="100vh",
            overflow="auto",
        ),
        width="100%",
        spacing="0",
        background=bg,
        style={"minHeight": "100vh"},
    )
