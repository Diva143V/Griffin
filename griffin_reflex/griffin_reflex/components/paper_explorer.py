import reflex as rx

def paper_card(p):
    return rx.box(
        rx.vstack(
            rx.heading(
                p["title"],
                size="4"
            ),
            rx.text(
                p["source"]
            ),
            rx.hstack(
                rx.badge(
                    p["year"]
                ),
                rx.badge(
                    f"Evidence {p['score']}/10"
                )
            ),
            rx.link(
                rx.button(
                    "Open Analysis"
                ),
                href=p["url"] if "url" in p else "#"
            )
        ),
        padding="25px",
        border_radius="20px",
        background="rgba(15,23,42,0.8)"
    )

def paper_explorer():
    from griffin_reflex.griffin_reflex import State
    return rx.vstack(
        rx.heading(
            "Scientific Literature Explorer",
            size="7"
        ),
        rx.input(
            placeholder="Search papers...",
            on_change=State.set_paper_search_query
        ),
        rx.grid(
            rx.foreach(
                State.filtered_ranked_papers,
                paper_card
            ),
            columns="3",
            spacing="5"
        )
    )
