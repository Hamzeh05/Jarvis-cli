import json
import time
from pathlib import Path

from langchain_openai import ChatOpenAI

from harness.config import (
    MODEL_HISTORY_FILE,
    MODEL_STATE_FILE,
    ROUTER_MODEL,
    ROUTER_URL,
)

from harness.logger import log_event

from harness.model_registry import (
    MODELS,
    get_default_model,
    get_model,
    model_exists,
)


_SELECTOR_LLM = ChatOpenAI(
    base_url=ROUTER_URL,
    api_key="lm-studio",
    model=ROUTER_MODEL,
    temperature=0,
)


# ============================================================
# STATE
# ============================================================

def _load_state():

    if not MODEL_STATE_FILE.exists():

        return {
            "auto": True,
            "manual_model": get_default_model(),
        }

    try:

        with MODEL_STATE_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        if not isinstance(state, dict):

            raise ValueError()

        return {
            "auto": bool(
                state.get(
                    "auto",
                    True,
                )
            ),
            "manual_model": state.get(
                "manual_model",
                get_default_model(),
            ),
        }

    except Exception:

        return {
            "auto": True,
            "manual_model": get_default_model(),
        }


def _save_state(state):

    with MODEL_STATE_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
        )


# ============================================================
# PUBLIC MODEL MODE
# ============================================================

def is_auto_mode() -> bool:

    return _load_state()["auto"]


def get_manual_model() -> str:

    state = _load_state()

    model = state["manual_model"]

    if not model_exists(model):

        return get_default_model()

    return model


def set_auto_mode(enabled: bool):

    state = _load_state()

    state["auto"] = enabled

    _save_state(state)

    log_event(
        "model_mode_changed",
        "system",
        auto=enabled,
    )


def set_manual_model(model_id: str):

    if not model_exists(model_id):

        raise ValueError(
            f"Unknown model '{model_id}'."
        )

    state = _load_state()

    state["manual_model"] = model_id
    state["auto"] = False

    _save_state(state)

    log_event(
        "manual_model_changed",
        "system",
        model=model_id,
    )


# ============================================================
# MODEL DESCRIPTION
# ============================================================

def model_summary():

    state = _load_state()

    selected = (
        state["manual_model"]
        if not state["auto"]
        else "automatic"
    )

    return {
        "auto": state["auto"],
        "selected": selected,
        "manual_model": state["manual_model"],
        "router": ROUTER_MODEL,
        "available": len(MODELS),
    }


def format_model_status() -> str:

    state = _load_state()

    lines = [
        "",
        "  Model configuration",
        "  " + "─" * 48,
        (
            "  Mode:       "
            + (
                "AUTO"
                if state["auto"]
                else "MANUAL"
            )
        ),
        (
            "  Selected:   "
            + (
                "automatic"
                if state["auto"]
                else state["manual_model"]
            )
        ),
        (
            "  Manual:     "
            + state["manual_model"]
        ),
        (
            "  Router:     "
            + ROUTER_MODEL
        ),
        (
            "  Available:  "
            + str(len(MODELS))
            + " models"
        ),
        "",
        "  Available models:",
    ]

    for model in MODELS.values():

        lines.append(
            f"    • {model.model_id}"
            f"  [{model.provider}]"
        )

    lines.append("")

    return "\n".join(lines)


# ============================================================
# ROUTER JSON
# ============================================================

def _extract_json(text: str):

    text = text.strip()

    try:

        return json.loads(text)

    except Exception:

        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:

        return None

    try:

        return json.loads(
            text[start:end + 1]
        )

    except Exception:

        return None


# ============================================================
# AUTOMATIC SELECTION
# ============================================================

async def select_model(
    request: str,
):

    state = _load_state()

    # --------------------------------------------------------
    # MANUAL
    # --------------------------------------------------------

    if not state["auto"]:

        model_id = state["manual_model"]

        if not model_exists(model_id):

            model_id = get_default_model()

        spec = get_model(model_id)

        return {
            "model": model_id,
            "reason": "Manual model selection.",
            "mode": "MANUAL",
            "confidence": 1.0,
            "provider": spec.provider,
        }

    # --------------------------------------------------------
    # AUTO
    # --------------------------------------------------------

    model_descriptions = []

    for model in MODELS.values():

        model_descriptions.append(
            {
                "id": model.model_id,
                "provider": model.provider,
                "description": model.description,
                "capabilities": list(
                    model.capabilities
                ),
            }
        )

    prompt = f"""
You are the TaskRun model selector.

Choose exactly ONE model for the user's request.

Do not answer the user.
Do not execute tools.
Return JSON only.

Available models:
{json.dumps(model_descriptions, indent=2)}

Selection guidance:

- Simple/general tasks can use a general model.
- Coding tasks should prefer a coding-capable model.
- Complex reasoning should prefer a reasoning model.
- Multi-step analysis should prefer a reasoning model.
- Tool-heavy computer tasks should prefer a model capable of tools.
- Do not automatically choose a thinking model for every request.
- Prefer the lighter/local model when the task is simple.
- The selected model MUST exactly match one of the model IDs.

User request:
{request}

Return exactly:

{{
  "model": "exact-model-id",
  "reason": "short reason",
  "confidence": 0.0
}}
"""

    start = time.time()

    try:

        response = await _SELECTOR_LLM.ainvoke(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )

        raw = response.content

        parsed = _extract_json(raw)

        if not isinstance(parsed, dict):

            raise ValueError(
                "Model selector returned invalid JSON."
            )

        model_id = parsed.get("model")

        if not isinstance(model_id, str):

            raise ValueError(
                "Model selector did not return a model."
            )

        if not model_exists(model_id):

            raise ValueError(
                f"Model selector chose unknown model: {model_id}"
            )

        reason = str(
            parsed.get(
                "reason",
                "Automatic model selection.",
            )
        )

        try:

            confidence = float(
                parsed.get(
                    "confidence",
                    0.0,
                )
            )

        except Exception:

            confidence = 0.0

        spec = get_model(model_id)

        duration = time.time() - start

        log_event(
            "model_selected",
            "system",
            model=model_id,
            mode="AUTO",
            reason=reason,
            confidence=confidence,
            duration_seconds=round(
                duration,
                3,
            ),
        )

        return {
            "model": model_id,
            "reason": reason,
            "mode": "AUTO",
            "confidence": confidence,
            "provider": spec.provider,
        }

    except Exception as exc:

        # Fail safe to the known local main model.
        # The selector itself must never prevent TaskRun
        # from functioning.

        fallback = get_default_model()

        log_event(
            "model_selector_fallback",
            "system",
            model=fallback,
            error=str(exc),
        )

        return {
            "model": fallback,
            "reason": (
                "Selector unavailable; "
                "using default main model."
            ),
            "mode": "AUTO",
            "confidence": 0.0,
            "provider": get_model(
                fallback
            ).provider,
        }


# ============================================================
# PERFORMANCE HISTORY
# ============================================================

def record_model_result(
    model_id: str,
    duration_seconds: float,
    success: bool,
    error: str | None = None,
):

    entry = {
        "timestamp": time.time(),
        "model": model_id,
        "duration_seconds": round(
            duration_seconds,
            3,
        ),
        "success": success,
    }

    if error:

        entry["error"] = error

    with MODEL_HISTORY_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            json.dumps(entry)
            + "\n"
        )
