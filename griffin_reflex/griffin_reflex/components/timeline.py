import reflex as rx


def research_timeline(events: list | None = None):
    events = events or []
    if not events:
        return rx.vstack(
            rx.heading("Research Evolution Timeline", size="7"),
            rx.text("No year metadata yet — run the Planner to collect papers.", color="gray"),
            spacing="4",
            width="100%",
        )
    return rx.vstack(
        rx.heading("Research Evolution Timeline", size="7"),
        *[
            rx.hstack(
                rx.badge(e.get("year", "—"), size="3", color_scheme="indigo"),
                rx.text(e.get("text", ""), size="3"),
                spacing="5",
                align_items="center",
                width="100%",
            )
            for e in events
        ],
        spacing="4",
        width="100%",
    )


def research_timeline_view(events_var):
    return rx.vstack(
        rx.heading("Research Evolution Timeline", size="7"),
        rx.cond(
            events_var.length() == 0,
            rx.text("No timeline data yet.", color="gray"),
            rx.foreach(
                events_var,
                lambda e: rx.hstack(
                    rx.badge(e["year"], size="3", color_scheme="indigo"),
                    rx.text(e["text"], size="3"),
                    spacing="5",
                    align_items="center",
                    width="100%",
                ),
            ),
        ),
        spacing="4",
        width="100%",
    )
