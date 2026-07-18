import unittest
from src.agents import planner_agent

class TestAgents(unittest.TestCase):
    def test_empty_query_plan(self):
        plan = planner_agent.build_query_plan("", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "empty")
        self.assertEqual(plan.route, "idle")
        self.assertEqual(plan.model, "llama3.1:8b")
        self.assertEqual(len(plan.steps), 1)

    def test_contradiction_query_plan(self):
        plan = planner_agent.build_query_plan("Are there contradictions in metformin studies?", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "conflict_analysis")
        self.assertEqual(plan.route, "graph_rag + contradiction_review")
        self.assertTrue(any(step.name == "load_relations" for step in plan.steps))

    def test_evidence_query_plan(self):
        plan = planner_agent.build_query_plan("What is the level of evidence for metformin?", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "evidence_review")
        self.assertEqual(plan.route, "ranked_evidence_rag")

    def test_claims_query_plan(self):
        plan = planner_agent.build_query_plan("List claims and assertions for berberine", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "claim_analysis")
        self.assertEqual(plan.route, "claims_exploration")

    def test_synthesis_query_plan(self):
        plan = planner_agent.build_query_plan("Provide a synthesis of metformin for cancer cell growth", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "summary")
        self.assertEqual(plan.route, "scientific_synthesis")

    def test_default_rag_query_plan(self):
        plan = planner_agent.build_query_plan("What does metformin do?", "llama3.1:8b", default_top_k=5)
        self.assertEqual(plan.intent, "general_research_question")
        self.assertEqual(plan.route, "standard_rag")

if __name__ == "__main__":
    unittest.main()
