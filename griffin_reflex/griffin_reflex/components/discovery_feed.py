import reflex as rx

def discovery_card():
    return rx.box(
        rx.vstack(
            rx.heading(
                "New Scientific Discovery"
            ),
            rx.text(
                "Metformin response differs between tumour subtypes"
            ),
            rx.progress(
                value=92
            ),
            rx.hstack(
                rx.button("Accept"),
                rx.button("Review")
            )
        ),
        padding="25px",
        border_radius="25px",
        background="rgba(15,23,42,0.65)",
        border="1px solid rgba(255,255,255,0.08)"
    )
