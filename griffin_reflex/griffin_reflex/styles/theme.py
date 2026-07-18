import reflex as rx

# Premium State-of-the-Art Color Palette
COLORS = {
    "background": "#050816",
    "surface": "rgba(10, 15, 30, 0.7)",
    "surface_light": "rgba(20, 30, 55, 0.55)",
    "border": "rgba(99, 102, 241, 0.08)",
    "border_highlight": "rgba(99, 102, 241, 0.18)",
    "primary": "#6366f1",         # Neon Indigo
    "primary_glow": "rgba(99, 102, 241, 0.35)",
    "secondary": "#8b5cf6",       # Electric Violet
    "secondary_glow": "rgba(139, 92, 246, 0.3)",
    "accent": "#06b6d4",          # Radiant Cyan
    "accent_glow": "rgba(6, 182, 212, 0.35)",
    "success": "#10b981",         # Emerald Green
    "success_glow": "rgba(16, 185, 129, 0.3)",
    "warning": "#f59e0b",         # Clean Amber
    "warning_glow": "rgba(245, 158, 11, 0.3)",
    "error": "#ef4444",           # Rose Red
    "error_glow": "rgba(239, 68, 68, 0.3)",
    "text_primary": "#f8fafc",     # Soft White
    "text_secondary": "#94a3b8",   # Cool Grey
    "text_muted": "#475569",       # Dark Muted Slate
}

# Modern Typography Pairing
FONTS = {
    "heading": "'Outfit', system-ui, -apple-system, sans-serif",
    "body": "'DM Sans', system-ui, -apple-system, sans-serif",
    "mono": "'JetBrains Mono', 'Fira Code', monospace",
}

# Premium Glassmorphism Effect Helper
def glass(intensity: str = "medium"):
    """Enhanced glass effect with varying backdrop blurs and subtle borders"""
    intensities = {
        "light": {
            "background": "rgba(15, 23, 42, 0.35)",
            "backdropFilter": "blur(12px)",
            "-webkit-backdrop-filter": "blur(12px)",
            "border": f"1px solid {COLORS['border']}",
        },
        "medium": {
            "background": "rgba(10, 15, 30, 0.65)",
            "backdropFilter": "blur(20px)",
            "-webkit-backdrop-filter": "blur(20px)",
            "border": f"1px solid {COLORS['border_highlight']}",
        },
        "heavy": {
            "background": "rgba(5, 8, 22, 0.88)",
            "backdropFilter": "blur(32px)",
            "-webkit-backdrop-filter": "blur(32px)",
            "border": f"1px solid rgba(255, 255, 255, 0.12)",
        },
    }
    return intensities.get(intensity, intensities["medium"])

def glass_card(style_intensity: str = "medium"):
    """Complete premium glass card styling with high-end shadows and transitions"""
    base = glass(style_intensity)
    return {
        **base,
        "borderRadius": "24px",
        "boxShadow": "0 12px 40px -10px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.05)",
        "transition": "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
    }

def premium_button(variant: str = "primary"):
    """State-of-the-art interactive button styles with hover lifting and glow indicators"""
    variants = {
        "primary": {
            "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
            "boxShadow": f"0 4px 20px -2px {COLORS['primary_glow']}",
            "border": "none",
            "color": "white",
            "borderRadius": "12px",
            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "transform": "translateY(-2px)",
                "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                "filter": "brightness(1.1)",
            },
            "_active": {
                "transform": "translateY(0) scale(0.98)",
            }
        },
        "accent": {
            "background": f"linear-gradient(135deg, {COLORS['accent']}, {COLORS['primary']})",
            "boxShadow": f"0 4px 20px -2px {COLORS['accent_glow']}",
            "border": "none",
            "color": "white",
            "borderRadius": "12px",
            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "transform": "translateY(-2px)",
                "boxShadow": f"0 8px 25px {COLORS['accent_glow']}",
                "filter": "brightness(1.1)",
            },
            "_active": {
                "transform": "translateY(0) scale(0.98)",
            }
        },
        "ghost": {
            "background": "transparent",
            "border": f"1px solid {COLORS['border_highlight']}",
            "color": COLORS["text_primary"],
            "borderRadius": "12px",
            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "background": "rgba(99, 102, 241, 0.08)",
                "borderColor": COLORS["primary"],
                "color": "white",
            }
        },
        "glass": {
            "background": "rgba(99, 102, 241, 0.12)",
            "border": f"1px solid {COLORS['primary']}40",
            "color": COLORS["text_primary"],
            "borderRadius": "12px",
            "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            "_hover": {
                "background": "rgba(99, 102, 241, 0.2)",
                "borderColor": COLORS["primary"],
                "boxShadow": f"0 0 15px {COLORS['primary_glow']}",
            }
        },
    }
    return variants.get(variant, variants["primary"])

def status_color(status: str):
    """Refined status color palette helper"""
    colors = {
        "active": COLORS["success"],
        "idle": COLORS["text_muted"],
        "running": COLORS["accent"],
        "error": COLORS["error"],
        "warning": COLORS["warning"],
        "success": COLORS["success"],
    }
    return colors.get(status.lower(), COLORS["text_muted"])

def gradient_background():
    """Nebula space style ambient background with high contrast gradients"""
    return """
radial-gradient(circle at 10% 15%, rgba(99, 102, 241, 0.12) 0%, transparent 45%),
radial-gradient(circle at 85% 80%, rgba(6, 182, 212, 0.08) 0%, transparent 40%),
radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.05) 0%, transparent 50%),
linear-gradient(180deg, #050816 0%, #070c24 100%)
"""

def glow_effect(color: str = "primary", intensity: str = "medium"):
    """Helper to generate consistent premium drop shadows and glow filters"""
    glows = {
        "primary": COLORS["primary_glow"],
        "accent": COLORS["accent_glow"],
        "success": COLORS["success_glow"],
        "warning": COLORS["warning_glow"],
        "error": COLORS["error_glow"],
        "secondary": COLORS["secondary_glow"],
    }
    intensities = {
        "subtle": "0 0 12px",
        "medium": "0 0 24px",
        "strong": "0 0 36px",
    }
    return f"{intensities.get(intensity, '0 0 24px')} {glows.get(color, COLORS['primary_glow'])}"
