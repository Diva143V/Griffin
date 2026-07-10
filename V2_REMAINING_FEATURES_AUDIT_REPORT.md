# Griffin V2 Remaining Features Audit Report

**Date:** 2026-07-10  
**Branch:** `arena/019f4b3c-griffin`  
**Scope:** Orphan components, backend stubs, missing infrastructure, and gaps vs. `imp.md` Phases 2–8

---

## Executive Summary

| Layer | Verdict | Reality |
|-------|---------|---------|
| **Orphan components** (8 files) | 🔴 **Non-functional / unused** | Exist on disk but never imported by any page |
| **Backend stubs** (14 files) | 🔴 **Non-functional / unused** | No FastAPI app mounts them; no real logic; mocks only |
| **Infrastructure** (Docker, DB, etc.) | 🔴 **Missing** | No `docker-compose.yml`, no DB models, no Neo4j/Qdrant/Postgres |
| **Design system** | 🟡 **Partial** | `styles/theme.py` exists but is never imported |
| **SaaS / multi-user** | 🔴 **Not implemented** | Auth returns static JWT; no user DB; no lab/project persistence |
| **Autonomous mode** | 🔴 **Not implemented** | Scheduler sleeps forever; planner returns hard-coded task list |

**Bottom line:** The V2 "product" scaffolding from `imp.md` (Phases 2–8) is **largely unimplemented as working code**. The repo contains file stubs and hard-coded demo strings, but nothing is wired to the real `src/` pipeline or to any persistent backend.

---

## 1. Orphan Components (never imported by any page)

These files exist in `griffin_reflex/components/` but **zero pages import them**.

### 1.1 `activity.py`
- **What it claims:** Live activity feed showing last 5 log events
- **Reality:** Imports `State.logs` and tries `State.logs.reverse()[:5]`. `list.reverse()` returns `None`, so this would crash if ever rendered.
- **Bug:** `State.logs.reverse()[:5]` is a runtime error (`TypeError: 'NoneType' object is not subscriptable`).
- **Used by:** None
- **Verdict:** 🔴 Broken stub

### 1.2 `agent_animation.py`
- **What it claims:** Animated thinking agent card with pulse animation
- **Reality:** Static emoji box with no animation hook; `font_size` prop uses old Reflex API syntax (`font_size="45px"` instead of `size="9"` or style dict).
- **Used by:** None
- **Verdict:** 🔴 Non-functional stub

### 1.3 `agent_monitor.py`
- **What it claims:** Real-time agent status monitor
- **Reality:** Reads `State.agent_statuses` (which exists and works in the main app). This component would actually function if imported, but it is not used anywhere.
- **Used by:** None
- **Verdict:** 🟡 Functional but orphan

### 1.4 `copilot.py`
- **What it claims:** AI Copilot floating panel for evidence questions
- **Reality:** Hard-coded greeting message; input field has no `value`/`on_change` binding; Send button has no `on_click`. Completely static.
- **Used by:** None
- **Verdict:** 🔴 Non-functional stub

### 1.5 `discovery_feed.py`
- **What it claims:** Autonomous discovery feed with Accept/Review buttons
- **Reality:** Reads `State.consensus_report` (real data), but has hard-coded `value=92` progress. **Critical bug:** `on_click=rx.redirect("/reports")` — the `/reports` route does **not exist** in the app.
- **Used by:** None
- **Verdict:** 🔴 Broken redirect + hard-coded demo data

### 1.6 `graph.py`
- **What it claims:** Interactive scientific interaction map
- **Reality:** Static ASCII-like text showing `Metformin → AMPK → mTOR`. No interactivity, no real data.
- **Used by:** None
- **Verdict:** 🔴 Hard-coded mock

### 1.7 `live_agents.py`
- **What it claims:** Live AI scientist execution stream
- **Reality:** Reads `State.logs` and renders them. Would work if imported, but is not.
- **Used by:** None
- **Verdict:** 🟡 Functional but orphan

### 1.8 `reports.py`
- **What it claims:** Scientific reports library with compiled PDF/DOCX summaries
- **Reality:** Hard-coded list of 3 fake reports (`"Metformin Oncology Study"`, `"92%"`, etc.). No file system access, no real reports.
- **Used by:** None
- **Verdict:** 🔴 Hard-coded mock

### Orphan component summary

| Component | Real data? | Interactive? | Bugs | Verdict |
|-----------|-----------|--------------|------|---------|
| activity.py | Partial (reads State.logs) | No | `list.reverse()` returns None | 🔴 Broken |
| agent_animation.py | No | No | Old API syntax | 🔴 Stub |
| agent_monitor.py | Yes | No | None | 🟡 Orphan |
| copilot.py | No | No | No state binding | 🔴 Stub |
| discovery_feed.py | Partial | No | Redirect to missing `/reports` | 🔴 Broken |
| graph.py | No | No | None | 🔴 Mock |
| live_agents.py | Yes | No | None | 🟡 Orphan |
| reports.py | No | No | None | 🔴 Mock |

---

## 2. Backend Stubs (never imported by any code outside `backend/`)

These files exist in `backend/` but **nothing imports them** — not the Reflex app, not the CLI, not the Streamlit app.

### 2.1 `backend/agents/citation.py`
- **Claim:** Citation verification agent
- **Reality:** `CitationAgent.verify()` always returns `{"verified": True, "source": "PubMed", "confidence_score": 0.98}` regardless of input.
- **Real equivalent:** `src/agents/peer_review_agent.py` + `src/agents/validation_agent.py` (actually used)
- **Verdict:** 🔴 Mock stub

### 2.2 `backend/agents/experiment.py`
- **Claim:** Experiment planning agent
- **Reality:** Always returns the same MCF7/Metformin plan regardless of hypothesis input.
- **Real equivalent:** `src/agents/experiment_agent.py` + `src/core/experiment_planner.py` (actually used)
- **Verdict:** 🔴 Mock stub

### 2.3 `backend/agents/hypothesis.py`
- **Claim:** Novel hypothesis generation
- **Reality:** Returns a hard-coded string about Metformin/AMPK/T-cell exhaustion regardless of input evidence.
- **Real equivalent:** `src/agents/refinement_agent.py` can refine hypotheses; no dedicated hypothesis agent in `src/`.
- **Verdict:** 🔴 Mock stub

### 2.4 `backend/api/agents.py`
- **Claim:** WebSocket agent stream endpoint
- **Reality:** Defines a FastAPI WebSocket route that sends 4 hard-coded steps with 0.5s sleep.
- **Critical gap:** No FastAPI app exists to mount this router. `include_router` is never called anywhere in the repo.
- **Verdict:** 🔴 Orphan router

### 2.5 `backend/api/auth.py`
- **Claim:** User authentication system
- **Reality:** Returns static `"jwt-token"` for any email/password. No password hashing, no DB lookup.
- **Critical gap:** No FastAPI app mounts this router. No login UI calls this endpoint.
- **Verdict:** 🔴 Insecure mock stub

### 2.6 `backend/autonomous/planner.py`
- **Claim:** Research planner that decomposes objectives into tasks
- **Reality:** Returns a hard-coded list of 5 task dicts regardless of objective.
- **Verdict:** 🔴 Mock stub

### 2.7 `backend/autonomous/research_loop.py`
- **Claim:** Autonomous research loop
- **Reality:** Returns a hard-coded list of 5 strings regardless of objective.
- **Verdict:** 🔴 Mock stub

### 2.8 `backend/autonomous/scheduler.py`
- **Claim:** Nightly autonomous research scheduler
- **Reality:** `asyncio.sleep(86400)` loop with `print()` statements. Never started by any entry point.
- **Verdict:** 🔴 Non-running stub

### 2.9 `backend/control/human_review.py`
- **Claim:** Human approval checkpoint
- **Reality:** Always returns `{"status": "awaiting_review"}`. No actual approval flow.
- **Verdict:** 🔴 Mock stub

### 2.10 `backend/memory/research_graph.py`
- **Claim:** Agent memory graph for scientific knowledge
- **Reality:** Simple in-memory dict-of-lists. No graph traversal, no persistence.
- **Note:** Old audit reported `NameError: Any`; this is now fixed (imports `Any` from `typing`).
- **Verdict:** 🟡 Functional in-memory stub, but unused

### 2.11 `backend/memory/user_memory.py`
- **Claim:** Persistent user memory
- **Reality:** In-memory dict. Lost on process restart. No DB backing.
- **Verdict:** 🔴 Non-persistent stub

### 2.12 `backend/reasoning/contradiction.py`
- **Claim:** Contradiction resolution engine
- **Reality:** Pairs every claim with every other claim and always says reason is "Different patient population or dosing methodology".
- **Real equivalent:** `src/core/contradiction_detector.py` + `src/agents/contradiction_agent.py` (actually used)
- **Verdict:** 🔴 Toy stub

### 2.13 `backend/reasoning/graphrag.py`
- **Claim:** GraphRAG reasoning engine
- **Reality:** Contains `MockVectorDB`, `MockGraphDB`, `MockLLM` classes that return hard-coded Metformin/AMPK data. The `GraphRAG.reason()` method ignores the actual question and returns the same mock synthesis.
- **Real equivalent:** `src/core/graph_rag.py` (actually used by Benchmark tab)
- **Verdict:** 🔴 Mock stub

### 2.14 `backend/scoring/discovery.py`
- **Claim:** Scientific discovery scoring
- **Reality:** Simple weighted average formula. Not called by anything.
- **Verdict:** 🔴 Orphan formula

### 2.15 `backend/writer/scientific_writer.py`
- **Claim:** Automatic literature review writer
- **Reality:** Returns hard-coded section strings about Metformin regardless of evidence input.
- **Real equivalent:** `src/agents/report_agent.py` + `src/agents/consensus_agent.py` (actually used)
- **Verdict:** 🔴 Mock stub

### Backend stub summary

| File | Claim | Reality | Imported? | Verdict |
|------|-------|---------|-----------|---------|
| citation.py | Verify citations | Always `verified: True` | No | 🔴 |
| experiment.py | Design experiments | Hard-coded MCF7 plan | No | 🔴 |
| hypothesis.py | Generate hypotheses | Hard-coded Metformin text | No | 🔴 |
| api/agents.py | WebSocket stream | 4 fake steps, no app mounts it | No | 🔴 |
| api/auth.py | JWT auth | Static token, no DB | No | 🔴 |
| autonomous/planner.py | Task decomposition | 5 hard-coded tasks | No | 🔴 |
| autonomous/research_loop.py | Autonomous loop | 5 hard-coded strings | No | 🔴 |
| autonomous/scheduler.py | Nightly scheduler | Sleep loop, never started | No | 🔴 |
| control/human_review.py | Approval flow | Always `awaiting_review` | No | 🔴 |
| memory/research_graph.py | Knowledge graph | In-memory dict | No | 🟡 |
| memory/user_memory.py | User memory | In-memory dict | No | 🔴 |
| reasoning/contradiction.py | Contradiction resolver | Naïve O(n²) pairs | No | 🔴 |
| reasoning/graphrag.py | GraphRAG engine | Mock classes only | No | 🔴 |
| scoring/discovery.py | Discovery score | Weighted avg formula | No | 🔴 |
| writer/scientific_writer.py | Review writer | Hard-coded sections | No | 🔴 |

---

## 3. Missing Infrastructure

| Item | `imp.md` claim | Reality | Verdict |
|------|---------------|---------|---------|
| `docker-compose.yml` | Postgres + Qdrant + Neo4j + Frontend + Backend | **Missing entirely** | 🔴 |
| FastAPI app entrypoint | `backend/api/` routers mounted | No `FastAPI()` instance exists anywhere | 🔴 |
| DB models | SQLAlchemy `User`, `Lab`, `Project`, `Experiment` | **Missing entirely** | 🔴 |
| DB connection layer | `backend/database/connection.py` | **Missing entirely** | 🔴 |
| PostgreSQL | Production persistence | Not present | 🔴 |
| Qdrant | Vector DB | Not present (Chroma used in real pipeline) | 🔴 |
| Neo4j | Graph DB | Not present (NetworkX used in real pipeline) | 🔴 |
| `reflex-cytoscape` | Interactive graph UI | Not installed; Plotly used instead | 🟡 |

---

## 4. Design System

| Item | Status | Evidence |
|------|--------|----------|
| `styles/theme.py` | 🟡 Exists but unused | Defines `COLORS` and `glass()`; **never imported** by any component or page |
| Main app design tokens | ✅ Functional | `griffin_reflex.py` has its own inline `_FONT`, `_CARD_BG`, `_PAGE_BG`, etc. that power the real UI |

The V2 design system from `imp.md` was not adopted; the main app uses its own embedded tokens.

---

## 5. Gaps vs. `imp.md` Phase-by-Phase

### Phase 2 — Agent graph, evidence cards, copilot
| Feature | Status | Note |
|---------|--------|------|
| Animated multi-agent view | 🔴 Missing | `agent_animation.py` is a static emoji box |
| Evidence intelligence cards | 🟡 Partial | Real evidence is in main app Tab 4; no V2 component |
| AI copilot floating panel | 🔴 Broken | `copilot.py` has no state binding |
| Live agent stream | 🟡 Orphan | `live_agents.py` works but is unused |

### Phase 3 — Knowledge intelligence
| Feature | Status | Note |
|---------|--------|------|
| Knowledge graph explorer | 🟡 Real data now | Workspace `/workspace` uses real `contradictions.json`; the old `components/graph.py` mock is unused |
| Research timeline | 🟡 Real data now | Workspace uses real paper years; old `components/timeline.py` hard-coded events replaced |
| Paper explorer | 🟡 Real data now | Workspace uses real CSVs; old `components/paper_explorer.py` hard-coded papers replaced |
| `reflex-cytoscape` | 🔴 Not used | Plotly used in main app and workspace |

### Phase 4 — Streaming, projects, accounts, PDF UI
| Feature | Status | Note |
|---------|--------|------|
| Real-time agent animation | 🔴 No | No WebSocket connection from UI |
| Streaming AI responses | 🔴 No | Chat waits for full Ollama reply |
| Project management UI | 🟡 Honest stub | `/projects` shows local run data + disclaimer |
| User accounts | 🔴 No | Auth stub unused |
| DB-backed workspace | 🔴 No | All data is file-based (`dataset/`) |
| Report generation UI | 🔴 Mock | `reports.py` orphan with fake data |

### Phase 5 — SaaS architecture
| Feature | Status | Note |
|---------|--------|------|
| FastAPI auth | 🔴 Stub | Router exists but not mounted |
| WebSocket agent stream | 🔴 Stub | Router exists but not mounted |
| Labs / Projects / Experiments DB | 🔴 Missing | No models, no Postgres |
| User memory | 🔴 In-memory stub | `UserMemory` class unused |
| `docker-compose.yml` | 🔴 Missing | |
| PostgreSQL / Qdrant / Neo4j | 🔴 Missing | |

### Phase 6 — AI Scientist intelligence
| Feature | Status | Note |
|---------|--------|------|
| GraphRAG reasoning engine | 🔴 Mock | `backend/reasoning/graphrag.py` uses mock classes |
| Hypothesis generation | 🔴 Mock | `backend/agents/hypothesis.py` hard-coded |
| Experiment planning | 🔴 Mock | `backend/agents/experiment.py` hard-coded |
| Literature review writer | 🔴 Mock | `backend/writer/scientific_writer.py` hard-coded |
| Citation verification | 🔴 Mock | `backend/agents/citation.py` always returns True |
| Autonomous research loop | 🔴 Stub | `backend/autonomous/research_loop.py` hard-coded |

> **Important:** Real versions of these capabilities **do exist** under `src/agents/` and `src/core/`. The V2 `backend/` copies are non-functional duplicates.

### Phase 7 — Premium product UX
| Feature | Status | Note |
|---------|--------|------|
| Onboarding page | ✅ Working | `/onboarding` saves goal to disk and redirects |
| Design system `styles/theme.py` | 🟡 Unused | File exists but main app uses inline tokens |
| Activity feed | 🔴 Broken | `activity.py` has `list.reverse()` bug |
| Notifications | 🔴 Missing | |
| Team collaboration | 🔴 Missing | |
| Production monitoring | 🔴 Missing | |

### Phase 8 — Autonomous mode
| Feature | Status | Note |
|---------|--------|------|
| Research planner | 🔴 Stub | Hard-coded 5 tasks |
| Research memory graph | 🟡 In-memory stub | `ResearchMemory` class unused |
| Human approval | 🔴 Stub | Always `awaiting_review` |
| Discovery scoring | 🔴 Formula only | Unused |
| Nightly scheduler | 🔴 Stub | Infinite sleep, never started |
| Discovery feed UI | 🔴 Broken | Redirects to missing `/reports` route |
| Personality layer | 🔴 Missing | |

---

## 6. Concrete Bugs in Orphan / Stub Code

### Bug 1: `activity.py` — `list.reverse()` returns `None`
**File:** `griffin_reflex/components/activity.py:7`  
**Code:** `State.logs.reverse()[:5]`  
**Impact:** Would raise `TypeError: 'NoneType' object is not subscriptable` if rendered.  
**Fix:** Use `State.logs[-5:]` or `list(reversed(State.logs))[:5]`.

### Bug 2: `discovery_feed.py` — redirect to non-existent route
**File:** `griffin_reflex/components/discovery_feed.py:19`  
**Code:** `rx.button("Open Report", on_click=rx.redirect("/reports"))`  
**Impact:** Clicking would 404. No `app.add_page(..., route="/reports")` exists.  
**Fix:** Remove redirect or create `/reports` page backed by real generated reports.

### Bug 3: `copilot.py` — uncontrolled input
**File:** `griffin_reflex/components/copilot.py:22`  
**Code:** `rx.input(placeholder="Ask copilot...", size="1", style={"flex": 1})`  
**Impact:** Input has no `value`/`on_change` binding; Send button has no `on_click`. Completely non-interactive.  
**Fix:** Add state bindings and wire to RAG chat backend.

### Bug 4: `agent_animation.py` — old Reflex API syntax
**File:** `griffin_reflex/components/agent_animation.py:8`  
**Code:** `rx.text("🧬", font_size="45px")`  
**Impact:** May not render correctly in current Reflex versions (prop should be `size` or inside `style`).  
**Fix:** Use `style={"fontSize": "45px"}`.

---

## 7. What is "implemented in files" vs "working end-to-end"

```
imp.md claim                          File exists?   Wired to UI?   Calls real science?
─────────────────────────────────────────────────────────────────────────────────────
Glass dashboard                       Yes            Yes (V2)       Yes (data_layer)
Sidebar nav                           Yes            Yes (V2)       N/A
Knowledge graph explorer              Yes            Workspace      Yes (real data)
Paper explorer                        Yes            Workspace      Yes (real data)
Timeline                              Yes            Workspace      Yes (real data)
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

## 8. Recommendations

### A. Clean up orphan components (low effort, high clarity)
1. **Delete** `components/graph.py`, `components/reports.py`, `components/copilot.py` — they are pure mocks with no path to real data.
2. **Fix or delete** `components/activity.py` — fix the `list.reverse()` bug, or delete if not needed.
3. **Fix or delete** `components/discovery_feed.py` — fix the `/reports` redirect, or delete.
4. **Integrate** `components/agent_monitor.py` and `components/live_agents.py` into the main Planner tab if you want live agent status/logs display.

### B. Decide the fate of `backend/` (medium effort)
**Option 1 — Delete:** The real scientific logic already lives in `src/agents/` and `src/core/`. The `backend/` stubs add confusion and duplicate names.

**Option 2 — Wrap:** Replace each stub with a thin wrapper that calls the real `src/` implementation:
- `backend/reasoning/graphrag.py` → import `src.core.graph_rag`
- `backend/agents/experiment.py` → import `src.agents.experiment_agent`
- etc.

**Option 3 — Mount:** Create a real FastAPI app, mount the routers, and connect the WebSocket to the actual pipeline events. Only do this if you need a separate API backend (Reflex already handles the UI).

### C. Do not add infrastructure before data logic (high priority)
- Do **not** add `docker-compose.yml`, PostgreSQL, Neo4j, or Qdrant until the V2 pages actually need them.
- The current file-based `dataset/` approach is sufficient for single-user local mode and is working.
- If you move to multi-user SaaS, add auth + DB **after** the UI is fully functional, not before.

### D. Design system consolidation (low effort)
- Either delete `styles/theme.py` (since the main app uses inline tokens) or migrate the inline tokens into `theme.py` and import it.

---

## 9. Verdict

| Area | Score | Summary |
|------|-------|---------|
| **Orphan components** | 2/8 functional | Most are hard-coded mocks; 2 would work if imported; 2 have runtime bugs |
| **Backend stubs** | 1/15 functional | `ResearchMemory` is the only non-broken class, and it is unused |
| **Infrastructure** | 0/7 present | No Docker, no DB, no FastAPI app |
| **Design system** | 1/2 | `theme.py` exists but is ignored |
| **SaaS readiness** | 0/5 | No auth, no multi-user, no persistence |
| **Autonomous mode** | 0/5 | All stubs, no actual automation |

**Bottom line:** P0 and P1 are solid. Everything beyond that (Phases 2–8 from `imp.md`) is **scaffolded but not functional**. The repo has files on disk that look like a SaaS product, but they are disconnected demos. The real working product is the original `src/` pipeline + the main Reflex workbench at `/`.
