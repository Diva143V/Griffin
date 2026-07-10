import reflex as rx

NODES = [
    {
        "id":"metformin",
        "label":"Metformin",
        "type":"Drug"
    },
    {
        "id":"cancer",
        "label":"Cancer",
        "type":"Disease"
    },
    {
        "id":"ampk",
        "label":"AMPK Pathway",
        "type":"Mechanism"
    },
    {
        "id":"trial",
        "label":"Clinical Trials",
        "type":"Evidence"
    }
]
EDGES=[
    {
        "source":"metformin",
        "target":"cancer",
        "label":"studied in"
    },
    {
        "source":"metformin",
        "target":"ampk",
        "label":"activates"
    },
    {
        "source":"trial",
        "target":"cancer",
        "label":"evidence"
    }
]

def node_card(node):
    return rx.box(
        rx.vstack(
            rx.text(
                node["label"],
                weight="bold"
            ),
            rx.badge(
                node["type"]
            )
        ),
        padding="15px",
        border_radius="15px",
        background="rgba(99,102,241,.15)",
        border="1px solid rgba(255,255,255,.1)"
    )

def knowledge_graph():
    return rx.vstack(
        rx.heading(
            "Knowledge Graph Explorer",
            size="7"
        ),
        rx.text(
            "Explore scientific relationships between drugs, diseases and evidence",
            color="gray"
        ),
        rx.grid(
            *[
                node_card(n)
                for n in NODES
            ],
            columns="4",
            spacing="4"
        ),
        rx.divider(),
        rx.vstack(
            rx.heading(
                "Relationships",
                size="5"
            ),
            *[
                rx.text(
                    f"{e['source']} → {e['target']}  ({e['label']})"
                )
                for e in EDGES
            ],
            spacing="3"
        ),
        width="100%",
        spacing="6"
    )
