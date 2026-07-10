"""Central Ollama client: keep-alive, token limits, and task-based presets.

Every agent imports `chat` from here instead of calling `ollama.chat` directly.
This guarantees models stay warm (keep_alive) and that each task uses sensible
sampling defaults, while still honouring the Streamlit sidebar overrides.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import ollama

# Keep models resident in VRAM/RAM between calls so we avoid 10-30s cold reloads.
DEFAULT_KEEP_ALIVE = "30m"

# Task-based generation presets.
# - Low temperature for deterministic extraction / classification / JSON.
# - Moderate temperature for synthesis / protocols.
TASK_PRESETS: Dict[str, Dict[str, Any]] = {
    "extract":   {"temperature": 0.1, "top_p": 0.8, "num_predict": 1024},
    "classify":  {"temperature": 0.1, "top_p": 0.9, "num_predict": 512},
    "route":     {"temperature": 0.0,                       "num_predict": 256},
    "synthesis": {"temperature": 0.4, "top_p": 0.9, "num_predict": 4096},
    "consensus": {"temperature": 0.3, "top_p": 0.9, "num_predict": 3072},
    "protocol":  {"temperature": 0.3, "top_p": 0.9, "num_predict": 4096},
    "chat":      {"temperature": 0.6, "top_p": 0.9, "num_predict": 2048},
}


def resolve_options(
    task: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge task preset < user sidebar overrides < explicit per-call options."""
    preset = TASK_PRESETS.get(task) if task in TASK_PRESETS else TASK_PRESETS["chat"]
    base: Dict[str, Any] = dict(preset)
    if user_overrides:
        for k in ("temperature", "num_ctx", "top_p", "num_predict"):
            v = user_overrides.get(k)
            if v is not None:
                base[k] = v

    if options:
        base.update(options)

    # 'think' is a top-level ollama.chat kwarg on some models, not an options field
    base.pop("think", None)
    base.setdefault("num_predict", 4096)
    return base


def chat(
    model: str,
    messages: List[Dict[str, Any]],
    task: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    user_options: Optional[Dict[str, Any]] = None,
    keep_alive: str = DEFAULT_KEEP_ALIVE,
    **kwargs,
):
    """Drop-in replacement for ollama.chat() with keep_alive + presets baked in.

    If user_options contains ``think: True``, it is forwarded as a top-level
    argument for models that support Ollama thinking mode (ignored by others).
    """
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
