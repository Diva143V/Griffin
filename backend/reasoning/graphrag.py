from typing import List, Any

class MockVectorDB:
    def search(self, question: str) -> List[dict]:
        return [
            {"title": "Metformin and Breast Cancer Survival", "abstract": "Metformin linked with survival in cancer metabolism."},
            {"title": "AMPK activation pathways", "abstract": "AMPK pathways are active in cancer metabolism."}
        ]

class MockGraphDB:
    def query_entities(self, entities: List[str]) -> List[dict]:
        return [
            {"source": "Metformin", "target": "Cancer", "label": "studied in"},
            {"source": "Metformin", "target": "AMPK Pathway", "label": "activates"}
        ]

class MockLLM:
    def generate(self, prompt: str) -> str:
        return (
            "**1. Evidence Summary**\n"
            "Studies indicate a strong link between Metformin usage and survival rate improvements in diabetic patients.\n\n"
            "**2. Conflicting Findings**\n"
            "Some clinical trial cohorts show neutral or statistically insignificant differences.\n\n"
            "**3. Possible Mechanisms**\n"
            "Metformin activates the AMPK pathway, which inhibits mTOR and slows down cell proliferation.\n\n"
            "**4. Scientific Conclusion**\n"
            "Metformin serves as a potent modulator with strong indications of oncology-metabolism benefits."
        )

class GraphRAG:
    def __init__(self, vector_db=None, graph_db=None, llm=None):
        self.vector_db = vector_db or MockVectorDB()
        self.graph_db = graph_db or MockGraphDB()
        self.llm = llm or MockLLM()

    def extract_entities(self, papers: List[dict]) -> List[str]:
        entities = []
        for p in papers:
            if "title" in p:
                entities.append(p["title"])
        return entities

    def retrieve_context(self, question: str) -> dict:
        papers = self.vector_db.search(question)
        entities = self.extract_entities(papers)
        relationships = self.graph_db.query_entities(entities)
        return {
            "papers": papers,
            "entities": entities,
            "relationships": relationships
        }

    def reason(self, question: str) -> str:
        context = self.retrieve_context(question)
        prompt = f"""
You are a scientific reasoning agent.
Question:
{question}

Evidence:
{context}

Generate:
1. Evidence summary
2. Conflicting findings
3. Possible mechanisms
4. Scientific conclusion
"""
        return self.llm.generate(prompt)
