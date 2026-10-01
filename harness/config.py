from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"

MAX_REQUEST_LENGTH = 4000

DEFAULT_THREAD_PREFIX = "taskrun"

MEMORY_FILE = LOG_DIR / "memory.json"
QUEUE_FILE = LOG_DIR / "command_queue.json"
UNDO_FILE = LOG_DIR / "undo.json"

MODEL_STATE_FILE = LOG_DIR / "model_state.json"
MODEL_HISTORY_FILE = LOG_DIR / "model_history.jsonl"


# ============================================================
# MODEL ENDPOINTS
# ============================================================

LM_STUDIO_URL = "http://172.18.16.1:1234/v1"

LITELLM_URL = "http://10.100.100.8:4000/v1"

# LiteLLM authentication is optional.
#
# Linux / WSL:
#
# export LITELLM_API_KEY="your-key"
#
# Windows / PowerShell:
#
# $env:LITELLM_API_KEY="your-key"

LITELLM_API_KEY_ENV = "LITELLM_API_KEY"


# ============================================================
# DEFAULT MAIN MODEL
# ============================================================

DEFAULT_MAIN_MODEL = "qwen3-35b"


# ============================================================
# ROUTER / SAFETY MODELS
#
# These are intentionally separate from the main model pool.
# ============================================================

ROUTER_MODEL = "qwen/qwen3-1.7b"
SAFETY_MODEL = "qwen/qwen3-1.7b"

ROUTER_URL = LM_STUDIO_URL
SAFETY_URL = LM_STUDIO_URL


# ============================================================
# CONTEXT COMPACTION
# ============================================================
#
# TaskRun automatically compacts the LangGraph conversation
# when the estimated context reaches 80% of the configured
# context window.
#
# The default is 32K tokens.
#
# If a model/server has a different context size, you can
# override it without editing Python:
#
# export TASKRUN_CONTEXT_WINDOW=65536
#
# The estimate is intentionally conservative because tool
# definitions/system prompts also consume context that is not
# represented directly inside the conversation messages.
#

TASKRUN_CONTEXT_WINDOW = int(
    os.getenv(
        "TASKRUN_CONTEXT_WINDOW",
        "32768",
    )
)

CONTEXT_COMPACTION_THRESHOLD = float(
    os.getenv(
        "TASKRUN_COMPACTION_THRESHOLD",
        "0.80",
    )
)

CONTEXT_SYSTEM_OVERHEAD_TOKENS = int(
    os.getenv(
        "TASKRUN_CONTEXT_OVERHEAD",
        "4000",
    )
)

CONTEXT_KEEP_RECENT_MESSAGES = int(
    os.getenv(
        "TASKRUN_KEEP_RECENT_MESSAGES",
        "6",
    )
)

CONTEXT_MIN_OLD_MESSAGES = int(
    os.getenv(
        "TASKRUN_MIN_OLD_MESSAGES",
        "4",
    )
)


# ============================================================
# PROTECTED RESOURCES
# ============================================================

PROTECTED_PATHS = [
    Path.home() / ".ssh",
    Path.home() / ".gnupg",

    Path("/etc"),
    Path("/boot"),
    Path("/dev"),
    Path("/proc"),
    Path("/sys"),
    Path("/root"),
]


# ============================================================
# DIRECTORIES
# ============================================================

LOG_DIR.mkdir(
    exist_ok=True
)
