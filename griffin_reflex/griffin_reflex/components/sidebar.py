import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS, glow_effect
from griffin_reflex.components.sidebar_state import SidebarState

# Premium Navigation Menu with Section Groups
MENU_SECTIONS = {
    "Main": [
        ("🏠", "Dashboard", "/dashboard"),
        ("🧭", "Planner", "/"),
        ("🧬", "Workspace", "/workspace"),
    ],
    "Research": [
        ("🧪", "Labs", "/projects"),
    ],
    "System": [
        ("⚙️", "Settings", "/settings"),
    ]
}

def nav_item(icon: str, name: str, path: str, active: str):
    """Premium navigation item with hover lifts and glowing active states"""
    is_active = path == active
    
    active_style = {
        "background": f"linear-gradient(135deg, {COLORS['primary']}25, {COLORS['secondary']}18)",
        "border": f"1px solid {COLORS['primary']}",
        "boxShadow": f"0 0 20px {COLORS['primary_glow']}",
        "color": COLORS["text_primary"],
        "position": "relative",
    }
    
    inactive_style = {
        "background": "transparent",
        "border": f"1px solid transparent",
        "color": COLORS["text_secondary"],
        "_hover": {
            "background": f"{COLORS['surface_light']}",
            "border": f"1px solid {COLORS['border_highlight']}",
            "color": COLORS["text_primary"],
            "transform": "translateX(4px)",
        }
    }
    
    # Left vertical indicator bar for active item
    indicator = rx.cond(
        is_active,
        rx.box(
            position="absolute",
            left="0",
            top="25%",
            height="50%",
            width="4px",
            background=COLORS["accent"],
            border_radius="0 4px 4px 0",
            style={"boxShadow": f"0 0 10px {COLORS['accent']}"}
        ),
        rx.fragment()
    )

    item_content = rx.cond(
        SidebarState.is_collapsed,
        # Collapsed: Show only icon with a premium tooltip
        rx.tooltip(
            rx.center(
                rx.text(icon, font_size="20px", style={"filter": f"drop-shadow(0 0 4px {COLORS['primary']}40)" if is_active else "none"}),
                width="100%",
                padding="12px",
            ),
            content=name,
            delay_duration=0,
        ),
        # Expanded: Show icon + text label
        rx.hstack(
            rx.text(icon, font_size="20px", style={"filter": f"drop-shadow(0 0 6px {COLORS['primary']})" if is_active else "none"}),
            rx.text(name, font_family=FONTS["body"], font_weight="500", font_size="15px"),
            spacing="3",
            align_items="center",
            padding="12px 16px",
        )
    )
    
    return rx.link(
        rx.box(
            indicator,
            item_content,
            width="100%",
            style=active_style if is_active else inactive_style,
            border_radius="14px",
            transition="all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            cursor="pointer",
        ),
        href=path,
        width="100%",
        text_decoration="none",
    )

def section_header(title: str):
    """Premium section header hidden or simplified when collapsed"""
    return rx.cond(
        SidebarState.is_collapsed,
        rx.box(
            height="1px",
            width="100%",
            background=f"linear-gradient(90deg, transparent, {COLORS['border_highlight']}, transparent)",
            margin_y="4",
        ),
        rx.text(
            title,
            size="1",
            color=COLORS["text_secondary"],
            font_family=FONTS["body"],
            font_weight="700",
            letter_spacing="0.12em",
            text_transform="uppercase",
            padding_top="5",
            padding_bottom="2",
            style={"opacity": 0.8}
        )
    )

def pipeline_indicator():
    """Collapsible state status indicator"""
    return rx.cond(
        SidebarState.is_collapsed,
        # Collapsed indicator dot with tooltip
        rx.tooltip(
            rx.center(
                rx.box(
                    width="12px",
                    height="12px",
                    border_radius="50%",
                    background=COLORS["success"],
                    animation="pulse 2s infinite",
                    style={
                        "boxShadow": f"0 0 15px {COLORS['success']}",
                    }
                ),
                padding="8px",
            ),
            content="Pipeline Ready - Planner is active",
            delay_duration=0,
        ),
        # Expanded indicator box
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        width="8px",
                        height="8px",
                        border_radius="50%",
                        background=COLORS["success"],
                        animation="pulse 2s infinite",
                        style={
                            "boxShadow": f"0 0 12px {COLORS['success_glow']}",
                        }
                    ),
                    rx.text(
                        "Pipeline Active",
                        size="2",
                        color=COLORS["success"],
                        font_family=FONTS["body"],
                        font_weight="600",
                    ),
                    spacing="2",
                    align_items="center",
                ),
                rx.text(
                    "Planner triggers agents. Dashboard & Workspace sync database on disk.",
                    size="1",
                    color=COLORS["text_secondary"],
                    font_family=FONTS["body"],
                    line_height="1.4",
                ),
                spacing="2",
                align_items="flex-start",
            ),
            padding="16px",
            border_radius="18px",
            background=f"rgba(16,185,129,0.06)",
            border=f"1px solid {COLORS['success']}25",
            width="100%",
            style={"backdropFilter": "blur(8px)"}
        )
    )

def workspace_selector():
    """Workspace selector for choosing the active run subdirectory"""
    from griffin_reflex.griffin_reflex import State
    
    return rx.cond(
        SidebarState.is_collapsed,
        rx.tooltip(
            rx.center(
                rx.text("📂", font_size="20px"),
                padding="8px",
            ),
            content="Active workspace folder",
            delay_duration=0,
        ),
        rx.vstack(
            rx.text(
                "📂 Workspace Run",
                size="1",
                color=COLORS["text_secondary"],
                font_family=FONTS["body"],
                font_weight="700",
                letter_spacing="0.12em",
                text_transform="uppercase",
                padding_top="2",
            ),
            rx.select(
                State.available_runs,
                placeholder="Main Workspace",
                value=State.selected_run,
                on_change=State.set_selected_run_action,
                style={
                    "background": COLORS["surface"],
                    "color": COLORS["text_primary"],
                    "border": f"1px solid {COLORS['border_highlight']}",
                    "borderRadius": "8px",
                    "width": "100%",
                }
            ),
            width="100%",
            spacing="1",
            padding_bottom="2",
        )
    )

def sidebar(active: str = ""):
    """Collapsible navigation sidebar with custom interactive trigger"""
    return rx.box(
        rx.vstack(
            # Header block containing logo, brand name, and chevron toggle
            rx.hstack(
                rx.hstack(
                    rx.text(
                        "🧬",
                        font_size="32px",
                        style={"filter": f"drop-shadow(0 0 12px {COLORS['primary_glow']})"}
                    ),
                    rx.cond(
                        ~SidebarState.is_collapsed,
                        rx.vstack(
                            rx.heading(
                                "Griffin AI",
                                size="4",
                                color=COLORS["text_primary"],
                                font_family=FONTS["heading"],
                                style={"letterSpacing": "-0.03em"}
                            ),
                            rx.text(
                                "Scientific Intelligence",
                                size="1",
                                color=COLORS["text_secondary"],
                                font_family=FONTS["body"],
                            ),
                            spacing="0",
                            align_items="flex-start",
                        ),
                    ),
                    spacing="3",
                    align_items="center",
                ),
                rx.spacer(),
                # Toggle collapse action button
                rx.button(
                    rx.cond(
                        SidebarState.is_collapsed,
                        rx.icon(tag="chevron-right", size=18, color=COLORS["text_primary"]),
                        rx.icon(tag="chevron-left", size=18, color=COLORS["text_primary"])
                    ),
                    on_click=SidebarState.toggle_collapse,
                    size="1",
                    variant="ghost",
                    style={
                        "borderRadius": "50%",
                        "background": "rgba(255, 255, 255, 0.03)",
                        "border": f"1px solid {COLORS['border_highlight']}",
                        "padding": "4px",
                        "cursor": "pointer",
                        "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                        "_hover": {
                            "background": "rgba(255,255,255,0.08)",
                            "transform": "scale(1.1)",
                        }
                    }
                ),
                width="100%",
                align_items="center",
                padding_bottom="2",
            ),
            
            # Ambient line separation
            rx.box(
                height="1px",
                width="100%",
                background=f"linear-gradient(90deg, {COLORS['border_highlight']}, transparent)",
                margin_y="2",
            ),
            
            # Nav list grouping
            rx.vstack(
                *[
                    rx.vstack(
                        section_header(sec_title),
                        rx.vstack(
                            *[
                                nav_item(icon, name, path, active)
                                for icon, name, path in items
                            ],
                            spacing="2",
                            width="100%",
                        ),
                        spacing="1",
                        width="100%",
                    )
                    for sec_title, items in MENU_SECTIONS.items()
                ],
                spacing="3",
                width="100%",
            ),
            
            rx.spacer(),
            
            # Pipeline and footer indicators
            workspace_selector(),
            pipeline_indicator(),
            
            rx.cond(
                ~SidebarState.is_collapsed,
                rx.box(
                    rx.text(
                        "v2.0 • Premium Edition",
                        size="1",
                        color=COLORS["text_muted"],
                        font_family=FONTS["mono"],
                    ),
                    padding_top="4",
                    text_align="center",
                ),
            ),
            
            height="100%",
            width="100%",
            spacing="4",
        ),
        width=rx.cond(SidebarState.is_collapsed, "88px", "280px"),
        min_width=rx.cond(SidebarState.is_collapsed, "88px", "280px"),
        height="100vh",
        padding="24px 16px",
        background=f"linear-gradient(180deg, {COLORS['background']} 0%, rgba(5,8,22,0.99) 100%)",
        border_right=f"1px solid {COLORS['border_highlight']}",
        style={
            "boxShadow": f"4px 0 24px rgba(0,0,0,0.45)",
            "position": "sticky",
            "top": "0",
            "transition": "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
            "zIndex": "100",
        }
    )
