import reflex as rx

def knowledge_graph():
    from griffin_reflex.griffin_reflex import State
    return rx.vstack(
        rx.heading(
            "Knowledge Graph Explorer",
            size="7"
        ),
        rx.text(
            "Explore scientific relationships between drugs, diseases and evidence",
            color="gray"
        ),
        rx.cond(
            State.graph_figure,
            rx.plotly(data=State.graph_figure, layout={"height": "600px", "width": "100%"}),
            rx.box(
                rx.text("Knowledge Graph not generated yet. Run the consensus pipeline to view data.", color="gray"),
                padding="40px",
                border="1px dashed rgba(255,255,255,0.2)",
                border_radius="10px",
                width="100%",
                text_align="center"
            )
        ),
        width="100%",
        spacing="6"
    )
