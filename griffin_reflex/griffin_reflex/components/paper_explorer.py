import reflex as rx

PAPERS = [
    {
        "title": "Metformin and Breast Cancer Survival",
        "journal": "Nature Medicine",
        "year": 2024,
        "score": 9
    },
    {
        "title": "AMPK activation pathways",
        "journal": "Cell",
        "year": 2023,
        "score": 8
    }
]

def paper_card(p):
    return rx.box(
        rx.vstack(
            rx.heading(
                p["title"],
                size="4"
            ),
            rx.text(
                p["journal"]
            ),
            rx.hstack(
                rx.badge(
                    str(p["year"])
                ),
                rx.badge(
                    f"Evidence {p['score']}/10"
                )
            ),
            rx.button(
                "Open Analysis"
            )
        ),
        padding="25px",
        border_radius="20px",
        background="rgba(15,23,42,0.8)"
    )

def paper_explorer():
    return rx.vstack(
        rx.heading(
            "Scientific Literature Explorer",
            size="7"
        ),
        rx.input(
            placeholder="Search papers..."
        ),
        rx.grid(
            *[
                paper_card(p)
                for p in PAPERS
            ],
            columns="3",
            spacing="5"
        )
    )
