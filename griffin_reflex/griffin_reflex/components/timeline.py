import reflex as rx

EVENTS = [
    ("2015", "Metformin linked with cancer metabolism"),
    ("2019", "Clinical studies show mixed results"),
    ("2022", "Large cohort analysis contradicts earlier findings"),
    ("2025", "Meta analysis suggests patient subgroup effects")
]

def research_timeline():
    return rx.vstack(
        rx.heading(
            "Research Evolution Timeline",
            size="7"
        ),
        *[
            rx.hstack(
                rx.badge(
                    event[0],
                    size="3"
                ),
                rx.text(
                    event[1]
                ),
                spacing="5"
            )
            for event in EVENTS
        ],
        spacing="5"
    )
