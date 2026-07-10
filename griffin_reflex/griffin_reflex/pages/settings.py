import reflex as rx

from griffin_reflex.components.sidebar import sidebar
from griffin_reflex.components.ui import page_shell, glass_card


def settings():
    return page_shell(
        sidebar(active="/settings"),
        rx.vstack(
            rx.heading("System Configuration & Settings", size="9"),
            rx.text(
                "Model routing, API keys, and LLM options are configured in the Planner sidebar (main workbench).",
                color="gray",
            ),
            glass_card(
                rx.vstack(
                    rx.heading("Where to configure", size="5"),
                    rx.text("• PubMed email, Semantic Scholar key, Gemini key → Planner left sidebar"),
                    rx.text("• Global / custom model routing → Planner left sidebar"),
                    rx.text("• Temperature, context, max tokens, thinking mode → Planner left sidebar"),
                    rx.text("• Per-source collector limits → Planner tab"),
                    rx.divider(),
                    rx.link(
                        rx.button("Open Planner controls →", color_scheme="indigo"),
                        href="/",
                    ),
                    spacing="3",
                    width="100%",
                )
            ),
            glass_card(
                rx.vstack(
                    rx.heading("Default model mixture (when not overridden)", size="5"),
                    rx.text("Planner: llama3.1:8b"),
                    rx.text("Claim extractor: llama3.1:8b"),
                    rx.text("Contradiction detector: qwen3.5:9b"),
                    rx.text("Consensus analyst: koesn/llama3-openbiollm-8b:latest"),
                    rx.text("Synthesis / experiment: llama3.1:8b"),
                    spacing="2",
                    width="100%",
                )
            ),
            spacing="6",
            width="100%",
        ),
    )
