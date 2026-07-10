import reflex as rx

COLORS = {
    "background": "#050816",
    "surface": "rgba(15,23,42,0.75)",
    "border": "rgba(255,255,255,0.1)",
    "primary": "#6366f1",
    "success": "#22c55e"
}

def glass():
    return {
        "background": COLORS["surface"],
        "backdropFilter": "blur(25px)",
        "border": f"1px solid {COLORS['border']}",
    }
