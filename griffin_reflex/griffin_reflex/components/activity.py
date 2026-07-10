import reflex as rx

EVENTS = [
    "🧬 Retrieved 25 papers",
    "⚡ Found evidence conflict",
    "🧬 Generated hypothesis",
    "🧬 Created review draft"
]

def activity_feed():
    return rx.vstack(
        *[
            rx.box(
                event,
                padding="15px",
                border_radius="15px",
                background="rgba(255,255,255,0.05)"
            )
            for event in EVENTS
        ],
        spacing="3",
        width="100%"
    )
