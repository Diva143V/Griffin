import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.collectors import collect_clinicaltrials
from src.collectors import collect_pubmed
from src.collectors import collect_openalex

class TestCollectors(unittest.TestCase):
    @patch("src.collectors.collect_clinicaltrials.fetch_page")
    def test_clinicaltrials_collector(self, mock_fetch):
        # Mock empty response first
        mock_fetch.return_value = {"studies": []}
        df = collect_clinicaltrials.collect("test query", max_pages=1)
        self.assertTrue(df.empty)

        # Mock structured response
        mock_fetch.return_value = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT0001",
                            "briefTitle": "Metformin vs Placebo in Breast Cancer"
                        },
                        "descriptionModule": {
                            "briefSummary": "A summary of the study."
                        },
                        "statusModule": {
                            "startDateStruct": {"date": "2024-01-15"}
                        },
                        "sponsorCollaboratorsModule": {
                            "leadSponsor": {"name": "Sponsor University"}
                        }
                    }
                }
            ],
            "nextPageToken": None
        }
        df = collect_clinicaltrials.collect("test query", max_pages=1)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["title"], "Metformin vs Placebo in Breast Cancer")
        self.assertEqual(df.iloc[0]["doi"], "NCTId:NCT0001")
        self.assertEqual(df.iloc[0]["pmid"], "NCT0001")
        self.assertEqual(df.iloc[0]["source"], "ClinicalTrials")
        self.assertEqual(df.iloc[0]["year"], "2024")

    @patch("Bio.Entrez.esearch")
    @patch("Bio.Entrez.read")
    @patch("Bio.Entrez.efetch")
    @patch("Bio.Medline.parse")
    def test_pubmed_collector(self, mock_medline_parse, mock_efetch, mock_read, mock_esearch):
        # 1. Test empty search results
        mock_read.side_effect = [{"Count": "0"}]
        df = collect_pubmed.collect("no_results_query", limit=10, batch_size=10)
        self.assertTrue(df.empty)

        # 2. Test successful search and fetch
        mock_read.side_effect = [
            {"Count": "1"},  # Count lookup
            {"IdList": ["12345"]}  # IdList fetch
        ]
        mock_medline_parse.return_value = [
            {
                "TI": "AMPK activation by Metformin",
                "AB": "Abstract detail.",
                "DP": "2023",
                "PMID": "12345"
            }
        ]
        df = collect_pubmed.collect("metformin", limit=10, batch_size=10)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["title"], "AMPK activation by Metformin")
        self.assertEqual(df.iloc[0]["pmid"], "12345")
        self.assertEqual(df.iloc[0]["source"], "PubMed")

    @patch("requests.Session.get")
    def test_openalex_collector(self, mock_get):
        # Mock empty search results
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "meta": {"next_page": None}}
        mock_get.return_value = mock_response

        df = collect_openalex.collect("metformin", max_pages=1)
        self.assertTrue(df.empty)

        # Mock search results with data
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "OpenAlex Metformin Study",
                    "abstract_inverted_index": {"The": [0], "study": [1], "shows": [2], "AMPK": [3]},
                    "authorships": [{"author": {"display_name": "Dr. Alex"}}],
                    "publication_year": 2022,
                    "doi": "https://doi.org/10.1234/openalex",
                    "id": "W123456"
                }
            ],
            "meta": {"next_page": None}
        }
        df = collect_openalex.collect("metformin", max_pages=1)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["title"], "OpenAlex Metformin Study")
        # Inverted index reconstruction
        self.assertEqual(df.iloc[0]["abstract"], "The study shows AMPK")
        self.assertEqual(df.iloc[0]["pmid"], "https://doi.org/10.1234/openalex")
        self.assertEqual(df.iloc[0]["source"], "OpenAlex")

if __name__ == "__main__":
    unittest.main()
