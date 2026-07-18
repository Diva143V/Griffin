import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS, glass_card, gradient_background, glow_effect

# Typography bindings
FONT_HEADING = FONTS["heading"]
FONT_BODY = FONTS["body"]
FONT_MONO = FONTS["mono"]

PAGE_BG = gradient_background()

def premium_card(content, variant: str = "default", **kwargs):
    """Sleek glassmorphic card with advanced shadow mapping and smooth hover animations"""
    variants = {
        "default": {
            "background": "rgba(10, 15, 30, 0.55)",
            "backdropFilter": "blur(20px)",
            "-webkit-backdrop-filter": "blur(20px)",
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "24px",
            "padding": "28px",
            "boxShadow": "0 12px 30px -10px rgba(0, 0, 0, 0.5)",
            "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "transform": "translateY(-4px)",
                "boxShadow": f"0 20px 40px -12px {COLORS['primary_glow']}",
                "borderColor": COLORS["border_highlight"],
            }
        },
        "accent": {
            "background": f"linear-gradient(145deg, rgba(99, 102, 241, 0.08) 0%, rgba(6, 182, 212, 0.03) 100%)",
            "backdropFilter": "blur(20px)",
            "-webkit-backdrop-filter": "blur(20px)",
            "border": f"1px solid {COLORS['primary']}40",
            "borderRadius": "24px",
            "padding": "28px",
            "boxShadow": f"0 8px 30px -5px {COLORS['primary_glow']}15",
            "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "transform": "translateY(-4px)",
                "boxShadow": f"0 20px 40px -10px {COLORS['primary_glow']}",
                "borderColor": COLORS["primary"],
            }
        },
        "glass": {
            "background": "rgba(20, 30, 55, 0.45)",
            "backdropFilter": "blur(28px)",
            "-webkit-backdrop-filter": "blur(28px)",
            "border": f"1px solid {COLORS['border_highlight']}",
            "borderRadius": "28px",
            "padding": "32px",
            "boxShadow": "0 12px 32px rgba(0, 0, 0, 0.4)",
            "transition": "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "transform": "translateY(-4px)",
                "borderColor": COLORS["primary"],
                "boxShadow": f"0 20px 45px {COLORS['primary_glow']}20",
            }
        }
    }
    
    style = variants.get(variant, variants["default"])
    extra = kwargs.pop("style", None)
    if extra:
        style.update(extra)
    
    return rx.box(content, style=style, **kwargs)

def metric(title, value, icon, color: str = "primary", trend: str = None):
    """High-end statistic grid block with floating icon drops and ambient shadow glows"""
    color_map = {
        "primary": COLORS["primary"],
        "accent": COLORS["accent"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
    }
    metric_color = color_map.get(color, COLORS["primary"])
    
    return premium_card(
        rx.vstack(
            rx.hstack(
                rx.center(
                    rx.text(icon, font_size="22px"),
                    width="44px",
                    height="44px",
                    border_radius="12px",
                    background=f"{metric_color}18",
                    border=f"1px solid {metric_color}35",
                    style={"boxShadow": f"0 0 15px {metric_color}25"}
                ),
                rx.spacer(),
                rx.cond(
                    trend is not None,
                    rx.badge(
                        f"{trend}",
                        color_scheme="green",
                        variant="soft",
                        size="1",
                        radius="full",
                        style={"padding": "2px 8px"}
                    )
                ),
                width="100%",
                align_items="center",
            ),
            rx.text(title, color=COLORS["text_secondary"], size="2", font_family=FONT_BODY, font_weight="500"),
            rx.heading(
                value, 
                size="8", 
                color=COLORS["text_primary"],
                font_family=FONT_HEADING,
                style={
                    "textShadow": f"0 0 20px {metric_color}25",
                    "letterSpacing": "-0.02em"
                }
            ),
            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        variant="default"
    )

def status_badge(status, text=None):
    """Neon status badge with translucent glows"""
    status_colors = {
        "active": COLORS["success"],
        "running": COLORS["accent"],
        "idle": COLORS["text_muted"],
        "error": COLORS["error"],
        "warning": COLORS["warning"],
    }
    
    color = status_colors.get(status.lower(), COLORS["text_muted"])
    display_text = text or status.upper()
    
    return rx.badge(
        rx.hstack(
            rx.box(
                width="6px",
                height="6px",
                border_radius="50%",
                background=color,
                style={"boxShadow": f"0 0 8px {color}"}
            ),
            rx.text(display_text, font_weight="600"),
            spacing="2",
            align_items="center",
        ),
        variant="soft",
        size="2",
        style={
            "background": f"{color}12",
            "border": f"1px solid {color}30",
            "color": color,
            "boxShadow": f"0 0 10px {color}15",
            "fontFamily": FONT_BODY,
            "padding": "4px 10px",
            "borderRadius": "999px",
        }
    )

def terminal_box(content, height: str = "400px"):
    """IDE-like console box styling wrapper (maintained for backward fallback compat)"""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.box(width="10px", height="10px", borderRadius="50%", background="#ef4444"),
                    rx.box(width="10px", height="10px", borderRadius="50%", background="#f59e0b"),
                    rx.box(width="10px", height="10px", borderRadius="50%", background="#10b981"),
                    spacing="2",
                ),
                rx.text("TERMINAL CONSOLE", size="1", color=COLORS["text_secondary"], font_family=FONT_MONO),
                rx.spacer(),
                spacing="3",
                width="100%",
                align_items="center",
                padding="3",
                border_bottom=f"1px solid {COLORS['border']}",
            ),
            rx.box(
                content,
                font_family=FONT_MONO,
                font_size="13px",
                color=COLORS["text_primary"],
                overflow="auto",
                width="100%",
                height=f"calc({height} - 46px)",
                padding="4",
                style={
                    "lineHeight": "1.6",
                    "background": "rgba(0,0,0,0.3)",
                }
            ),
            spacing="0",
            width="100%",
        ),
        height=height,
        background="rgba(5,8,22,0.85)",
        border=f"1px solid {COLORS['border_highlight']}",
        border_radius="18px",
        style={
            "boxShadow": f"0 12px 35px rgba(0,0,0,0.6)",
            "overflow": "hidden",
            "backdropFilter": "blur(20px)",
        }
    )

def input_field(placeholder, value, on_change, **kwargs):
    """Modern glowing text input field"""
    return rx.input(
        placeholder=placeholder,
        value=value,
        on_change=on_change,
        size="3",
        style={
            "background": "rgba(10, 15, 30, 0.7)",
            "border": f"1px solid {COLORS['border_highlight']}",
            "borderRadius": "14px",
            "color": COLORS["text_primary"],
            "fontFamily": FONT_BODY,
            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            "padding": "12px 16px",
            "_focus": {
                "borderColor": COLORS["primary"],
                "boxShadow": f"0 0 15px {COLORS['primary_glow']}",
                "outline": "none",
            }
        },
        **kwargs
    )

def page_shell(sidebar_comp, body, bg: str = PAGE_BG):
    """Premium shell architecture wrapper supporting collapsible navigations"""
    return rx.hstack(
        sidebar_comp,
        rx.box(
            body,
            padding="48px",
            width="100%",
            height="100vh",
            overflow="auto",
            style={
                "scrollbarWidth": "thin",
                "scrollbarColor": f"{COLORS['border_highlight']} transparent",
                "transition": "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
            }
        ),
        width="100vw",
        spacing="0",
        background=bg,
        style={
            "minHeight": "100vh",
            "overflow": "hidden",
        },
    )

def section_header(title, subtitle=None, action=None):
    """Premium heading display with optional command call buttons"""
    return rx.hstack(
        rx.vstack(
            rx.heading(
                title, 
                size="8", 
                color=COLORS["text_primary"],
                font_family=FONT_HEADING,
                style={
                    "letterSpacing": "-0.03em",
                    "fontWeight": "700"
                }
            ),
            rx.cond(
                subtitle is not None,
                rx.text(
                    subtitle, 
                    color=COLORS["text_secondary"], 
                    size="3",
                    font_family=FONT_BODY,
                    style={"opacity": 0.9}
                )
            ),
            spacing="1",
            align_items="flex-start",
        ),
        rx.spacer(),
        rx.cond(
            action is not None,
            action,
            rx.fragment()
        ),
        width="100%",
        align_items="center",
        padding_bottom="6",
    )

def divider(spacing: str = "8"):
    """Fading linear layout divider"""
    return rx.box(
        height="1px",
        width="100%",
        background=f"linear-gradient(90deg, transparent, {COLORS['border_highlight']}, transparent)",
        margin_y=spacing,
    )
