import reflex as rx
from griffin_reflex.styles.theme import COLORS, FONTS

def limit_card(label: str, value: rx.Var, on_change) -> rx.Component:
    """Helper to render a database crawler limit input card"""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="database", size=12, color=COLORS["accent"]),
                rx.text(label, size="1", color=COLORS["text_secondary"], font_family=FONTS["body"], font_weight="600"),
                spacing="2",
                align_items="center",
            ),
            rx.input(
                type="number",
                value=value,
                on_change=on_change,
                size="2",
                style={
                    "background": "rgba(255, 255, 255, 0.02)",
                    "border": f"1px solid {COLORS['border_highlight']}",
                    "borderRadius": "8px",
                    "color": COLORS["text_primary"],
                    "fontFamily": FONTS["mono"],
                    "width": "100%",
                    "minHeight": "36px",
                    "padding": "4px 8px",
                    "transition": "all 0.3s ease",
                    "_focus": {
                        "borderColor": COLORS["accent"],
                        "boxShadow": f"0 0 10px {COLORS['accent_glow']}",
                    }
                }
            ),
            spacing="2",
            align_items="flex-start",
        ),
        padding="12px 14px",
        border_radius="12px",
        background="rgba(15, 23, 42, 0.35)",
        border=f"1px solid {COLORS['border']}",
        flex="1",
        min_width="120px",
        style={
            "transition": "all 0.25s ease",
            "_hover": {
                "borderColor": COLORS["border_highlight"],
                "background": "rgba(20, 30, 55, 0.4)",
            }
        }
    )

def agent_selector(label: str, checked_var: rx.Var, on_change) -> rx.Component:
    """Helper to render a premium styled agent toggle checkbox"""
    return rx.box(
        rx.hstack(
            rx.checkbox(
                checked=checked_var,
                on_change=on_change,
                style={"cursor": "pointer"}
            ),
            rx.text(label, size="2", font_family=FONTS["body"], color=COLORS["text_primary"]),
            spacing="3",
            align_items="center",
        ),
        padding="10px 14px",
        border_radius="10px",
        background="rgba(15, 23, 42, 0.4)",
        border=f"1px solid {COLORS['border']}",
        width="100%",
        style={
            "transition": "all 0.2s ease",
            "_hover": {
                "borderColor": COLORS["primary"],
                "background": f"{COLORS['primary']}05",
            }
        }
    )

def planner_workspace() -> rx.Component:
    """The redesigned Research Planner workspace component"""
    from griffin_reflex.griffin_reflex import State

    return rx.vstack(
        # Page Header
        rx.vstack(
            rx.heading(
                "Scientific Query Planner",
                size="8",
                style={
                    "fontFamily": FONTS["heading"],
                    "letterSpacing": "-0.03em",
                    "background": f"linear-gradient(120deg, {COLORS['text_primary']} 0%, {COLORS['primary']} 45%, {COLORS['accent']} 100%)",
                    "WebkitBackgroundClip": "text",
                    "WebkitTextFillColor": "transparent",
                    "backgroundClip": "text",
                }
            ),
            rx.text(
                "Define your scientific hypothesis or research query to direct autonomous specialized agents.",
                color=COLORS["text_secondary"],
                size="3",
                style={"lineHeight": "1.6"}
            ),
            spacing="1",
            margin_bottom="4",
            width="100%",
        ),

        # Query Card Input Workspace
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="search", size=18, color=COLORS["primary"]),
                    rx.text("Enter Research Goal or Hypothesis", weight="bold", size="3", color=COLORS["text_primary"], font_family=FONTS["heading"]),
                    spacing="2",
                    align_items="center",
                ),
                rx.text_area(
                    placeholder="e.g. Compare the efficacy of Metformin and Berberine in diabetic breast cancer cell lines, focusing on AMPK pathway targets...",
                    value=State.query,
                    on_change=State.set_query,
                    width="100%",
                    height="120px",
                    size="3",
                    style={
                        "fontFamily": FONTS["body"],
                        "lineHeight": "1.6",
                        "padding": "16px",
                        "background": "rgba(10, 15, 30, 0.8)",
                        "border": f"1px solid {COLORS['border_highlight']}",
                        "borderRadius": "14px",
                        "color": COLORS["text_primary"],
                        "transition": "all 0.3s ease",
                        "_focus": {
                            "borderColor": COLORS["primary"],
                            "boxShadow": f"0 0 15px {COLORS['primary_glow']}",
                        }
                    },
                ),
                spacing="3",
                width="100%",
            ),
            padding="24px",
            border_radius="20px",
            background="rgba(15, 23, 42, 0.45)",
            border=f"1px solid {COLORS['border']}",
            width="100%",
            style={
                "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
                "backdropFilter": "blur(16px)",
            }
        ),

        # Crawler Limits Section
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="download", size=18, color=COLORS["accent"]),
                    rx.text("Crawler Search Limits (Max Papers)", weight="bold", size="3", color=COLORS["text_primary"], font_family=FONTS["heading"]),
                    spacing="2",
                    align_items="center",
                ),
                rx.grid(
                    limit_card("PubMed", State.collector_limits["PubMed"], State.set_limit_pubmed),
                    limit_card("PMC", State.collector_limits["PMC"], State.set_limit_pmc),
                    limit_card("SemanticScholar", State.collector_limits["SemanticScholar"], State.set_limit_semanticscholar),
                    limit_card("OpenAlex", State.collector_limits["OpenAlex"], State.set_limit_openalex),
                    limit_card("ClinicalTrials", State.collector_limits["ClinicalTrials"], State.set_limit_clinicaltrials),
                    limit_card("bioRxiv", State.collector_limits["bioRxiv"], State.set_limit_biorxiv),
                    limit_card("ChEMBL", State.collector_limits["ChEMBL"], State.set_limit_chembl),
                    limit_card("UniProt", State.collector_limits["UniProt"], State.set_limit_uniprot),
                    limit_card("PubChem", State.collector_limits["PubChem"], State.set_limit_pubchem),
                    limit_card("dbSNP", State.collector_limits["dbSNP"], State.set_limit_dbsnp),
                    columns="5",
                    spacing="3",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            padding="24px",
            border_radius="20px",
            background="rgba(15, 23, 42, 0.45)",
            border=f"1px solid {COLORS['border']}",
            width="100%",
            style={
                "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
                "backdropFilter": "blur(16px)",
            },
            margin_top="4",
        ),

        # Synthesis Configuration Card
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon(tag="settings-2", size=18, color=COLORS["primary"]),
                    rx.text("Synthesis & Specialist Agent Routing Settings", weight="bold", size="3", color=COLORS["text_primary"], font_family=FONTS["heading"]),
                    spacing="2",
                    align_items="center",
                ),
                rx.hstack(
                    rx.hstack(
                        rx.checkbox(
                            checked=State.use_manual_agents,
                            on_change=State.set_use_manual_agents,
                            style={"cursor": "pointer"}
                        ),
                        rx.text("Override LLM Routing (manually select agents)", size="2", font_family=FONTS["body"], color=COLORS["text_primary"]),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.hstack(
                        rx.checkbox(
                            checked=State.force_fresh,
                            on_change=State.set_force_fresh,
                            style={"cursor": "pointer"}
                        ),
                        rx.text("Force Fresh Dataset Retrieval", size="2", font_family=FONTS["body"], color=COLORS["text_primary"]),
                        spacing="2",
                        align_items="center",
                    ),
                    spacing="6",
                    wrap="wrap",
                ),
                # Show manual specialist selectors
                rx.cond(
                    State.use_manual_agents,
                    rx.box(
                        rx.grid(
                            agent_selector("Claim Extractor", State.sel_claim_extractor, State.set_sel_claim_extractor),
                            agent_selector("Evidence Ranker", State.sel_evidence, State.set_sel_evidence),
                            agent_selector("Contradiction Detector", State.sel_contradiction, State.set_sel_contradiction),
                            agent_selector("Synthesis Agent", State.sel_synthesis, State.set_sel_synthesis),
                            agent_selector("Glossary Generator", State.sel_glossary, State.set_sel_glossary),
                            agent_selector("Clinical Evaluator", State.sel_clinical, State.set_sel_clinical),
                            agent_selector("Consensus Analyst", State.sel_consensus, State.set_sel_consensus),
                            agent_selector("Lab Protocol Planner", State.sel_experiment, State.set_sel_experiment),
                            agent_selector("ELN Record Assistant", State.sel_eln, State.set_sel_eln),
                            agent_selector("Layperson Primer", State.sel_primer, State.set_sel_primer),
                            agent_selector("Methodology Critic", State.sel_methodology, State.set_sel_methodology),
                            agent_selector("Bias Detector", State.sel_bias, State.set_sel_bias),
                            columns="4",
                            spacing="3",
                            width="100%",
                        ),
                        padding="20px",
                        border_radius="16px",
                        background="rgba(99, 102, 241, 0.04)",
                        border=f"1px solid {COLORS['primary']}25",
                        width="100%",
                        style={"boxShadow": f"inset 0 0 15px {COLORS['primary_glow']}10"},
                        margin_top="3",
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            padding="24px",
            border_radius="20px",
            background="rgba(15, 23, 42, 0.45)",
            border=f"1px solid {COLORS['border']}",
            width="100%",
            style={
                "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.35)",
                "backdropFilter": "blur(16px)",
            },
            margin_top="4",
        ),

        # Execute Planned Query Trigger Button
        rx.button(
            rx.hstack(
                rx.icon(tag="microscope", size=18),
                rx.text("Run Planned Query Pipeline", font_weight="600"),
                spacing="3",
            ),
            on_click=State.prepare_query_planner,
            loading=State.is_running | State.is_extracting_intent,
            size="3",
            style={
                "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                "boxShadow": f"0 6px 20px {COLORS['primary_glow']}",
                "border": "none",
                "color": "white",
                "borderRadius": "14px",
                "minHeight": "48px",
                "padding": "0 28px",
                "cursor": "pointer",
                "transition": "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                "marginTop": "16px",
                "_hover": {
                    "transform": "translateY(-2px)",
                    "boxShadow": f"0 8px 25px {COLORS['primary_glow']}",
                    "filter": "brightness(1.1)",
                }
            }
        ),

        # Verification dialog popover root
        rx.dialog.root(
            rx.dialog.content(
                rx.vstack(
                    rx.dialog.title(
                        rx.hstack(
                            rx.text("🧬", font_size="24px"),
                            rx.text("Verify Research Intent & Specialist Routing", font_family=FONTS["heading"], font_weight="700"),
                            spacing="2",
                            align_items="center",
                        ),
                    ),
                    rx.box(
                        height="1px",
                        width="100%",
                        background=f"linear-gradient(90deg, {COLORS['border_highlight']}, transparent)",
                        margin_y="2",
                    ),
                    rx.dialog.description(
                        rx.vstack(
                            rx.text("Extracted Hypothesis Intent:", size="2", weight="bold", color=COLORS["text_secondary"], font_family=FONTS["heading"]),
                            rx.text(
                                State.extracted_intent, 
                                size="3", 
                                color=COLORS["primary"], 
                                style={
                                    "background": f"{COLORS['primary']}12", 
                                    "padding": "12px 16px", 
                                    "borderRadius": "10px", 
                                    "fontFamily": FONTS["mono"], 
                                    "width": "100%",
                                    "border": f"1px solid {COLORS['primary']}25",
                                }
                            ),
                            rx.cond(
                                ~State.use_manual_agents,
                                rx.vstack(
                                    rx.text("Specialist Agent LLM Routing Route:", size="2", weight="bold", color=COLORS["text_secondary"], font_family=FONTS["heading"]),
                                    rx.text(
                                        State.extracted_routed_agents_str, 
                                        size="3", 
                                        color=COLORS["accent"], 
                                        style={
                                            "background": f"{COLORS['accent']}12", 
                                            "padding": "12px 16px", 
                                            "borderRadius": "10px", 
                                            "fontFamily": FONTS["mono"], 
                                            "width": "100%",
                                            "border": f"1px solid {COLORS['accent']}25",
                                        }
                                    ),
                                    width="100%",
                                    spacing="2",
                                    margin_top="3",
                                )
                            ),
                            rx.text("If you need to adjust or guide the search intent, provide refinement prompts below:", size="2", color=COLORS["text_secondary"], font_family=FONTS["body"], margin_top="4"),
                            rx.input(
                                placeholder="Refinement prompts (e.g. 'prioritize Oxford clinical evidence', 'ignore non-human trial reports')",
                                value=State.refinement_instruction,
                                on_change=State.set_refinement_instruction,
                                size="3",
                                style={
                                    "background": "rgba(10, 15, 30, 0.7)",
                                    "border": f"1px solid {COLORS['border_highlight']}",
                                    "borderRadius": "10px",
                                    "color": COLORS["text_primary"],
                                    "fontFamily": FONTS["body"],
                                    "width": "100%",
                                    "_focus": {
                                        "borderColor": COLORS["primary"],
                                        "boxShadow": f"0 0 10px {COLORS['primary_glow']}",
                                    }
                                }
                            ),
                            rx.hstack(
                                rx.dialog.close(
                                    rx.button(
                                        "Cancel & Edit Query", 
                                        on_click=State.close_confirm_dialog,
                                        size="2",
                                        variant="soft",
                                        color_scheme="gray",
                                        style={
                                            "borderRadius": "10px",
                                            "cursor": "pointer",
                                            "minHeight": "38px",
                                        }
                                    )
                                ),
                                rx.dialog.close(
                                    rx.button(
                                        "Confirm & Run", 
                                        on_click=State.run_query_planner,
                                        size="2",
                                        style={
                                            "background": f"linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']})",
                                            "color": "white",
                                            "borderRadius": "10px",
                                            "cursor": "pointer",
                                            "minHeight": "38px",
                                            "padding": "0 18px",
                                        }
                                    )
                                ),
                                spacing="3",
                                justify="end",
                                width="100%",
                                margin_top="5",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                style={
                    "background": "linear-gradient(160deg, #050816 0%, #0b1020 100%)",
                    "border": f"1px solid {COLORS['border_highlight']}",
                    "borderRadius": "22px",
                    "boxShadow": "0 24px 80px rgba(0, 0, 0, 0.75)",
                    "padding": "24px",
                    "maxWidth": "580px",
                },
            ),
            open=State.show_confirm_dialog,
        ),
        spacing="4",
        width="100%",
    )
