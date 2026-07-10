import reflex as rx

def research_timeline():
    from griffin_reflex.griffin_reflex import State
    return rx.vstack(
        rx.heading(
            "Research Evolution Timeline",
            size="7"
        ),
        rx.foreach(
            State.timeline_events,
            lambda event: rx.hstack(
                rx.badge(
                    event["year"],
                    size="3"
                ),
                rx.text(
                    event["title"]
                ),
                spacing="5"
            )
        ),
        spacing="5"
    )
