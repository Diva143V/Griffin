import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS
from griffin_reflex.components.ui import section_header, premium_card, input_field

def paper_card(p):
    """Premium state-driven paper card with hover lifts and neon border highlights"""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(p["title"], size="4", font_family=FONTS["heading"], color=COLORS["text_primary"]),
                rx.spacer(),
                rx.box(
                    width="10px",
                    height="10px",
                    border_radius="50%",
                    background=COLORS["accent"],
                    style={"boxShadow": f"0 0 10px {COLORS['accent']}"}
                ),
                width="100%",
                align_items="flex-start",
            ),
            rx.text(p["source"], size="2", color=COLORS["text_secondary"], font_family=FONTS["body"], font_weight="500"),
            
            # Metadata Tags
            rx.hstack(
                rx.badge(
                    rx.hstack(
                        rx.icon(tag="calendar", size=12),
                        rx.text(p["year"]),
                        spacing="1",
                    ),
                    size="1",
                    variant="soft",
                    style={
                        "background": f"{COLORS['accent']}15",
                        "border": f"1px solid {COLORS['accent']}40",
                        "color": COLORS["accent"],
                        "fontFamily": FONTS["mono"],
                        "padding": "2px 8px",
                    }
                ),
                rx.badge(
                    rx.hstack(
                        rx.icon(tag="check", size=12),
                        rx.text(f"Evidence {p['score']}/10"),
                        spacing="1",
                    ),
                    size="1",
                    variant="soft",
                    style={
                        "background": f"{COLORS['primary']}15",
                        "border": f"1px solid {COLORS['primary']}40",
                        "color": COLORS["primary"],
                        "fontFamily": FONTS["mono"],
                        "padding": "2px 8px",
                    }
                ),
                spacing="2",
            ),
            
            # Abstract snippet text
            rx.cond(
                p["abstract"] != "",
                rx.text(
                    p["abstract"],
                    size="1",
                    color=COLORS["text_secondary"],
                    font_family=FONTS["body"],
                    line_height="1.6",
                    style={"opacity": 0.85}
                ),
            ),
            
            # Action Link Button
            rx.link(
                rx.button(
                    rx.hstack(
                        rx.text("Open Source Analysis"),
                        rx.icon(tag="external-link", size=14),
                        spacing="2",
                    ),
                    size="2",
                    variant="ghost",
                    style={
                        "border": f"1px solid {COLORS['border_highlight']}",
                        "color": COLORS["text_primary"],
                        "borderRadius": "8px",
                        "cursor": "pointer",
                        "transition": "all 0.25s ease",
                        "_hover": {
                            "borderColor": COLORS["primary"],
                            "background": f"{COLORS['primary']}12",
                            "color": "white",
                        }
                    }
                ),
                href=p["url"],
                is_external=True,
                text_decoration="none",
            ),
            spacing="4",
            width="100%",
            align_items="flex-start",
        ),
        padding="26px",
        border_radius="24px",
        background=f"rgba(15, 23, 42, 0.45)",
        border=f"1px solid {COLORS['border']}",
        width="100%",
        style={
            "backdropFilter": "blur(16px)",
            "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
            "_hover": {
                "transform": "translateY(-6px)",
                "borderColor": COLORS["border_highlight"],
                "boxShadow": f"0 15px 35px -5px {COLORS['primary_glow']}, 0 10px 24px rgba(0, 0, 0, 0.4)",
                "background": "rgba(20, 30, 55, 0.5)",
            }
        }
    )

def paper_explorer():
    """Premium main State paper explorer (Planner page)"""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        section_header(
            "Scientific Literature Explorer",
            "Search and analyze ranked scientific publications retrieved in your dataset.",
        ),
        input_field(
            "Search papers by keyword, phrase, title or abstract text...",
            State.paper_search_query,
            State.set_paper_search_query,
        ),
        rx.grid(
            rx.foreach(State.filtered_ranked_papers, paper_card),
            columns="3",
            spacing="5",
            width="100%",
        ),
        spacing="6",
        width="100%",
    )

def paper_explorer_view(papers_var, search_var, on_search, on_refresh):
    """Premium workspace paper explorer driven by data_layer / WorkspaceState"""
    return rx.vstack(
        section_header(
            "Scientific Literature Explorer",
            "Curated papers compiled from local clean and ranked CSV metrics.",
            action=rx.button(
                rx.hstack(
                    rx.icon(tag="rotate-cw", size=16),
                    rx.text("Refresh Index"),
                    spacing="2",
                ),
                on_click=on_refresh,
                size="3",
                style={
                    "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                    "boxShadow": f"0 4px 15px {COLORS['primary_glow']}",
                    "border": "none",
                    "color": "white",
                    "borderRadius": "12px",
                    "padding": "0 22px",
                    "minHeight": "40px",
                    "cursor": "pointer",
                    "transition": "all 0.3s ease",
                    "_hover": {
                        "transform": "translateY(-2px)",
                        "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                    }
                }
            )
        ),
        input_field(
            "Search papers by keyword, phrase, title or abstract text...",
            search_var,
            on_search,
        ),
        rx.cond(
            papers_var.length() == 0,
            premium_card(
                rx.vstack(
                    rx.text(
                        "No paper indexing files found. Run the planner query to start ingestion pipelines.",
                        color=COLORS["text_secondary"],
                        font_family=FONTS["body"],
                        size="3",
                        text_align="center",
                    ),
                    spacing="2",
                    align_items="center",
                    width="100%",
                ),
                variant="default"
            ),
            rx.grid(
                rx.foreach(papers_var, paper_card),
                columns="2",
                spacing="4",
                width="100%",
            ),
        ),
        spacing="6",
        width="100%",
    )
