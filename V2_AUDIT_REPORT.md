# Griffin V2 Plan vs Codebase — Full Audit Report

**Date:** 2026-07-10  
**Scope:** `imp.md` (Phases 1–8) · `griffin_reflex/` · `backend/` · working pipeline (`src/`, `app.py`, main Reflex app)

---

## Executive summary

| Layer | Status | Reality |
|-------|--------|---------|
| **Working product** | ✅ Real | Streamlit `app.py` + main Reflex app (`griffin_reflex.py` ~1700 lines) wired to `src/` agents |
| **V2 UI shell** | 🟡 Skeleton only | Pages/components exist; almost all hard-coded mock data; **not wired to real pipeline** |
| **V2 backend stubs** | 🔴 Mock only | Every `backend/**` module is a stub; **nothing imports or runs them** |
| **SaaS / Phase 5–8** | 🔴 Not implemented | No auth, DB, Docker, WebSockets in production, multi-user labs, autonomous loops |

**Bottom line:** `imp.md` was partially *scaffolded* (file tree + demo UI), not *implemented*. The real scientific workbench still lives in the original pipeline + the large `griffin_reflex.py` main app. The V2 “product” pages are disconnected demos.

---

## 1. What actually works today

### Real pipeline (`src/`)
Fully implemented agents and collectors:

- Collectors: PubMed, PMC, Semantic Scholar, OpenAlex, ClinicalTrials, bioRxiv, ChEMBL, UniProt, PubChem, dbSNP
- Agents: planner, retriever, claim extractor, evidence ranker, contradiction, consensus, experiment, ELN, synthesizer, verifier, peer review, validation, refinement, report
- Core: GraphRAG, embeddings, Chroma DB, final synthesis
- UIs that drive this: **Streamlit `app.py`** and **main Reflex index** (`griffin_reflex/griffin_reflex/griffin_reflex.py`)

### Main Reflex app (`/` route) — functional workbench
Tabs that **are** wired to real backend logic:

| Tab | Feature | Backend |
|-----|---------|---------|
| Planner | Run pipeline, logs, routing stats | `run_pipeline_cli.py` → `query_planner` |
| Synthesis | Load/run consensus + peer review | `consensus_agent`, `peer_review_agent` |
| Contradictions | Load/run claim pairs | claim extractor + contradiction detector |
| Evidence | Ranked papers + methodology flags | CSV + `audit_methodology` |
| Claims | Stance filter table | `claims.csv` |
| Benchmark | RAG vs GraphRAG | `src.core.graph_rag` |
| Overseer | Gemini report + QA + refine | report/validation/refinement agents |
| GraphRAG | Plotly knowledge graph | NetworkX from `contradictions.json` |
| Sidebar chat | RAG chat over embeddings | SentenceTransformer + Ollama |

This is the only production-usable Griffin UI in the repo.

---

## 2. V2 plan phase-by-phase status

### Phase 1 — Production UI shell
| Planned | Status | Notes |
|---------|--------|-------|
| `components/ui.py` glass cards / metrics | ✅ File exists | Static styles only |
| `components/sidebar.py` | 🟡 Partial | Exists but **wrong routes** (see bugs) |
| `components/dashboard.py` | 🟡 Mock | Hard-coded metrics (`250`, `92%`, `18`, `7`) |
| Main shell with sidebar + dashboard | 🟡 Split | V2 pages use V2 sidebar; **main `/` uses a different sidebar** (credentials/LLM controls), not the V2 nav |

### Phase 2 — Agent graph, evidence cards, copilot
| Planned | Status | Notes |
|---------|--------|-------|
| Animated multi-agent view | 🔴 Stub | `agent_animation.py` — static emoji box, **never imported** |
| Evidence intelligence cards | 🔴 Missing as V2 feature | Real evidence is only in main app Tab 4 |
| AI copilot floating panel | 🔴 Stub | `copilot.py` — no state, Send does nothing, **never imported** |
| Live agent stream | 🔴 Stub | `live_agents.py` — hard-coded logs, **never imported** |

### Phase 3 — Knowledge intelligence
| Planned | Status | Notes |
|---------|--------|-------|
| Knowledge graph explorer | 🟡 Mock | `knowledge_graph.py` — 4 hard-coded nodes (Metformin/Cancer/…); **not** Plotly/Cytoscape, not real data |
| Research timeline | 🟡 Mock | Hard-coded 2015–2025 events |
| Paper explorer | 🟡 Mock | 2 fake papers; search/Open Analysis do nothing |
| Workspace page | 🟡 Assembled | `/workspace` composes the three mocks above |
| `reflex-cytoscape` | 🔴 Not installed / not used | Plotly used only in main app |

### Phase 4 — Streaming, projects, accounts, PDF UI
| Planned | Status | Notes |
|---------|--------|-------|
| Real-time agent animation | 🔴 No | |
| Streaming AI responses | 🔴 No | Chat waits for full Ollama reply |
| Project management UI | 🟡 Mock | `/projects` shows 2 hard-coded labs |
| User accounts | 🔴 No | |
| DB-backed workspace | 🔴 No | |
| Report generation UI (PDF/LaTeX) | 🟡 Mock | `reports.py` hard-coded list, **never imported** |

### Phase 5 — SaaS architecture
| Planned | Status | Notes |
|---------|--------|-------|
| FastAPI auth (`backend/api/auth.py`) | 🔴 Stub | Returns fake `"jwt-token"`; **no FastAPI app mounts the router** |
| WebSocket agent stream | 🔴 Stub | Fake 4 steps; not mounted; UI not connected |
| Labs / Projects / Experiments DB | 🔴 No models, no Postgres | |
| User memory | 🔴 In-memory dict stub, unused | |
| `docker-compose.yml` | 🔴 **Missing** | |
| PostgreSQL / Qdrant / Neo4j | 🔴 Not present (Chroma exists in real pipeline only) | |

### Phase 6 — AI Scientist intelligence
| Planned file | Status | Reality |
|--------------|--------|---------|
| `backend/reasoning/graphrag.py` | 🔴 Mock | `MockVectorDB` / `MockGraphDB` / `MockLLM` — fake metformin text |
| `backend/agents/hypothesis.py` | 🔴 Stub | Always returns the same hard-coded hypothesis |
| `backend/agents/experiment.py` | 🔴 Stub | Always returns same MCF7 plan |
| `backend/reasoning/contradiction.py` | 🔴 Toy | Pairs every claim with “different population…” |
| `backend/writer/scientific_writer.py` | 🔴 Stub | Returns fixed section strings |
| `backend/agents/citation.py` | 🔴 Stub | Always `verified: True` |
| `backend/autonomous/research_loop.py` | 🔴 Stub | Returns a list of task strings |

**Note:** Real GraphRAG / contradiction / experiment / citation verification already exist under `src/core/` and `src/agents/` — the V2 `backend/` copies do **not** call them.

### Phase 7 — Premium product UX
| Planned | Status | Notes |
|---------|--------|-------|
| Onboarding page | 🟡 Shell | `/onboarding` works as redirect only; goal is **not saved or used** |
| Design system `styles/theme.py` | 🟡 Partial | Minimal COLORS/glass; **main app uses its own tokens**, not this file |
| Activity feed | 🔴 Orphan | `activity.py` never imported |
| Notifications | 🔴 Missing | |
| Team collaboration | 🔴 Mock badge text only | |
| Production monitoring page | 🔴 Missing | |
| Main app polish (fonts, animations) | ✅ Partial | Main `/` has real design system + keyframes |

### Phase 8 — Autonomous mode
| Planned | Status | Notes |
|---------|--------|-------|
| Research planner | 🔴 Stub | Hard-coded 5 tasks |
| Research memory graph | 🔴 Broken stub | `NameError: Any` (see bugs) |
| Human approval | 🔴 Stub | Always `awaiting_review` |
| Discovery scoring | 🔴 Formula only | Unused |
| Nightly scheduler | 🔴 Stub | Infinite sleep loop, never started |
| Discovery feed UI | 🔴 Orphan | Accept/Review buttons do nothing |
| Personality layer | 🔴 Missing | |

---

## 3. UI components: integrated vs orphaned

### Used by V2 pages
| Component | Used by |
|-----------|---------|
| `sidebar.py` | dashboard, workspace, projects, settings |
| `dashboard.py` + `ui.py` | `/dashboard` |
| `knowledge_graph.py`, `timeline.py`, `paper_explorer.py` | `/workspace` |

### Registered routes but dead-end / incomplete
| Route | Issue |
|-------|-------|
| `/` | Real workbench — **no link** to V2 pages |
| `/dashboard` | Mock metrics only |
| `/workspace` | Mock KG / timeline / papers |
| `/projects` | Mock labs only |
| `/settings` | Hard-coded model names; **not editable**, not linked from V2 sidebar |
| `/onboarding` | Goal discarded; no nav entry from main app |

### Orphan components (never imported by any page)
- `activity.py`
- `agent_animation.py`
- `agent_monitor.py`
- `copilot.py`
- `discovery_feed.py`
- `graph.py` (V2 fake interaction map)
- `live_agents.py`
- `reports.py`

These are **not in the UI** and **do not work**.

---

## 4. Backend V2 stubs — not integrated

Every module under `backend/` is unused by UI and by `src/`:

```
backend/agents/{citation,experiment,hypothesis}.py
backend/api/{auth,agents}.py          # routers never mounted
backend/autonomous/{planner,research_loop,scheduler}.py
backend/control/human_review.py
backend/memory/{user_memory,research_graph}.py
backend/reasoning/{graphrag,contradiction}.py
backend/scoring/discovery.py
backend/writer/scientific_writer.py
```

No `FastAPI()` app, no `include_router`, no Docker, no DB connection layer.

---

## 5. Concrete bugs (real code, not just missing features)

### Critical / high — main Reflex pipeline wiring

1. **`force_fresh` UI is ignored**  
   Checkbox updates `State.force_fresh`, but `execute_backend_pipeline()` never passes it. CLI hard-codes `force_fresh=True` always.

2. **Manual agent selection is discarded**  
   `forced_agents` is built as a comma-separated string then **never passed** to CLI/env/`execute_query_plan`. Override checkboxes are cosmetic.

3. **Collector limits never reach the pipeline**  
   UI stores `collector_limits` and has per-source inputs, but CLI/`execute_backend_pipeline` never forwards them. Always defaults inside planner.

4. **`refinement_instruction` never used**  
   Confirm dialog captures it; pipeline never receives it.

5. **`llm_think` never applied**  
   Checkbox exists; `src/shared/llm.py` explicitly strips `think` from options. Setting does nothing.

### Medium — UI / state bugs

6. **V2 sidebar routes are wrong**  
   ```
   Dashboard → "/"   (real workbench, not /dashboard)
   Settings  → "/workspace"  (should be /settings)
   Agents / KG / Evidence / Reports → all "/workspace"
   /projects never linked
   ```

7. **Onboarding discards research goal**  
   `OnboardingState.research_goal` is set but never written to main `State.query` or any backend.

8. **Email / limits use `default_value` not controlled `value`**  
   Inputs can desync from state on re-render; limits default display is always `"20"` even after changes.

9. **Benchmark source/relation data loaded but never rendered**  
   `std_sources_data`, `graph_sources_data`, `graph_relations_data` are filled; eval tab only shows answer text + latency.

10. **Pipeline trace fields loaded but not shown**  
    `verification_trace`, `fetched_sources`, `matched_claims`, `graph_relations_trace`, `fallback_warnings` are set after run but have no UI.

11. **Graph empty-state condition is ineffective**  
    `rx.cond(State.graph_figure, ...)` — a `go.Figure()` object is always truthy, so the “Click Load…” empty card may never show as intended.

### Low / stub runtime bugs

12. **`backend/memory/research_graph.py` — `NameError`**  
    Uses `Any` without `from typing import Any`. Crashes if called.

13. **Auth stub is insecure by design**  
    Any email/password returns success + static JWT. Not real auth (and unused).

14. **Duplicate `from typing import Any, Optional`** in main `griffin_reflex.py` (harmless clutter).

15. **Two parallel UIs with no shared nav**  
    Real app at `/` vs V2 marketing shell at `/dashboard|/workspace|...` confuses which is “the product.”

---

## 6. What is “implemented in files” vs “working end-to-end”

```
imp.md claim                          File exists?   Wired to UI?   Calls real science?
─────────────────────────────────────────────────────────────────────────────────────
Glass dashboard                       Yes            Partial        No (hard-coded)
Sidebar nav                           Yes            Yes (V2 only)  Wrong routes
Knowledge graph explorer              Yes            Workspace      Mock nodes
Paper explorer                        Yes            Workspace      Mock papers
Timeline                              Yes            Workspace      Mock events
Copilot                               Yes            No             No
Live agents / WebSocket               Yes            No             Fake steps
Auth / JWT                            Yes            No             Fake token
GraphRAG V2 class                     Yes            No             Mocks only
Hypothesis / experiment agents (V2)   Yes            No             Hard-coded strings
Autonomous loop / scheduler           Yes            No             No
Discovery feed / human review         Yes            No             No
Docker / Postgres / Neo4j / Qdrant    No             No             No
Real multi-agent pipeline             Yes (src/)     Main / only    Yes
Streamlit dashboard                   Yes (app.py)   Separate       Yes
```

---

## 7. Recommended priority fixes

### A. Make main Reflex pipeline controls actually work (highest value)
1. Pass `force_fresh`, `forced_agents`, `collector_limits`, and optionally refinement via env/CLI args into `run_pipeline_cli.py` → `execute_query_plan`.
2. Either implement `llm_think` in `src/shared/llm.py` or remove the checkbox.
3. Render loaded trace/source fields already sitting in state.

### B. Integrate or delete V2 shell
Pick one:
- **Integrate:** Point V2 sidebar to real tabs/data; replace mock metrics/papers/KG with reads from `dataset/*.csv|json`; delete orphan stubs.
- **Or quarantine:** Document V2 pages as design prototypes so they are not mistaken for production.

### C. If continuing the V2 plan for real
1. Replace every `backend/*` stub with thin wrappers over `src/agents/*` and `src/core/*`.
2. Mount FastAPI routers or drop them and use Reflex events only.
3. Add real auth + persistence only after UI is data-driven.
4. Do not add Docker/Neo4j/Qdrant until GraphRAG and projects use real stores.

---

## 8. Quick map of the repo

```
WORKING (science + UI)
├── app.py                          Streamlit production dashboard
├── run_pipeline_cli.py             CLI entry for Reflex planner
├── src/agents/*                    Real multi-agent layer
├── src/core/*                      GraphRAG, claims, evidence, synthesis
├── src/collectors/*                10 literature/data sources
└── griffin_reflex/.../griffin_reflex.py   Real Reflex workbench at "/"

SCAFFOLD / MOCK (imp.md V2 — mostly non-functional)
├── griffin_reflex/.../components/*   Many orphans + mock widgets
├── griffin_reflex/.../pages/*        Dashboard/workspace/projects/settings shells
└── backend/*                         Unused stubs for Phases 5–8

PLAN DOC
└── imp.md                          Phases 1–8 design conversation (aspirational)
```

---

## 9. Verdict

**Has the V2 plan been implemented?**  
**No — only scaffolded.** Roughly:

| Phases | Implementation quality |
|--------|------------------------|
| 1–3 UI files | ~40% of *files* exist, ~10% *functional* |
| 4–5 SaaS | ~5% (stubs only) |
| 6–8 Intelligence / autonomous | ~0% real; mocks only |
| Original Griffin science stack | ~solid and still the real product |

**What is not in the UI / not working / not integrated:** almost the entire V2 product layer (copilot, live agents, discovery feed, agent monitor, reports library, auth, WebSockets, autonomous research, real knowledge graph explorer, multi-user labs).  

**What is working:** the original multi-agent research pipeline and the main Reflex + Streamlit workbenches that drive `src/`.

Several **real bugs** in the main Reflex app mean UI controls (fresh fetch, agent override, collector limits, refinement, think mode) look active but do not affect execution.
