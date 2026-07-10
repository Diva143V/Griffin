# Griffin V2 P0 + P1 Audit Report

**Date:** 2026-07-10  
**Branch:** `arena/019f4b3c-griffin` (based on `35e5d296`)  
**Scope:** Pipeline control wiring (P0) and unified nav + live dataset-driven pages (P1)

---

## Executive Summary

| Criterion | Verdict |
|-----------|---------|
| **P0 — Pipeline controls reach the backend** | **PASS** (all 7 sub-criteria) |
| **P1 — Unified nav + live Dashboard/Workspace** | **PASS** (all 6 sub-criteria) |

**Bottom line:** The P0/P1 fixes are **real and end-to-end**. UI controls are no longer cosmetic; they propagate through environment variables into `run_pipeline_cli.py` and arrive as kwargs in `execute_query_plan`. The V2 shell pages (`/dashboard`, `/workspace`, `/projects`, `/settings`, `/onboarding`) are wired to `dataset/` artifacts via `data_layer.py`, not hard-coded mocks.

> **Note:** A previous audit (`V2_AUDIT_REPORT.md`) predates these fixes and lists several issues that are now resolved. This report supersedes it for P0/P1 scope.

---

## P0 — Pipeline Control Wiring

### P0-1: force_fresh ✅ PASS

**Evidence:**
- UI checkbox bound to `State.force_fresh` with `on_change=State.set_force_fresh`  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:380`
- `execute_backend_pipeline` sets env var:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1119`
  ```python
  env["GRIFFIN_FORCE_FRESH"] = "1" if self.force_fresh else "0"
  ```
- `run_pipeline_cli.py` reads it (defaults to `True` only when **unset** to preserve backward-compat):  
  `run_pipeline_cli.py:43`
  ```python
  force_fresh = _env_bool("GRIFFIN_FORCE_FRESH", default=True)
  ```
- Passed into `execute_query_plan(..., force_fresh=force_fresh)`:  
  `run_pipeline_cli.py:113`
- `execute_query_plan` uses it to skip cache:  
  `src/agents/query_planner.py:470`
  ```python
  if force_fresh:
      is_present = False
      check_msg = "Force fresh retrieval requested. Ignoring database cache."
  ```

**Wiring simulation:** Setting `GRIFFIN_FORCE_FRESH=0` in env causes `_env_bool` to return `False`, which reaches `execute_query_plan` and bypasses the Chroma-DB short-circuit.

---

### P0-2: manual agent selection ✅ PASS

**Evidence:**
- UI checkboxes update `State.sel_*` booleans and `State.use_manual_agents`  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:382-389`
- `execute_backend_pipeline` builds comma list and sets `GRIFFIN_FORCED_AGENTS`:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1100-1116`
  ```python
  if self.use_manual_agents:
      fa = []
      if self.sel_claim_extractor: fa.append("claim_extractor")
      ...
      forced_agents = ",".join(fa)
  ```
  ```python
  if forced_agents:
      env["GRIFFIN_FORCED_AGENTS"] = forced_agents
  else:
      env.pop("GRIFFIN_FORCED_AGENTS", None)
  ```
- CLI parses string into list:  
  `run_pipeline_cli.py:46-51`
  ```python
  forced_agents_raw = os.environ.get("GRIFFIN_FORCED_AGENTS", "").strip()
  forced_agents = (
      [a.strip() for a in forced_agents_raw.split(",") if a.strip()]
      if forced_agents_raw else None
  )
  ```
- Passed into `execute_query_plan(..., forced_agents=forced_agents)`:  
  `run_pipeline_cli.py:115`
- `execute_query_plan` uses the list to override the LLM router:  
  `src/agents/query_planner.py:520-524`
  ```python
  if forced_agents is not None:
      executed_agents = forced_agents
      notes.append(f"User Manually Selected Agents: {', '.join(executed_agents)}")
  ```

**Agent name mapping is consistent** between UI and executor:
| UI label | String passed |
|----------|---------------|
| Claim Extractor | `claim_extractor` |
| Consensus | `consensus_analyst` |
| Evidence Ranker | `evidence_ranker` |
| Lab Experiment | `experiment_planner` |
| Contradiction | `contradiction_detector` |
| ELN Assistant | `eln_assistant` |
| Synthesis | `synthesis` |

---

### P0-3: collector limits ✅ PASS

**Evidence:**
- UI inputs are **controlled** (`value=…`, `on_change=…`) for all 10 sources:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:395-436` and `tab0_content()` around line 1545
- State stores raw strings and coerces to `int` via `_collector_limits_int()`:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:438-445`
  ```python
  def _collector_limits_int(self) -> dict[str, int]:
      out: dict[str, int] = {}
      for k, v in (self.collector_limits or {}).items():
          try:
              out[k] = max(0, int(float(str(v))))
          except Exception:
              out[k] = 20
      return out
  ```
- `execute_backend_pipeline` serializes and sets env:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1121`
  ```python
  env["GRIFFIN_COLLECTOR_LIMITS"] = json.dumps(self._collector_limits_int())
  ```
- CLI parses JSON and validates type:  
  `run_pipeline_cli.py:53-56`
  ```python
  collector_limits = _env_json("GRIFFIN_COLLECTOR_LIMITS", None)
  if collector_limits is not None and not isinstance(collector_limits, dict):
      collector_limits = None
  ```
- Passed into `execute_query_plan(..., collector_limits=collector_limits)`:  
  `run_pipeline_cli.py:116`
- `execute_query_plan` forwards to ingestion:  
  `src/agents/query_planner.py:483`
  ```python
  ingest_logs = run_pipeline_ingestion(..., collector_limits=collector_limits)
  ```
- `run_pipeline_ingestion` passes `--collector-limits` to `build_dataset.py`:  
  `src/agents/query_planner.py:260-270`
- `build_dataset.py` applies per-source limits:  
  `build_dataset.py:35-55`
  ```python
  custom_limit = limits.get(spec.name, args.max_results)
  if spec.name == "PubMed":
      args.pubmed_batch_size = custom_limit
  elif spec.name == "PMC":
      args.pmc_page_size = custom_limit
  ...
  ```

---

### P0-4: refinement instruction ✅ PASS

**Evidence:**
- Confirm dialog captures `State.refinement_instruction` with controlled input:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1566-1572`
- `execute_backend_pipeline` sets env when non-empty:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1122-1126`
  ```python
  if (self.refinement_instruction or "").strip():
      env["GRIFFIN_REFINEMENT"] = self.refinement_instruction.strip()
  else:
      env.pop("GRIFFIN_REFINEMENT", None)
  ```
- CLI reads and **prepends to query before planning**:  
  `run_pipeline_cli.py:38-41`
  ```python
  refinement = os.environ.get("GRIFFIN_REFINEMENT", "").strip()
  if refinement:
      query = f"{query} (Refinement: {refinement})"
  ```
- `build_query_plan` receives the modified query:  
  `run_pipeline_cli.py:95`
  ```python
  plan = build_query_plan(query, resolved, default_top_k=10)
  ```

The refinement is therefore applied **before** the planner builds the query plan, affecting search keywords and agent routing.

---

### P0-5: llm_think ✅ PASS

**Evidence:**
- UI checkbox bound to `State.llm_think`:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:378`
- Sidebar chat **and** pipeline both include `think` in the options dict sent to env:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1091-1098`
  ```python
  env["GRIFFIN_LLM_OPTS"] = json.dumps(
      {
          "temperature": self.llm_temperature,
          "num_ctx": int(self.llm_num_ctx),
          "num_predict": int(self.llm_num_predict),
          "think": bool(self.llm_think),
      }
  )
  ```
- CLI forwards `llm_options` to `execute_query_plan`:  
  `run_pipeline_cli.py:117`
- `execute_query_plan` passes `llm_options` to every agent LLM call:  
  `src/agents/query_planner.py:569`, `605`, `615`, `640`
- **`src/shared/llm.py` forwards `think` as a top-level `ollama.chat` kwarg** (not stripped forever):  
  `src/shared/llm.py:62-70`
  ```python
  call_kwargs = dict(kwargs)
  think_flag = call_kwargs.pop("think", None)
  if think_flag is None and user_options and "think" in user_options:
      think_flag = bool(user_options.get("think"))
  if think_flag is not None:
      call_kwargs["think"] = think_flag

  return ollama.chat(
      model=model,
      messages=messages,
      options=resolve_options(task, options, user_options),
      keep_alive=keep_alive,
      **call_kwargs,
  )
  ```
- `resolve_options` **only strips `think` from the `options` dict** (where it is invalid), preserving it for top-level forwarding:  
  `src/shared/llm.py:52`
  ```python
  base.pop("think", None)
  ```

**Runtime simulation verified:** `chat(model, messages, user_options={"think": True})` returns a call payload containing `think=True` at the top level, not inside `options`.

---

### P0-6: pipeline results surfaced in UI ✅ PASS

**Evidence:**
- After pipeline run, `run_query_planner` loads `dataset/execution_trace.json` and populates trace fields:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1000-1080`
- Surfaced in `tab0_content()` (Planner tab) when `State.pipeline_trace_visible` is `True`:
  - **Verification status + trace** — badge + foreach loop over `State.verification_trace`  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1589-1614`
  - **Routing stats** — `rx.data_table` with columns `Stage, Requested, Resolved, Latency, Status`  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1616`
  - **Retrieved sources** — foreach over `State.fetched_sources` showing title, score, study design, abstract  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1618-1640`
  - **Matched claims** — foreach over `State.matched_claims` showing claim, stance, title  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1642-1664`
  - **Consensus report** — `State.consensus_report` (markdown card)  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1587`
  - **Experiment protocol** — `State.experiment_protocol` (markdown card)  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1666`
  - **ELN entry** — `State.eln_entry` (markdown card)  
    `griffin_reflex/griffin_reflex/griffin_reflex.py:1668`
- **Benchmark tab** renders sources and graph relations:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1876-1924`
  - `std_sources_data` rendered when `length() > 0`
  - `graph_sources_data` rendered when `length() > 0`
  - `graph_relations_data` rendered when `length() > 0`

---

### P0-7: graph empty state ✅ PASS

**Evidence:**
- `State.graph_loaded` is an explicit boolean flag, default `False`:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:178`
- `load_knowledge_graph` sets it based on whether `_graph_sync` returned a figure:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1422-1429`
  ```python
  fig = await loop.run_in_executor(None, _graph_sync)
  if fig is not None:
      self.graph_figure = fig
      self.graph_loaded = True
  else:
      self.graph_loaded = False
  ```
- `tab3_content` uses `rx.cond(State.graph_loaded, ...)` to show either the Plotly card or the empty-state card:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1702-1719`

The old bug (`rx.cond(State.graph_figure, ...)`) has been replaced with the explicit flag.

---

## P1 — Unified Navigation + Live Dataset Pages

### P1-1: unified navigation ✅ PASS

**Evidence:**
- Shared sidebar (`components/sidebar.py`) routes:  
  `griffin_reflex/griffin_reflex/components/sidebar.py:8-14`
  ```python
  MENU = [
      ("🏠", "Dashboard", "/dashboard"),
      ("🧭", "Planner", "/"),
      ("🧬", "Workspace", "/workspace"),
      ("🧪", "Labs", "/projects"),
      ("⚙️", "Settings", "/settings"),
  ]
  ```
- All V2 pages import this sidebar and pass their active route:  
  `dashboard.py`, `workspace.py`, `projects.py`, `settings.py`
- Main Planner (`/`) links out to V2 pages in the top nav strip:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:1966-1973`
  ```python
  rx.link(rx.button("Dashboard", ...), href="/dashboard"),
  rx.link(rx.button("Workspace", ...), href="/workspace"),
  rx.link(rx.button("Labs", ...), href="/projects"),
  rx.link(rx.button("Settings", ...), href="/settings"),
  ```
- App page registration matches:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:2044-2066`
  - `/` → Planner
  - `/dashboard` → Dashboard
  - `/workspace` → Workspace
  - `/projects` → Labs
  - `/settings` → Settings
  - `/onboarding` → Onboarding

**No redirect collisions:** Settings does **not** redirect to `/workspace`; each route is distinct.

---

### P1-2: live Dashboard (not hard-coded metrics) ✅ PASS

**Evidence:**
- `DashboardState.load_metrics` calls `data_layer.get_dashboard_metrics()`:  
  `griffin_reflex/griffin_reflex/pages/dashboard.py:18-29`
- `get_dashboard_metrics` reads real `dataset/` artifacts:  
  `griffin_reflex/griffin_reflex/data_layer.py:40-130`
  - `papers` → counts rows in `clean_papers.csv`, `ranked_papers.csv`, or `clean_papers_with_embeddings.csv`
  - `evidence_score` → mean of `evidence_score` or `score` column in `ranked_papers.csv`, expressed as % of 10
  - `contradictions` → length of `contradictions` list in `contradictions.json`
  - `claims` → row count of `claims.csv` or `claims_dataset.csv`
  - `agents` → count of `executed_agents` from `execution_trace.json`
  - `goal` → content of `last_research_goal.txt`
  - `progress` → derived heuristic (0 → 25 → 45 → 70 → 100) based on which artifacts exist
  - `pipeline_status` → string derived from artifact presence

- Empty dataset shows zeros / idle messaging:
  - `papers` defaults to `"0"`
  - `goal` defaults to `"No active research run yet"`
  - `pipeline_status` defaults to `"Idle — run a query from the Planner"`

**No hard-coded demo numbers** like `"250"` or `"92%"` were found in Dashboard code. (The only `"92%"` found in the repo is in the orphan `reports.py` component, which is never rendered on any page.)

---

### P1-3: live Workspace ✅ PASS

**Evidence:**
- `WorkspaceState.load_workspace` calls `data_layer` helpers:  
  `griffin_reflex/griffin_reflex/pages/workspace.py:22-28`
  ```python
  self.papers = get_papers(limit=24, search=self.paper_search)
  nodes, edges = get_knowledge_graph()
  self.kg_nodes = nodes
  self.kg_edges = edges
  self.timeline = get_timeline_events()
  ```
- `get_papers` reads `ranked_papers.csv`, `clean_papers_with_embeddings.csv`, or `clean_papers.csv`:  
  `griffin_reflex/griffin_reflex/data_layer.py:133-174`
- `get_knowledge_graph` reads `contradictions.json` and builds nodes/edges from real claim titles:  
  `griffin_reflex/griffin_reflex/data_layer.py:177-215`
- `get_timeline_events` reads paper years and contradiction counts:  
  `griffin_reflex/griffin_reflex/data_layer.py:218-252`
- Search works: `paper_explorer_view` receives `search_var`, `on_search`, and `on_refresh` callbacks; `WorkspaceState.search_papers` re-calls `get_papers` with the search term:  
  `griffin_reflex/griffin_reflex/pages/workspace.py:30-31`
- Empty states explain "run Planner first":
  - Papers: `"No papers found. Run the Planner to collect and rank literature."`  
    `griffin_reflex/griffin_reflex/components/paper_explorer.py:78-85`
  - KG: `"No graph data yet. Run Planner + contradiction analysis to populate dataset/contradictions.json."`  
    `griffin_reflex/griffin_reflex/components/knowledge_graph.py:62-69`
  - Timeline: returns `"No dataset yet. Run the Planner to collect literature."` via `data_layer.py:247-250`

---

### P1-4: onboarding goal persistence ✅ PASS

**Evidence:**
- `/onboarding` saves goal to disk:  
  `griffin_reflex/griffin_reflex/pages/onboarding.py:16-19`
  ```python
  def start(self):
      goal = (self.research_goal or "").strip()
      if goal:
          save_research_goal(goal)
      return rx.redirect("/")
  ```
- `save_research_goal` writes `dataset/last_research_goal.txt`:  
  `griffin_reflex/griffin_reflex/data_layer.py:255-258`
- Dashboard shows the goal via `get_dashboard_metrics` (which reads the same file):  
  `griffin_reflex/griffin_reflex/data_layer.py:91-100`
- Planner prefills query when empty on load:  
  `griffin_reflex/griffin_reflex/griffin_reflex.py:384-395`
  ```python
  @rx.event
  async def on_load(self):
      ...
      if not (self.query or "").strip():
          goal_path = os.path.join(DATASET_DIR, "last_research_goal.txt")
          if os.path.exists(goal_path):
              try:
                  with open(goal_path, "r", encoding="utf-8") as gf:
                      g = gf.read().strip()
                  if g:
                      self.query = g
              except Exception:
                  pass
  ```

---

### P1-5: Labs / Settings honesty ✅ PASS

**Evidence:**
- `/projects` explicitly states multi-lab SaaS is not implemented:  
  `griffin_reflex/griffin_reflex/pages/projects.py:38-41`
  ```python
  rx.text(
      "Local single-user workspace (multi-lab SaaS is not enabled yet). "
      "This view reflects your last pipeline run on disk.",
      color="gray",
  )
  ```
- `/projects` reflects real local data (papers count, contradictions count, goal, execution trace presence):  
  `griffin_reflex/griffin_reflex/pages/projects.py:22-28`
- `/settings` points to real Planner controls:  
  `griffin_reflex/griffin_reflex/pages/settings.py:17-29`
  ```python
  rx.text("• PubMed email, Semantic Scholar key, Gemini key → Planner left sidebar")
  rx.text("• Global / custom model routing → Planner left sidebar")
  rx.text("• Temperature, context, max tokens, thinking mode → Planner left sidebar")
  rx.text("• Per-source collector limits → Planner tab")
  rx.link(rx.button("Open Planner controls →", ...), href="/")
  ```
- `/settings` also displays the actual default model mixture (not fake names):  
  `griffin_reflex/griffin_reflex/pages/settings.py:31-39`

---

### P1-6: no broken imports ✅ PASS

**Evidence:**
- Workspace imports existing APIs:  
  `griffin_reflex/griffin_reflex/pages/workspace.py:4-6`
  ```python
  from griffin_reflex.components.knowledge_graph import knowledge_graph_view
  from griffin_reflex.components.timeline import research_timeline_view
  from griffin_reflex.components.paper_explorer import paper_explorer_view
  ```
- All three view functions exist and accept the expected signatures.
- `python -m py_compile` succeeds on all changed modules:
  - `griffin_reflex/griffin_reflex/griffin_reflex.py`
  - `griffin_reflex/griffin_reflex/pages/dashboard.py`
  - `griffin_reflex/griffin_reflex/pages/workspace.py`
  - `griffin_reflex/griffin_reflex/pages/projects.py`
  - `griffin_reflex/griffin_reflex/pages/settings.py`
  - `griffin_reflex/griffin_reflex/pages/onboarding.py`
  - `griffin_reflex/griffin_reflex/data_layer.py`
  - `griffin_reflex/griffin_reflex/components/sidebar.py`
  - `griffin_reflex/griffin_reflex/components/knowledge_graph.py`
  - `griffin_reflex/griffin_reflex/components/paper_explorer.py`
  - `griffin_reflex/griffin_reflex/components/timeline.py`
  - `run_pipeline_cli.py`
  - `src/shared/llm.py`
  - `src/agents/query_planner.py`

---

## Minor findings (not P0/P1 blockers)

| Issue | Location | Severity | Note |
|-------|----------|----------|------|
| `discovery_feed.py` redirects to `/reports` (route does not exist) | `components/discovery_feed.py:19` | Low | Component is **orphan** — never imported by any page |
| `reports.py` contains hard-coded mock reports | `components/reports.py:4-6` | Low | Component is **orphan** — never imported by any page |
| `discovery_feed.py` has hard-coded `value=92` progress | `components/discovery_feed.py:16` | Low | Orphan component |

These do **not** affect P0/P1 acceptance because they are not reachable in the running UI.

---

## Methodology

1. **Static code audit** — read all files in the control path from UI → State → env → CLI → `execute_query_plan` → `llm.chat`.
2. **Grep sweep** — searched for hard-coded metrics (`"250"`, `"92%"`, `"Metformin effect"`), orphan routes, and env var names.
3. **Wiring simulation** — ran Python snippets that replicate the env-var serialization/parsing logic without requiring a full Ollama stack or pandas install.
4. **Import check** — `python -m py_compile` on every module in the P1 path.
5. **Trace verification** — followed the data flow for each P0 control from the Reflex event handler through to the final backend consumer.

---

## Verdict

**P0: PASS** — All 7 acceptance criteria are met. The pipeline controls are fully wired end-to-end.

**P1: PASS** — All 6 acceptance criteria are met. Navigation is unified and the Dashboard/Workspace pages are driven by real `dataset/` artifacts via `data_layer.py`.
