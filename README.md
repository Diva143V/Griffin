# Metformin and Breast Cancer Paper Pipeline

This project builds a small research dataset around the query **metformin breast cancer**.

It collects papers from modular source collectors, merges and deduplicates them, filters to the topic of interest, generates embeddings, and supports semantic retrieval and claim extraction.

## Pipeline

```mermaid
flowchart TD
    A[PubMed collector] --> D[Merge and deduplicate]
    B[Europe PMC collector] --> D
    C[Semantic Scholar collector] --> D
    D --> E[Save final dataset]
    E --> F[Clean topic-specific subset]
    F --> G[Generate embeddings]
    G --> H[Semantic retrieval]
    F --> I[Claim extraction]
    F --> J[Evidence ranking]
    I --> K[Contradiction detector]
    J --> K
    K --> L[Final synthesis]
    L --> M[Streamlit App Dashboard]
    K --> M
    J --> M
    I --> M
```

## Main Scripts

- `collector_registry.py` - central registry for source collectors and their output paths.
- `planner_agent.py` - builds the query plan, workflow sections, and edges.
- `retriever_agent.py` - wraps standard and graph retrieval.
- `claim_extractor_agent.py` - agent facade for claim extraction.
- `evidence_ranker_agent.py` - agent facade for evidence scoring.
- `contradiction_agent.py` - agent facade for contradiction analysis.
- `synthesizer_agent.py` - agent facade for synthesis generation.
- `verifier_agent.py` - lightweight consistency checks for routed answers.
- `build_dataset.py` - runs the full collection and merge pipeline and can target a subset of collectors with `--sources`.
- `collect_pubmed.py` - fetches PubMed papers with Entrez.
- `collect_pmc.py` - fetches Europe PMC papers.
- `collect_semanticscholar.py` - fetches Semantic Scholar papers.
- `clean_dataset.py` - filters to metformin + breast cancer papers.
- `generate_embeddings.py` - creates sentence embeddings for cleaned papers.
- `retrieval.py` - searches the embedded dataset by semantic similarity.
- `claim_extractor.py` - extracts structured claims using Ollama.
- `evidence_ranker.py` - classifies papers by Oxford Levels of Evidence, extracts sample sizes, and assigns scores.
- `contradiction_detector.py` - identifies contradictions from extracted claims using pairwise LLM comparison.
- `final_synthesis.py` - synthesizes an advanced final report from claims, contradiction records, and evidence quality metrics.
- `app.py` - launches the premium Streamlit interactive web dashboard to visualize findings.

## Setup

Create and activate the virtual environment, then install dependencies:

```powershell
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set required environment variables:

```powershell
$env:ENTREZ_EMAIL = 'your.email@example.com'
$env:SEMANTIC_SCHOLAR_API_KEY = 'your-semantic-scholar-key'
```

## Build the dataset

Run the full pipeline:

```powershell
python build_dataset.py --query "metformin breast cancer" --max-results 100 --run-filter
```

Run only a subset of collectors:

```powershell
python build_dataset.py --sources PubMed PMC --max-results 100 --run-filter
```

This produces:

- `dataset/pubmed.csv`
- `dataset/pmc.csv`
- `dataset/semantic_scholar.csv`
- `dataset/final_papers.csv`
- `dataset/clean_papers.csv` when `--run-filter` is used

The collector layer is intentionally modular: new source fetchers should register once in `collector_registry.py` and can then be switched on or off from the build command.

## Generate embeddings

```powershell
python generate_embeddings.py --input dataset/clean_papers.csv --output dataset/clean_papers_with_embeddings.csv --include-title
```

## Vector Database (Chroma DB)

This project integrates **Chroma DB** as a persistent local vector database to enable semantic caching, fast retrieval, and fallback recovery.

### Setup & Requirements

Chroma DB is included in the project dependencies ([pyproject.toml](file:///c:/Users/Diwa/Griffin/pyproject.toml)). It will be installed when running:

```powershell
pip install -r requirements.txt
```

### Auto-Indexing with Embeddings

By default, when you generate embeddings, they are automatically and incrementally indexed into a Chroma DB collection:

```powershell
python generate_embeddings.py --input dataset/clean_papers.csv --output dataset/clean_papers_with_embeddings.csv --include-title
```

- **Database Directory**: Stored locally at `dataset/chroma_db/`
- **Collection Name**: Defaults to `papers`
- **Bypassing Chroma DB**: Use the `--skip-chroma` flag to skip indexing.

### Populating or Querying Standalone

You can run `create_chromadb.py` to manually populate the database or test queries:

```powershell
# Populate Chroma DB from a precomputed CSV
python create_chromadb.py --input dataset/clean_papers_with_embeddings.csv --db-path dataset/chroma_db

# Run a sample query against Chroma DB
python create_chromadb.py --query "How does metformin affect breast cancer cells?"
```

### Integration in Query Planner & Recovery

Chroma DB is integrated into the agent layer:
1. **Semantic Cache Bypassing**: The [Query Planner](file:///c:/Users/Diwa/Griffin/src/agents/query_planner.py) queries Chroma DB first. If relevant papers matching the query are already present (based on cosine distance threshold), it bypasses the collection pipeline.
2. **Disk Recovery Cache**: If the dataset CSVs on disk are deleted or corrupted, the planner automatically retrieves the papers and embeddings from the Chroma DB cache and restores them back to disk.

## Search the dataset

```powershell
python retrieval.py --input dataset/clean_papers_with_embeddings.csv --query "metformin breast cancer" --top-k 5
```

## Claim extraction

```powershell
python claim_extractor.py --input dataset/clean_papers.csv --output dataset/claims.csv --limit 50 --save-every 10
```

## Evidence Ranking (Oxford Levels & Sample Size Extraction)

Ranks and updates metadata for papers:

```powershell
python evidence_ranker.py
```

Produces:
- `dataset/ranked_papers.csv` (contains Oxford clinical design labels, sample size extractions, and scaled scores)

## LLM and Agent Layer

The current application uses a focused, stage-based LLM workflow rather than a loose agent swarm.

- `claim_extractor.py` turns papers into structured claims.
- `evidence_ranker.py` scores paper quality and study design.
- `contradiction_detector.py` performs pairwise claim analysis, evidence weighting, and synthesis.
- `final_synthesis.py` produces the final report.
- `graph_rag.py` and `app.py` combine retrieval with evidence-aware answer generation for the dashboard.

This is the right place to mix models and agents selectively: keep ingestion deterministic, and reserve multi-model or multi-agent coordination for analysis, synthesis, and dashboard reasoning.

Current Ollama defaults used across the app are `llama3.1:8b`, `gemma3:4b`, `gemma3:1b`, and `qwen3.5:9b`.

## Query Planner

The Streamlit app now includes a planner tab that turns a user question into a full execution workflow before answering.

- General research questions route to standard RAG.
- Conflict or agreement questions route to graph-aware RAG plus contradiction review.
- Evidence-quality questions route to ranked evidence retrieval.
- Claim-focused questions route to the claims layer.
- The planner now shows the full workflow chain: Query, Planner, Retriever, collectors, Filter, Converter/Standardizer, Embedding, Vector DB, Executor, Evidence Ranker, Claim Extractor, Contradiction Agent, Consensus Agent, Synthesizer, and Verifier.
- The planner executes the matching retriever and surfaces the fetched papers, matched claims, and graph relations before generating the answer.

Open the planner tab in `app.py`, enter a query, review the generated steps, and then run the planned query to see the routed answer.

## Contradiction detection

The contradiction detector uses a multi-stage pipeline:

1. **Semantic pre-filtering** — embeds claims and selects the most relevant pairs by cosine similarity
2. **Pairwise LLM analysis** — classifies each pair as AGREEMENT / CONTRADICTION / PARTIAL_AGREEMENT / UNRELATED
3. **Evidence-weighted scoring** — integrates evidence quality scores from `evidence_ranker.py`
4. **Cluster & synthesise** — generates a focused synthesis from high-confidence results
5. **Report generation** — outputs JSON, Markdown, plain-text, and CSV reports

Basic usage:

```powershell
python contradiction_detector.py
```

With options:

```powershell
python contradiction_detector.py --max-pairs 20 --similarity-threshold 0.4 --evidence-file dataset/ranked_papers.csv
```

Skip embedding pre-filtering:

```powershell
python contradiction_detector.py --no-embeddings --max-pairs 15
```

Outputs produced:

- `dataset/contradictions.json` — full structured results
- `dataset/contradictions_report.md` — rich Markdown report with tables
- `dataset/contradictions.txt` — plain-text report (backward compatible)
- `dataset/contradictions.csv` — all pairwise results as CSV

## Final Synthesis

Compiles the final advanced markdown and text reports leveraging contradiction outputs and ranked evidence levels:

```powershell
python final_synthesis.py
```

Produces:
- `dataset/final_synthesis.txt` (Plain text report)
- `dataset/final_synthesis.md` (Markdown report)

## Interactive Dashboard UI

Launch the Streamlit app to explore metrics, synthesis summaries, contradictions list, and ranked clinical datasets:

```powershell
streamlit run app.py
```

## Notes

- `venv/` is intentionally ignored and should not be committed.
- The Semantic Scholar collector uses conservative pacing and retries because the API is rate-limited.
- `claim_extractor.py`, `contradiction_detector.py`, and `final_synthesis.py` require a local Ollama instance to be running.
