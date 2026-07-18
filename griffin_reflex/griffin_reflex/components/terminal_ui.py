import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS

# Unique DOM ID for the scrollable log container so JS can target it
_TERMINAL_ID = "griffin-terminal-log-box"

def format_log_line(log: rx.Var) -> rx.Component:
    """Format individual log line with dynamic colors depending on content"""
    return rx.cond(
        log.contains("Error") | log.contains("Failed") | log.contains("failed") | log.contains("critical"),
        rx.text(log, style={"color": COLORS["error"], "fontFamily": FONTS["mono"], "fontSize": "0.82rem", "lineHeight": "1.4"}),
        rx.cond(
            log.contains("Warning") | log.contains("⚠️") | log.contains("warning"),
            rx.text(log, style={"color": COLORS["warning"], "fontFamily": FONTS["mono"], "fontSize": "0.82rem", "lineHeight": "1.4"}),
            rx.cond(
                log.contains("Success") | log.contains("Complete") | log.contains("complete") | log.contains("Done") | log.contains("done"),
                rx.text(log, style={"color": COLORS["success"], "fontFamily": FONTS["mono"], "fontSize": "0.82rem", "lineHeight": "1.4"}),
                rx.cond(
                    log.contains("Starting") | log.contains("Running") | log.contains("running") | log.contains("Starting"),
                    rx.text(log, style={"color": COLORS["accent"], "fontFamily": FONTS["mono"], "fontSize": "0.82rem", "lineHeight": "1.4"}),
                    rx.text(log, style={"color": COLORS["text_secondary"], "fontFamily": FONTS["mono"], "fontSize": "0.82rem", "lineHeight": "1.4"})
                )
            )
        )
    )


def terminal_logs_box() -> rx.Component:
    """Render a premium IDE-like live console box with auto-scroll-to-bottom"""
    from griffin_reflex.griffin_reflex import State

    # Inline JS: on every DOM mutation inside the terminal box, snap to bottom
    _autoscroll_js = f"""
    (function() {{
        function scrollTerminal() {{
            var el = document.getElementById('{_TERMINAL_ID}');
            if (el) {{ el.scrollTop = el.scrollHeight; }}
        }}
        // Scroll once immediately (e.g. on initial load / page transition)
        scrollTerminal();
        // Observe any new child nodes (new log lines) and scroll on each change
        var el = document.getElementById('{_TERMINAL_ID}');
        if (el && !el.__griffinObserver) {{
            var obs = new MutationObserver(scrollTerminal);
            obs.observe(el, {{ childList: true, subtree: true, characterData: true }});
            el.__griffinObserver = obs;
        }}
    }})();
    """

    return rx.box(
        rx.vstack(
            # ── Top Window Title Bar ──────────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.box(width="12px", height="12px", border_radius="50%", background="#ef4444", style={"boxShadow": "0 0 6px #ef4444"}),
                    rx.box(width="12px", height="12px", border_radius="50%", background="#f59e0b", style={"boxShadow": "0 0 6px #f59e0b"}),
                    rx.box(width="12px", height="12px", border_radius="50%", background="#10b981", style={"boxShadow": "0 0 6px #10b981"}),
                    spacing="2",
                ),
                rx.hstack(
                    rx.icon(tag="terminal", size=14, color=COLORS["text_secondary"]),
                    rx.text("griffin-ai-scientist @ dataset", size="1", color=COLORS["text_secondary"], font_family=FONTS["mono"]),
                    spacing="2",
                    align_items="center",
                ),
                rx.spacer(),
                rx.badge("LIVE", color_scheme="green", variant="soft", size="1", radius="full"),
                width="100%",
                align_items="center",
                padding="8px 16px",
                border_bottom=f"1px solid {COLORS['border_highlight']}",
                background="rgba(10, 15, 30, 0.4)",
            ),

            # ── Console Content Logs (auto-scroll container) ──────────────
            rx.box(
                # The scrollable div — targeted by _autoscroll_js via its id
                rx.box(
                    rx.foreach(
                        State.logs,
                        format_log_line,
                    ),
                    id=_TERMINAL_ID,
                    width="100%",
                    height="260px",
                    overflow_y="auto",
                    # smooth scroll so jumps feel polished
                    style={"scrollBehavior": "smooth"},
                ),
                # Auto-scroll script — re-runs every time the component re-renders
                rx.script(_autoscroll_js),
                width="100%",
                padding="16px",
                background="rgba(0, 0, 0, 0.4)",
            ),

            # ── Bottom Window Status Bar ──────────────────────────────────
            rx.hstack(
                rx.hstack(
                    rx.box(
                        width="8px",
                        height="8px",
                        border_radius="50%",
                        background=COLORS["success"],
                        style={"boxShadow": f"0 0 6px {COLORS['success']}"}
                    ),
                    rx.text("CONNECTED", size="1", font_family=FONTS["mono"], font_weight="600", color=COLORS["success"]),
                    spacing="2",
                    align_items="center",
                ),
                rx.spacer(),
                rx.text(
                    rx.cond(State.logs.length() > 0, f"Lines: {State.logs.length()}", "Console Idle"),
                    size="1",
                    color=COLORS["text_secondary"],
                    font_family=FONTS["mono"],
                ),
                rx.text("UTF-8", size="1", color=COLORS["text_secondary"], font_family=FONTS["mono"]),
                rx.text("powershell", size="1", color=COLORS["text_secondary"], font_family=FONTS["mono"]),
                spacing="4",
                width="100%",
                padding="6px 16px",
                border_top=f"1px solid {COLORS['border_highlight']}",
                background="rgba(10, 15, 30, 0.4)",
            ),
            spacing="0",
            width="100%",
        ),
        height="350px",
        background="rgba(5, 8, 22, 0.85)",
        border=f"1px solid {COLORS['border_highlight']}",
        border_radius="18px",
        style={
            "boxShadow": "0 20px 40px -15px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.05)",
            "overflow": "hidden",
            "backdropFilter": "blur(20px)",
        },
        margin_top="6",
        width="100%",
    )
