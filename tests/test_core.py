import unittest
import numpy as np
from src.core import evidence_ranker
from src.core import graph_rag

class TestCoreLogic(unittest.TestCase):
    def test_extract_sample_size(self):
        # Test explicit 'n = ...' pattern
        self.assertEqual(evidence_ranker.extract_sample_size("n = 154 patients"), 154)
        self.assertEqual(evidence_ranker.extract_sample_size("There were n=1,245 participants in the trial."), 1245)
        
        # Test 'X patients' pattern
        self.assertEqual(evidence_ranker.extract_sample_size("cohort of 300 women with breast cancer"), 300)
        self.assertEqual(evidence_ranker.extract_sample_size("we enrolled 42 individuals"), 42)
        
        # Test no matches / invalid ranges
        self.assertIsNone(evidence_ranker.extract_sample_size("there were no participants mentioned"))
        self.assertIsNone(evidence_ranker.extract_sample_size("enrolled 2 patients"))  # below lower threshold of 5

    def test_classify_and_score(self):
        # Level 1 RCT classification
        base, label, size, final = evidence_ranker.classify_and_score(
            "Double-blind randomized controlled trial of metformin",
            "We enrolled 500 patients and monitored AMPK."
        )
        self.assertEqual(base, 9.0)
        self.assertEqual(label, "Randomized Controlled Trial (Phase III/IV)")
        self.assertEqual(size, 500)
        self.assertEqual(final, 9.5)  # RCT (9.0) + sample size > 100 bonus (0.5)

        # Level 5 Preclinical (In vitro)
        base, label, size, final = evidence_ranker.classify_and_score(
            "In vitro cell viability effects of metformin",
            "Metformin activates AMPK in MCF7 breast cancer cell line."
        )
        self.assertEqual(base, 2.0)
        self.assertEqual(label, "Preclinical Study (In Vitro / In Vivo Animal)")
        self.assertEqual(final, 2.0)  # Cell lines don't get sample size bonuses

    def test_parse_embedding(self):
        # Test parsing float list JSON string
        emb_str = "[0.1, -0.2, 0.35]"
        parsed = graph_rag.parse_embedding(emb_str)
        self.assertTrue(isinstance(parsed, np.ndarray))
        np.testing.assert_allclose(parsed, np.array([0.1, -0.2, 0.35], dtype=np.float32), rtol=1e-5)

        # Test parsing actual list
        np.testing.assert_allclose(graph_rag.parse_embedding([1.0, 2.0]), np.array([1.0, 2.0], dtype=np.float32), rtol=1e-5)

        # Test invalid inputs raises ValueError
        with self.assertRaises(ValueError):
            graph_rag.parse_embedding("invalid embedding")

if __name__ == "__main__":
    unittest.main()
