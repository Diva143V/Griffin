import reflex as rx

def reports():
    reports_list = [
        ("Metformin Oncology Study", "2026-07-01", "PDF", "92%"),
        ("AMPK Activation pathways review", "2026-06-15", "DOCX", "85%"),
        ("In-vitro cellular survival patterns", "2026-05-20", "PDF", "95%")
    ]
    return rx.box(
        rx.vstack(
            rx.heading("Scientific Reports Library", size="5"),
            rx.text("Compiled LaTeX/PDF research summaries and reviews.", size="2", color="gray"),
            *[
                rx.hstack(
                    rx.vstack(
                        rx.text(title, weight="bold", size="3"),
                        rx.text(f"Created: {date} | Format: {fmt}", size="2", color="gray"),
                        spacing="1"
                    ),
                    rx.spacer(),
                    rx.badge(f"Score {score}", color_scheme="indigo"),
                    width="100%",
                    align_items="center"
                )
                for title, date, fmt, score in reports_list
            ],
            spacing="4",
            width="100%"
        ),
        padding="20px",
        border_radius="18px",
        background="rgba(17,24,39,0.75)",
        border="1px solid rgba(255,255,255,0.08)",
        width="100%"
    )
