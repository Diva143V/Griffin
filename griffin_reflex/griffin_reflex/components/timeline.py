import reflex as rx


def research_timeline():
    """Main State timeline from ranked paper years."""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        rx.heading("Research Evolution Timeline", size="7"),
        rx.foreach(
            State.timeline_events,
            lambda event: rx.hstack(
                rx.badge(event["year"], size="3", color_scheme="indigo"),
                rx.text(event["title"], size="3"),
                spacing="5",
                align_items="center",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )


def research_timeline_view(events_var):
    """Workspace timeline driven by data_layer / WorkspaceState (year + text)."""
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
