# Griffin Dataset & Neo4j Integration Workflows

### 1. Data Pipeline & Collectors
- Extraction collectors (`PubMed`, `PMC`, `OpenAlex`, `ClinicalTrials`, `bioRxiv`, `ChEMBL`, `UniProt`, `PubChem`, `dbSNP`, `DuckDuckGo`) save output CSVs to `dataset/`.
- De-duplication and keyword filtering clean the records into `dataset/clean_papers.csv` and generate vector embeddings with `BAAI/bge-small-en-v1.5`.
- Secondary LLM stages produce markdown analysis reports on disk (`final_synthesis.md`, `consensus_report.md`, `contradictions_report.md`, `clinical_report.md`, `bias_report.md`, `methodology_report.md`, `glossary_report.md`, `primer_report.md`, `protocol_draft.txt`, `eln_entry.txt`, `overseer_report.md`).

### 2. Ollama GPU/CUDA Troubleshooting
- If Ollama fails to run models (like `llama3.1:8b`) with CUDA stack overrun errors (exit code `0xc0000409`), override the execution backend to use Vulkan compute:
  ```powershell
  $env:CUDA_VISIBLE_DEVICES="-1"; ollama serve
  ```

### 3. Neo4j Synchronization Workflows
- **`sync_neo4j.py`** populates the Neo4j Graph DB:
  1. Sets up unique constraints for `Paper`, `Claim`, `Entity`, `Query`, and `Report` nodes.
  2. Ingests raw papers and maps vectors to the cosine `paper_embeddings` index.
  3. Ingests extracted claims (`dataset/claims.csv`) and contradictions (`dataset/contradictions.json`).
  4. Ingests starting `Query` details from `dataset/execution_trace.json`.
  5. Ingests the 11 text/markdown agent reports as `Report` nodes linked to the query via `[:PRODUCED_REPORT]`.
  6. Automatically scans report texts to link them back to relevant papers via `[:REFERENCES_PAPER]`.
- **Sync Speed Optimization**: If you only need to sync papers, metadata, and reports without running heavy LLM-based entity-relationship extraction on every claim, run:
  ```powershell
  python sync_neo4j.py --model llama3.1:8b --skip-entities
  ```
- **Database Growth & Clearing**:
  - By default, `sync_neo4j.py` runs in **incremental sync mode** (preserving historical queries, papers, and reports to let the database grow).
  - To wipe the database and start fresh, run with the `--clear` flag:
    ```powershell
    python sync_neo4j.py --model llama3.1:8b --clear
    ```
