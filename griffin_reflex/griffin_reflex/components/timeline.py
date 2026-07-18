import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS

def timeline_event_card(event, index: int, is_last: bool = False):
    """Premium chronological timeline card with modern dot-and-line layout"""
    return rx.hstack(
        # Glowing vertical line and dot connection
        rx.vstack(
            rx.box(
                # Inner solid indigo core with outer glowing cyan circle
                rx.box(
                    width="10px",
                    height="10px",
                    border_radius="50%",
                    background=COLORS["primary"],
                ),
                width="22px",
                height="22px",
                border_radius="50%",
                border=f"2px solid {COLORS['accent']}",
                background="transparent",
                display="flex",
                align_items="center",
                justify_content="center",
                style={
                    "boxShadow": f"0 0 15px {COLORS['accent_glow']}",
                    "zIndex": "2",
                }
            ),
            rx.cond(
                ~is_last,
                rx.box(
                    width="2px",
                    height="100%",
                    background=f"linear-gradient(180deg, {COLORS['accent']}, {COLORS['primary']} 40%, transparent 100%)",
                    margin_top="4px",
                    style={"opacity": 0.85}
                )
            ),
            spacing="1",
            align_items="center",
            min_width="50px",
        ),
        
        # Chronological Event Box Card
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.badge(
                        event["year"],
                        size="2",
                        variant="soft",
                        style={
                            "background": f"linear-gradient(135deg, {COLORS['accent']}20, {COLORS['primary']}15)",
                            "border": f"1px solid {COLORS['accent']}40",
                            "color": COLORS["accent"],
                            "fontFamily": FONTS["mono"],
                            "fontWeight": "700",
                            "letterSpacing": "0.05em",
                            "boxShadow": f"0 0 10px {COLORS['accent_glow']}20",
                        }
                    ),
                    rx.spacer(),
                ),
                rx.text(
                    event["text"],  # Use event["text"] since data_layer.py returns it!
                    size="3",
                    color=COLORS["text_primary"],
                    font_family=FONTS["body"],
                    line_height="1.6",
                ),
                spacing="3",
                align_items="flex-start",
                width="100%",
            ),
            padding="24px",
            border_radius="20px",
            background=f"rgba(15, 23, 42, 0.45)",
            border=f"1px solid {COLORS['border']}",
            border_left=f"4px solid {COLORS['primary']}",
            style={
                "backdropFilter": "blur(16px)",
                "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
                "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
                "_hover": {
                    "borderColor": COLORS["border_highlight"],
                    "transform": "translateY(-4px)",
                    "boxShadow": f"0 12px 35px -5px {COLORS['primary_glow']}, 0 10px 24px rgba(0, 0, 0, 0.4)",
                    "background": "rgba(20, 30, 55, 0.5)",
                }
            },
            flex="1",
        ),
        
        spacing="2",
        align_items="flex-start",
        width="100%",
        margin_bottom="4",
    )

def research_timeline():
    """Premium main State timeline (Planner)"""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        rx.vstack(
            rx.heading("Research Evolution Timeline", size="6", style={"fontFamily": FONTS["heading"], "color": COLORS["text_primary"]}),
            rx.text("Chronological view of scientific discoveries and papers", size="2", color=COLORS["text_secondary"]),
            spacing="1",
            align_items="flex-start",
            margin_bottom="4",
        ),
        rx.cond(
            State.timeline_events.length() == 0,
            rx.box(
                rx.center(
                    rx.text("No timeline data yet.", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                    width="100%",
                    padding="32px",
                ),
                border_radius="20px",
                border=f"1px solid {COLORS['border']}",
                background="rgba(15, 23, 42, 0.4)",
                width="100%",
            ),
            rx.vstack(
                rx.foreach(
                    State.timeline_events,
                    lambda event, index: timeline_event_card(
                        event,
                        index,
                        is_last=(index == State.timeline_events.length() - 1)
                    ),
                ),
                spacing="0",
                width="100%",
                padding_left="2",
            ),
        ),
        spacing="4",
        width="100%",
    )

def research_timeline_view(events_var):
    """Premium workspace timeline driven by data_layer / WorkspaceState"""
    return rx.vstack(
        rx.vstack(
            rx.heading("Research Evolution Timeline", size="6", style={"fontFamily": FONTS["heading"], "color": COLORS["text_primary"]}),
            rx.text("Chronological view of scientific discoveries and papers", size="2", color=COLORS["text_secondary"]),
            spacing="1",
            align_items="flex-start",
            margin_bottom="4",
        ),
        rx.cond(
            events_var.length() == 0,
            rx.box(
                rx.center(
                    rx.text("No timeline data yet.", color=COLORS["text_secondary"], font_family=FONTS["body"]),
                    width="100%",
                    padding="32px",
                ),
                border_radius="20px",
                border=f"1px solid {COLORS['border']}",
                background="rgba(15, 23, 42, 0.4)",
                width="100%",
            ),
            rx.vstack(
                rx.foreach(
                    events_var,
                    lambda e, index: timeline_event_card(
                        e,
                        index,
                        is_last=(index == events_var.length() - 1)
                    ),
                ),
                spacing="0",
                width="100%",
                padding_left="2",
            ),
        ),
        spacing="4",
        width="100%",
    )
