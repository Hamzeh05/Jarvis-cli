from pathlib import Path
import asyncio
import json
import re

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import StructuredTool

from harness.context import (
    current_session_id,
    is_dry_run,
    is_queue_mode,
    set_approval_waiting,
)

from harness.logger import log_event
from harness.policy import operation_command
from harness.safety import classify_mcp_operation
from harness.queue import CommandQueue
from harness.undo import UndoManager
from harness.verification import verify_operation
from harness.ui_bridge import request_approval

from agent_registry import (
    get_agent_specs,
    create_agent as create_discovered_agent,
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

LM_STUDIO_URL = "http://172.18.16.1:1234/v1"
LITELLM_URL = "http://10.100.100.8:4000/v1"

ROUTER_MODEL_NAME = "qwen/qwen3-1.7b"
SAFETY_MODEL_NAME = "qwen/qwen3-1.7b"

DEFAULT_MAIN_MODEL = "qwen3-35b"


# ============================================================
# MODEL REGISTRY
# ============================================================

MODEL_REGISTRY = {
    "gemma4-31b": {
        "provider": "litellm",
        "base_url": LITELLM_URL,
        "model": "gemma4-31b",
        "label": "Gemma 4 31B",
        "strength": 4,
        "reasoning": 4,
        "coding": 4,
        "speed": 3,
        "best_for": [
            "general reasoning",
            "analysis",
            "coding",
        ],
        "fallback": "qwen3-35b",
    },

    "gemma4-31b-thinking": {
        "provider": "litellm",
        "base_url": LITELLM_URL,
        "model": "gemma4-31b-thinking",
        "label": "Gemma 4 31B Thinking",
        "strength": 5,
        "reasoning": 5,
        "coding": 4,
        "speed": 2,
        "best_for": [
            "complex reasoning",
            "analysis",
            "planning",
            "difficult debugging",
        ],
        "fallback": "gemma4-31b",
    },

    "qwen3-35b": {
        "provider": "litellm",
        "base_url": LITELLM_URL,
        "model": "qwen3-35b",
        "label": "Qwen 3 35B",
        "strength": 5,
        "reasoning": 4,
        "coding": 5,
        "speed": 3,
        "best_for": [
            "coding",
            "agent tasks",
            "reasoning",
            "technical tasks",
        ],
        "fallback": None,
    },

    "qwen3-35b-thinking": {
        "provider": "litellm",
        "base_url": LITELLM_URL,
        "model": "qwen3-35b-thinking",
        "label": "Qwen 3 35B Thinking",
        "strength": 5,
        "reasoning": 5,
        "coding": 5,
        "speed": 2,
        "best_for": [
            "complex reasoning",
            "architecture",
            "difficult debugging",
            "planning",
            "multi-step agent tasks",
        ],
        "fallback": "qwen3-35b",
    },
}


# ============================================================
# MODEL INSTANCES
# ============================================================

_model_cache = {}


def get_model(model_id: str):

    if model_id not in MODEL_REGISTRY:
        model_id = DEFAULT_MAIN_MODEL

    if model_id in _model_cache:
        return _model_cache[model_id]

    config = MODEL_REGISTRY[model_id]

    if config["provider"] == "lmstudio":
        api_key = "lm-studio"
    else:
        api_key = "not-needed"

    model = ChatOpenAI(
        base_url=config["base_url"],
        api_key=api_key,
        model=config["model"],
        temperature=0,
    )

    _model_cache[model_id] = model

    return model


# ============================================================
# ROUTER MODEL
# ============================================================

router_llm = ChatOpenAI(
    base_url=LM_STUDIO_URL,
    api_key="lm-studio",
    model=ROUTER_MODEL_NAME,
    temperature=0,
)


# ============================================================
# MCP CLIENT
# ============================================================

mcp_client = MultiServerMCPClient(
    {
        "computer": {
            "command": "python",
            "args": ["mcp_server.py"],
            "transport": "stdio",
        }
    }
)


# ============================================================
# CHECKPOINTER
# ============================================================

checkpointer = InMemorySaver()


# ============================================================
# CACHES
# ============================================================

_mcp_tools_cache = None
_mcp_tools_lock = asyncio.Lock()

_supervisor_cache = {}


# ============================================================
# MCP TOOL DESCRIPTIONS
# ============================================================

MCP_TOOL_DESCRIPTIONS = {
    "execute_command": (
        "Execute a command on the computer. "
        "Use for commands that genuinely need execution."
    ),

    "list_directory": (
        "List files and directories at a path."
    ),

    "read_file": (
        "Read the contents of a file."
    ),

    "search_files": (
        "Search for files matching a pattern or query."
    ),

    "write_file": (
        "Create or overwrite a file with supplied content."
    ),

    "make_directory": (
        "Create a directory."
    ),

    "copy_path": (
        "Copy a file or directory."
    ),

    "move_path": (
        "Move or rename a file or directory."
    ),

    "delete_path": (
        "Delete a file or directory."
    ),

    "system_info": (
        "Get system information."
    ),

    "process_list": (
        "List running processes."
    ),

    "docker_ps": (
        "List running Docker containers."
    ),
}


# ============================================================
# ROUTER PROMPT
# ============================================================

ROUTER_PROMPT = """
You are TaskRun's tool router.

Your job is ONLY to select the minimum number of computer MCP tools
needed to answer the user's request.

You DO NOT execute anything.

Available tools:

1. execute_command
   Execute a shell/system command.

2. list_directory
   List files/directories.

3. read_file
   Read a file.

4. search_files
   Search files.

5. write_file
   Create or modify a file.

6. make_directory
   Create a directory.

7. copy_path
   Copy files/directories.

8. move_path
   Move/rename files/directories.

9. delete_path
   Delete files/directories.

10. system_info
    Get operating-system information.

11. process_list
    List processes.

12. docker_ps
    List Docker containers.

Rules:

- Select ONLY tools that may actually be needed.
- Prefer read-only tools when possible.
- Do not select execute_command when a dedicated tool can do the job.
- Do not select write/delete/move/copy tools unless the user explicitly
  requests a modification.
- For general computer questions, select the smallest useful set.
- If the request does not require computer tools, return an empty list.

Return ONLY valid JSON:

{
  "tools": ["tool_name"],
  "reason": "short explanation"
}
"""


# ============================================================
# ROUTER JSON PARSER
# ============================================================

def _extract_router_json(text: str):

    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)

    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if not match:
        return None

    try:
        return json.loads(
            match.group(0)
        )

    except Exception:
        return None


# ============================================================
# ROUTER VALIDATION
# ============================================================

def _validate_router_result(data):

    if not isinstance(data, dict):
        return None

    tools = data.get("tools")

    if not isinstance(tools, list):
        return None

    valid_tools = [
        name
        for name in tools
        if name in MCP_TOOL_DESCRIPTIONS
    ]

    reason = data.get(
        "reason",
        "Tool selection completed.",
    )

    if not isinstance(reason, str):
        reason = "Tool selection completed."

    return {
        "tools": list(
            dict.fromkeys(valid_tools)
        ),
        "reason": reason,
    }


# ============================================================
# FALLBACK TOOL SELECTION
# ============================================================

def fallback_mcp_tools(request: str):

    text = request.lower()

    selected = []

    if any(
        word in text
        for word in [
            "docker",
            "container",
        ]
    ):
        selected.append("docker_ps")

    if any(
        word in text
        for word in [
            "process",
            "running",
            "cpu",
            "memory usage",
        ]
    ):
        selected.append("process_list")

    if any(
        word in text
        for word in [
            "system",
            "computer information",
            "os information",
            "hardware",
        ]
    ):
        selected.append("system_info")

    if any(
        word in text
        for word in [
            "read",
            "open",
            "show contents",
            "contents of",
        ]
    ):
        selected.append("read_file")

    if any(
        word in text
        for word in [
            "find",
            "search",
            "locate",
        ]
    ):
        selected.append("search_files")

    if any(
        word in text
        for word in [
            "list",
            "files",
            "folder",
            "directory",
        ]
    ):
        selected.append("list_directory")

    if any(
        word in text
        for word in [
            "create file",
            "write file",
            "modify file",
            "edit file",
        ]
    ):
        selected.append("write_file")

    if any(
        word in text
        for word in [
            "mkdir",
            "create directory",
            "create folder",
        ]
    ):
        selected.append("make_directory")

    if any(
        word in text
        for word in [
            "copy",
        ]
    ):
        selected.append("copy_path")

    if any(
        word in text
        for word in [
            "move",
            "rename",
        ]
    ):
        selected.append("move_path")

    if any(
        word in text
        for word in [
            "delete",
            "remove",
        ]
    ):
        selected.append("delete_path")

    if any(
        word in text
        for word in [
            "run",
            "execute",
            "command",
            "terminal",
            "shell",
        ]
    ):
        selected.append("execute_command")

    return list(
        dict.fromkeys(selected)
    )


# ============================================================
# TOOL ROUTING
# ============================================================

async def route_mcp_tools(request: str):

    try:

        response = await router_llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": ROUTER_PROMPT,
                },
                {
                    "role": "user",
                    "content": request,
                },
            ]
        )

        raw = response.content

        parsed = _extract_router_json(
            raw
        )

        validated = _validate_router_result(
            parsed
        )

        if validated is not None:

            selected = validated["tools"]

            print()
            print("[ROUTER MODEL]")
            print(
                f"  {ROUTER_MODEL_NAME}"
            )

            if selected:

                print(
                    "[ROUTER TOOLS] "
                    + ", ".join(selected)
                )

            else:

                print(
                    "[ROUTER TOOLS] none"
                )

            print(
                f"[ROUTER REASON] "
                f"{validated['reason']}"
            )

            log_event(
                "tool_routing",
                current_session_id(),
                router_model=ROUTER_MODEL_NAME,
                tools=selected,
                reason=validated["reason"],
            )

            return selected

    except Exception as exc:

        log_event(
            "tool_routing_error",
            current_session_id(),
            error=str(exc),
        )

    fallback = fallback_mcp_tools(
        request
    )

    print()
    print("[ROUTER FALLBACK]")
    print(
        "  "
        + (
            ", ".join(fallback)
            if fallback
            else "no tools"
        )
    )

    log_event(
        "tool_routing_fallback",
        current_session_id(),
        tools=fallback,
    )

    return fallback


# ============================================================
# SPECIALIST HELPERS
# ============================================================

async def _run_specialist(
    agent,
    request: str,
):

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": request,
                }
            ]
        }
    )

    messages = result.get(
        "messages",
        [],
    )

    if not messages:
        return "(No specialist response.)"

    content = messages[-1].content

    if isinstance(content, str):
        return content

    return str(content)


# ============================================================
# DYNAMIC SPECIALIST DISCOVERY
# ============================================================

def _build_specialist_description(
    agent_spec,
) -> str:

    return (
        f"Specialist agent: {agent_spec.name}\n\n"
        f"Capabilities:\n"
        f"{agent_spec.description.strip()}"
    )


def create_specialist_tools(
    model_id: str,
):

    agent_specs = get_agent_specs()

    specialist_tools = []

    if not agent_specs:

        print(
            "[AGENT DISCOVERY] "
            "No specialist agents discovered."
        )

        return specialist_tools

    print()
    print("[AGENT DISCOVERY]")

    for agent_spec in agent_specs:

        print(
            f"  {agent_spec.name}: "
            f"{agent_spec.description.strip()}"
        )

        specialist_agent = create_discovered_agent(
            agent_spec,
            model_id,
        )

        async def ask_specialist(
            request: str,
            _agent=specialist_agent,
            _spec=agent_spec,
        ) -> str:

            print()
            print(
                f"[MODEL: {model_id}]"
            )

            print(
                f"[ROUTING: {_spec.name}]"
            )

            log_event(
                "specialist_routing",
                current_session_id(),
                specialist=_spec.name,
                model=model_id,
                request=request,
            )

            return await _run_specialist(
                _agent,
                request,
            )

        tool_name = (
            "ask_"
            + agent_spec.name
        )

        specialist_tool = (
            StructuredTool.from_function(
                coroutine=ask_specialist,
                name=tool_name,
                description=(
                    "Delegate a request to "
                    f"{agent_spec.name}.\n\n"
                    f"{agent_spec.description.strip()}"
                ),
            )
        )

        specialist_tools.append(
            specialist_tool
        )

    return specialist_tools


# ============================================================
# TOOL RESULT CONTEXT
# ============================================================

MAX_TOOL_RESULT_CHARS = 6000


def summarize_tool_result(result):

    if result is None:
        return "(No result.)"

    if not isinstance(result, str):
        result = str(result)

    if len(result) <= MAX_TOOL_RESULT_CHARS:
        return result

    return (
        result[:MAX_TOOL_RESULT_CHARS]
        + "\n\n[Result truncated by TaskRun.]"
    )


# ============================================================
# OPERATION EXPLANATIONS
# ============================================================

def explain_operation(
    tool_name: str,
    kwargs: dict,
):

    explanations = {

        "list_directory":
            "List the contents of a directory.",

        "read_file":
            "Read the contents of a file.",

        "search_files":
            "Search the filesystem for matching files.",

        "system_info":
            "Read system information.",

        "process_list":
            "Read the list of running processes.",

        "docker_ps":
            "Read the currently running Docker containers.",

        "write_file":
            "Create or modify a file.",

        "make_directory":
            "Create a directory.",

        "copy_path":
            "Copy a file or directory.",

        "move_path":
            "Move or rename a file or directory.",

        "delete_path":
            "Delete a file or directory.",

        "execute_command":
            "Execute a command on the computer.",
    }

    return explanations.get(
        tool_name,
        f"Execute the {tool_name} operation.",
    )


# ============================================================
# DESKTOP PATH HANDLING
# ============================================================

def resolve_desktop_path(value):

    if not isinstance(value, str):
        return value

    normalized = value.strip()

    if normalized.lower() in {
        "desktop",
        "~/desktop",
        "$desktop",
    }:

        candidates = [
            Path.home() / "Desktop",

            Path(
                "/mnt/c/Users/hamze/Desktop"
            ),

            Path(
                "/mnt/c/Users/hamze/OneDrive/Desktop"
            ),
        ]

        for candidate in candidates:

            if candidate.exists():
                return str(candidate)

        return str(candidates[-1])

    return value


def resolve_paths_in_kwargs(kwargs):

    if not isinstance(kwargs, dict):
        return kwargs

    resolved = {}

    for key, value in kwargs.items():

        if isinstance(value, str):

            if any(
                token in key.lower()
                for token in [
                    "path",
                    "file",
                    "directory",
                    "folder",
                    "source",
                    "destination",
                    "target",
                ]
            ):

                resolved[key] = resolve_desktop_path(
                    value
                )

            else:

                resolved[key] = value

        else:

            resolved[key] = value

    return resolved


# ============================================================
# READ-ONLY TOOLS
# ============================================================

READ_ONLY_TOOLS = {
    "list_directory",
    "read_file",
    "search_files",
    "system_info",
    "process_list",
    "docker_ps",
}


# ============================================================
# MCP TOOLS
# ============================================================

async def get_all_mcp_tools():

    global _mcp_tools_cache

    if _mcp_tools_cache is not None:
        return _mcp_tools_cache

    async with _mcp_tools_lock:

        if _mcp_tools_cache is None:

            _mcp_tools_cache = (
                await mcp_client.get_tools()
            )

    return _mcp_tools_cache


# ============================================================
# MODEL INFORMATION
# ============================================================

def list_models():

    return list(
        MODEL_REGISTRY.keys()
    )


def get_model_info(
    model_id: str,
):

    return MODEL_REGISTRY.get(
        model_id
    )


def choose_fallback_model(
    model_id: str,
):

    config = MODEL_REGISTRY.get(
        model_id
    )

    if not config:
        return DEFAULT_MAIN_MODEL

    fallback = config.get(
        "fallback"
    )

    if fallback in MODEL_REGISTRY:
        return fallback

    return DEFAULT_MAIN_MODEL


# ============================================================
# MODEL SELECTION
# ============================================================

MODEL_SELECTOR_PROMPT = """
You are TaskRun's model selector.

Choose the most appropriate MAIN reasoning model for the task.

Available models:

gemma4-31b
- stronger general reasoning
- analysis
- coding

gemma4-31b-thinking
- deep reasoning
- difficult analysis
- planning
- difficult debugging

qwen3-35b
- strong coding
- strong technical reasoning
- agent tasks

qwen3-35b-thinking
- deep reasoning
- architecture
- complex debugging
- difficult multi-step tasks

Choose based on the actual task.

Prefer faster models for simple requests.
Use thinking models for genuinely complex reasoning.

Return ONLY JSON:

{
  "model": "exact_model_id",
  "reason": "short explanation",
  "confidence": 0.0
}
"""


def _parse_model_selection(
    text,
):

    if not text:
        return None

    parsed = _extract_router_json(
        text
    )

    if not isinstance(parsed, dict):
        return None

    model = parsed.get(
        "model"
    )

    if model not in MODEL_REGISTRY:
        return None

    reason = parsed.get(
        "reason",
        "Selected based on task requirements.",
    )

    confidence = parsed.get(
        "confidence",
        0.5,
    )

    try:

        confidence = float(
            confidence
        )

    except Exception:

        confidence = 0.5

    confidence = max(
        0.0,
        min(1.0, confidence),
    )

    return {
        "model": model,
        "reason": reason,
        "confidence": confidence,
    }


async def auto_select_model(
    request: str,
):

    try:

        response = await router_llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": MODEL_SELECTOR_PROMPT,
                },
                {
                    "role": "user",
                    "content": request,
                },
            ]
        )

        result = _parse_model_selection(
            response.content
        )

        if result:

            log_event(
                "model_selected",
                current_session_id(),
                model=result["model"],
                reason=result["reason"],
                confidence=result["confidence"],
                selector_model=ROUTER_MODEL_NAME,
            )

            return result

    except Exception as exc:

        log_event(
            "model_selection_error",
            current_session_id(),
            error=str(exc),
        )

    fallback = DEFAULT_MAIN_MODEL

    result = {
        "model": fallback,
        "reason": "Automatic selection fallback.",
        "confidence": 0.0,
    }

    log_event(
        "model_selection_fallback",
        current_session_id(),
        model=fallback,
    )

    return result


# ============================================================
# MODEL PREFERENCE
# ============================================================

from harness.config import LOG_DIR


MODEL_STATE_FILE = LOG_DIR / "model_state.json"


def _load_model_state():

    if not MODEL_STATE_FILE.exists():
        return {
            "mode": "auto",
            "manual_model": DEFAULT_MAIN_MODEL,
        }

    try:

        data = json.loads(
            MODEL_STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            raise ValueError

        mode = data.get(
            "mode",
            "auto",
        )

        manual_model = data.get(
            "manual_model",
            DEFAULT_MAIN_MODEL,
        )

        if manual_model not in MODEL_REGISTRY:
            manual_model = DEFAULT_MAIN_MODEL

        if mode not in {
            "auto",
            "manual",
        }:
            mode = "auto"

        return {
            "mode": mode,
            "manual_model": manual_model,
        }

    except Exception:

        return {
            "mode": "auto",
            "manual_model": DEFAULT_MAIN_MODEL,
        }


def _save_model_state(
    mode: str,
    manual_model: str,
):

    LOG_DIR.mkdir(
        exist_ok=True
    )

    MODEL_STATE_FILE.write_text(
        json.dumps(
            {
                "mode": mode,
                "manual_model": manual_model,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def get_model_preference():

    return _load_model_state()


def set_model_preference(
    mode: str,
    manual_model: str | None = None,
):

    state = _load_model_state()

    if mode not in {
        "auto",
        "manual",
    }:
        raise ValueError(
            "Model mode must be auto or manual."
        )

    if manual_model is None:
        manual_model = state[
            "manual_model"
        ]

    if manual_model not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {manual_model}"
        )

    _save_model_state(
        mode,
        manual_model,
    )

    return {
        "mode": mode,
        "manual_model": manual_model,
    }


async def resolve_model_for_request(
    request: str,
):

    state = get_model_preference()

    if state["mode"] == "manual":

        model_id = state[
            "manual_model"
        ]

        return {
            "model": model_id,
            "reason": "Manual model selection.",
            "confidence": 1.0,
            "mode": "manual",
        }

    selected = await auto_select_model(
        request
    )

    selected["mode"] = "auto"

    return selected


# ============================================================
# ACTUAL SUPERVISOR BUILDER
# ============================================================

async def _build_computer_supervisor(
    request: str,
    selected_names: list[str],
    model_id: str,
):

    all_mcp_tools = await get_all_mcp_tools()

    selected_mcp_tools = [
        tool_obj
        for tool_obj in all_mcp_tools
        if tool_obj.name in selected_names
    ]

    specialist_tools = create_specialist_tools(
        model_id
    )

    wrapped_tools = []

    # --------------------------------------------------------
    # Wrap MCP tools
    # --------------------------------------------------------

    for mcp_tool in selected_mcp_tools:

        tool_name = mcp_tool.name

        async def execute_wrapped_tool(
            _mcp_tool=mcp_tool,
            _tool_name=tool_name,
            **kwargs,
        ):

            kwargs = resolve_paths_in_kwargs(
                kwargs
            )

            command = operation_command(
                _tool_name,
                kwargs,
            )

            explanation = explain_operation(
                _tool_name,
                kwargs,
            )

            print()
            print(
                f"[MODEL: {model_id}]"
            )
            print(
                f"[MCP TOOL: {_tool_name}]"
            )

            # ------------------------------------------------
            # Safety
            # ------------------------------------------------

            safety_result = (
                await classify_mcp_operation(
                    _tool_name,
                    kwargs,
                )
            )

            log_event(
                "safety_check",
                current_session_id(),
                model=model_id,
                tool=_tool_name,
                command=command,
                risk_level=safety_result.level,
                system_risk=safety_result.system_risk,
                action=safety_result.action,
                reason=safety_result.reason,
            )

            print()
            print(
                "[SAFETY]"
            )
            print(
                f"  Risk: {safety_result.level}"
            )
            print(
                f"  System risk: "
                f"{safety_result.system_risk}"
            )
            print(
                f"  Action: "
                f"{safety_result.action}"
            )
            print(
                f"  Reason: "
                f"{safety_result.reason}"
            )

            # ------------------------------------------------
            # System-risk protection
            # ------------------------------------------------

            if safety_result.system_risk:

                log_event(
                    "operation_blocked",
                    current_session_id(),
                    model=model_id,
                    tool=_tool_name,
                    command=command,
                    reason=(
                        "System-risk operation "
                        "cannot be overridden."
                    ),
                )

                return (
                    "TaskRun blocked this operation "
                    "because it was classified as "
                    "system-risk."
                )

            # ------------------------------------------------
            # Command plan
            # ------------------------------------------------

            print()
            print(
                "[COMMAND PLAN]"
            )
            print(
                f"  {command}"
            )
            print()
            print(
                "[WHY]"
            )
            print(
                f"  {explanation}"
            )

            # ------------------------------------------------
            # Dry run
            # ------------------------------------------------

            if is_dry_run():

                log_event(
                    "dry_run_operation",
                    current_session_id(),
                    model=model_id,
                    tool=_tool_name,
                    command=command,
                )

                return (
                    "[DRY RUN]\n"
                    f"{command}\n\n"
                    "The operation was not executed."
                )

            # ------------------------------------------------
            # Queue mode
            # ------------------------------------------------

            if is_queue_mode():

                queue = CommandQueue()

                try:

                    queue.add(
                        session_id=current_session_id(),
                        tool=_tool_name,
                        operation=command,
                        kwargs=kwargs,
                    )

                except TypeError:

                    try:

                        queue.add(
                            current_session_id(),
                            _tool_name,
                            command,
                            kwargs,
                        )

                    except Exception as exc:

                        log_event(
                            "queue_add_error",
                            current_session_id(),
                            error=str(exc),
                        )

                log_event(
                    "operation_queued",
                    current_session_id(),
                    model=model_id,
                    tool=_tool_name,
                    command=command,
                )

                return (
                    "[QUEUED]\n"
                    f"{command}\n\n"
                    "The operation was placed in "
                    "the command queue."
                )

            # ------------------------------------------------
            # Human approval
            # ------------------------------------------------

            set_approval_waiting(
                True
            )

            try:

                approval = await request_approval(
                    {
                        "tool": _tool_name,
                        "command": command,
                        "reason": explanation,
                        "risk_level": safety_result.level,
                    }
                )

            finally:

                set_approval_waiting(
                    False
                )

            if not approval:

                log_event(
                    "operation_denied",
                    current_session_id(),
                    model=model_id,
                    tool=_tool_name,
                    command=command,
                )

                return (
                    "Operation denied by the user."
                )

            # ------------------------------------------------
            # Undo registration
            # ------------------------------------------------

            undo = UndoManager()

            try:

                undo.record(
                    current_session_id(),
                    _tool_name,
                    kwargs,
                )

            except TypeError:

                try:

                    undo.record(
                        session_id=current_session_id(),
                        tool=_tool_name,
                        kwargs=kwargs,
                    )

                except Exception:

                    pass

            # ------------------------------------------------
            # Execute
            # ------------------------------------------------

            log_event(
                "operation_started",
                current_session_id(),
                model=model_id,
                tool=_tool_name,
                command=command,
            )

            try:

                raw_result = await _mcp_tool.ainvoke(
                    kwargs
                )

            except Exception as exc:

                log_event(
                    "operation_failed",
                    current_session_id(),
                    model=model_id,
                    tool=_tool_name,
                    command=command,
                    error=str(exc),
                )

                raise

            # ------------------------------------------------
            # Raw result
            # ------------------------------------------------

            log_event(
                "raw_tool_result",
                current_session_id(),
                model=model_id,
                tool=_tool_name,
                command=command,
                result=str(raw_result),
            )

            print()
            print(
                "[RAW RESULT -> AI]"
            )
            print(
                summarize_tool_result(
                    raw_result
                )
            )

            # ------------------------------------------------
            # Verification
            # ------------------------------------------------

            verification = verify_operation(
                _tool_name,
                kwargs,
                raw_result,
            )

            log_event(
                "operation_verified",
                current_session_id(),
                model=model_id,
                tool=_tool_name,
                verification=str(
                    verification
                ),
            )

            # ------------------------------------------------
            # Context-aware result
            # ------------------------------------------------

            contextual_result = (
                summarize_tool_result(
                    raw_result
                )
            )

            return (
                f"TOOL: {_tool_name}\n\n"
                f"RESULT:\n"
                f"{contextual_result}\n\n"
                f"VERIFICATION:\n"
                f"{verification}"
            )

        wrapped = StructuredTool.from_function(
            coroutine=execute_wrapped_tool,
            name=tool_name,
            description=(
                mcp_tool.description
                or MCP_TOOL_DESCRIPTIONS.get(
                    tool_name,
                    "Computer operation.",
                )
            ),
            args_schema=getattr(
                mcp_tool,
                "args_schema",
                None,
            ),
        )

        wrapped_tools.append(
            wrapped
        )

    # --------------------------------------------------------
    # Parallel read-only tool
    # --------------------------------------------------------

    selected_read_only = [
        name
        for name in selected_names
        if name in READ_ONLY_TOOLS
    ]

    if len(selected_read_only) > 1:

        async def parallel_read_only(
            operations: list[dict],
        ) -> str:
            """
            Execute multiple independent read-only
            computer operations concurrently.

            Each operation must contain:
            {
                "tool": "tool_name",
                "arguments": {...}
            }
            """

            tasks = []

            tool_map = {
                tool_obj.name: tool_obj
                for tool_obj in selected_mcp_tools
            }

            for operation in operations:

                operation_tool = operation.get(
                    "tool"
                )

                arguments = operation.get(
                    "arguments",
                    {},
                )

                if operation_tool not in READ_ONLY_TOOLS:

                    raise ValueError(
                        "parallel_read_only can only "
                        "use read-only tools."
                    )

                if operation_tool not in tool_map:

                    raise ValueError(
                        f"Tool {operation_tool} "
                        "was not routed."
                    )

                tasks.append(
                    tool_map[
                        operation_tool
                    ].ainvoke(
                        resolve_paths_in_kwargs(
                            arguments
                        )
                    )
                )

            results = await asyncio.gather(
                *tasks
            )

            output = []

            for index, result in enumerate(
                results,
                start=1,
            ):

                output.append(
                    f"Operation {index}:\n"
                    f"{summarize_tool_result(result)}"
                )

            return "\n\n".join(
                output
            )

        parallel_tool = StructuredTool.from_function(
            coroutine=parallel_read_only,
            name="parallel_read_only",
            description=(
                "Execute multiple independent "
                "read-only computer operations "
                "concurrently."
            ),
        )

        wrapped_tools.append(
            parallel_tool
        )

    # --------------------------------------------------------
    # Specialist tools
    # --------------------------------------------------------

    wrapped_tools.extend(
        specialist_tools
    )

    # --------------------------------------------------------
    # Dynamic agent descriptions
    # --------------------------------------------------------

    agent_specs = get_agent_specs()

    if agent_specs:

        specialist_capabilities = "\n\n".join(
            [
                (
                    f"- {agent.name}:\n"
                    f"  {agent.description.strip()}"
                )
                for agent in agent_specs
            ]
        )

    else:

        specialist_capabilities = (
            "No specialist agents are currently available."
        )

    # --------------------------------------------------------
    # Supervisor prompt
    # --------------------------------------------------------

    supervisor_prompt = f"""
You are TaskRun's Supervisor.

Main reasoning model:
{model_id}

Your job is to understand the user's request and coordinate
the capabilities available to you.

SPECIALIST AGENTS
=================

The following specialist agents were discovered dynamically:

{specialist_capabilities}

Their descriptions define their capabilities.

Do not assume that an agent exists unless it appears above.

Do not invent agents or capabilities.

Each specialist agent owns its own system prompt and tools.
When delegating to a specialist, preserve the user's original
intent and let that specialist perform its own task.

COMPUTER MCP
============

Computer MCP provides computer capabilities such as:

- reading files
- searching files
- listing directories
- executing commands
- creating files/directories
- moving/copying/deleting paths
- reading system information
- inspecting processes
- inspecting Docker containers

Computer operations are safety checked by TaskRun.

The system has a separate 1.7B model for:
- computer tool routing
- safety classification

Those models are NOT your main reasoning model.

IMPORTANT RULES
===============

- Use the minimum capabilities required.
- Choose specialist agents based on their descriptions.
- You may use multiple specialist agents when necessary.
- You may combine specialist-agent results with computer MCP results.
- Do not claim an agent or tool was used if it was not.
- Do not invent tool results.
- Treat actual agent/tool results as the source of truth.
- Preserve the user's exact request when delegating.
- Computer operations are always safety checked.
- Computer operations require human approval unless TaskRun
  is explicitly operating in dry-run or queue mode.
- System-risk computer operations are blocked and cannot be overridden.
- If a tool returns a verification result, use it.
- If an operation was denied, clearly say that it was denied.
- If an operation was queued, clearly say that it was queued.
- Keep responses clear and concise.
- Desktop refers to the user's Windows Desktop when applicable.
"""

    model = get_model(
        model_id
    )

    return create_agent(
        model=model,
        tools=wrapped_tools,
        system_prompt=supervisor_prompt,
        checkpointer=checkpointer,
    )


# ============================================================
# SUPERVISOR CREATION
# ============================================================

async def create_supervisor(
    request: str,
    model_id: str,
    selected_names=None,
):

    if selected_names is None:

        selected_names = await route_mcp_tools(
            request
        )

    return await _build_computer_supervisor(
        request,
        selected_names,
        model_id,
    )


# ============================================================
# GET SUPERVISOR
# ============================================================

async def get_supervisor(
    request: str,
    model_id: str | None = None,
):

    if model_id is None:

        selection = await resolve_model_for_request(
            request
        )

        model_id = selection[
            "model"
        ]

    selected_names = await route_mcp_tools(
        request
    )

    cache_key = (
        model_id,
        frozenset(
            selected_names
        ),
    )

    if cache_key in _supervisor_cache:

        return _supervisor_cache[
            cache_key
        ]

    supervisor = await create_supervisor(
        request=request,
        model_id=model_id,
        selected_names=selected_names,
    )

    _supervisor_cache[
        cache_key
    ] = supervisor

    return supervisor


# ============================================================
# MODEL STATUS
# ============================================================

async def get_model_status(
    request: str | None = None,
):

    state = get_model_preference()

    if state["mode"] == "manual":

        selected = state[
            "manual_model"
        ]

        reason = "Manual model selection."

    elif request:

        selection = await resolve_model_for_request(
            request
        )

        selected = selection[
            "model"
        ]

        reason = selection[
            "reason"
        ]

    else:

        selected = DEFAULT_MAIN_MODEL

        reason = "Automatic mode."

    return {
        "mode": state["mode"],
        "selected": selected,
        "reason": reason,
        "available_models": list_models(),
        "router": ROUTER_MODEL_NAME,
        "safety": SAFETY_MODEL_NAME,
    }
