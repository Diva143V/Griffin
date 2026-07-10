import reflex as rx


def paper_card(p):
    """State-driven paper card (dict Var) — supports main State and workspace rows."""
    return rx.box(
        rx.vstack(
            rx.heading(p["title"], size="4"),
            rx.text(p["source"], size="2", color="gray"),
            rx.hstack(
                rx.badge(p["year"]),
                rx.badge("Evidence " + p["score"] + "/10", color_scheme="indigo"),
                spacing="2",
            ),
            rx.cond(
                p["abstract"] != "",
                rx.text(p["abstract"], size="1", color="gray"),
            ),
            rx.link(
                rx.button("Open Analysis", size="1", variant="soft"),
                href=p["url"],
            ),
            spacing="2",
            width="100%",
        ),
        padding="25px",
        border_radius="20px",
        background="rgba(15,23,42,0.8)",
        border="1px solid rgba(255,255,255,0.08)",
        width="100%",
        margin_bottom="3",
    )


def paper_explorer():
    """Main State paper explorer (ranked papers + search)."""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        rx.heading("Scientific Literature Explorer", size="7"),
        rx.input(
            placeholder="Search papers...",
            on_change=State.set_paper_search_query,
            width="100%",
            size="3",
        ),
        rx.grid(
            rx.foreach(State.filtered_ranked_papers, paper_card),
            columns="3",
            spacing="5",
            width="100%",
        ),
        spacing="5",
        width="100%",
    )


def paper_explorer_view(papers_var, search_var, on_search, on_refresh):
    """Workspace paper explorer driven by data_layer / WorkspaceState."""
    return rx.vstack(
        rx.heading("Scientific Literature Explorer", size="7"),
        rx.text("Papers from ranked / clean dataset CSVs.", color="gray", size="2"),
        rx.hstack(
            rx.input(
                placeholder="Search papers...",
                value=search_var,
                on_change=on_search,
                width="100%",
                size="3",
            ),
            rx.button("Refresh", on_click=on_refresh, color_scheme="indigo"),
            width="100%",
            spacing="3",
        ),
        rx.cond(
            papers_var.length() == 0,
            rx.box(
                rx.text(
                    "No papers found. Run the Planner to collect and rank literature.",
                    color="gray",
                ),
                padding="20px",
                border_radius="15px",
                background="rgba(255,255,255,0.04)",
                width="100%",
            ),
            rx.grid(
                rx.foreach(papers_var, paper_card),
                columns="2",
                spacing="4",
                width="100%",
            ),
        ),
        spacing="5",
        width="100%",
    )
