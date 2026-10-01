from dataclasses import dataclass
import importlib
from pathlib import Path
from types import ModuleType


@dataclass(frozen=True)
class AgentSpec:
    """
    Metadata describing a dynamically discovered specialist agent.
    """

    name: str
    description: str
    system_prompt: str
    module_name: str
    factory: object


AGENT_FILE_PATTERN = "*_agent.py"


def _taskrun_directory() -> Path:
    """
    Return the root directory of the TaskRun project.
    """

    return Path(__file__).resolve().parent


def _load_agent_module(
    module_path: Path,
) -> ModuleType:
    """
    Import an agent module from the TaskRun directory.
    """

    module_name = module_path.stem

    return importlib.import_module(
        module_name
    )


def _build_agent_spec(
    module: ModuleType,
) -> AgentSpec | None:
    """
    Build an AgentSpec from an agent module.

    Required module attributes:

        AGENT_NAME
        AGENT_DESCRIPTION
        AGENT_SYSTEM_PROMPT
        get_agent
    """

    name = getattr(
        module,
        "AGENT_NAME",
        None,
    )

    description = getattr(
        module,
        "AGENT_DESCRIPTION",
        None,
    )

    system_prompt = getattr(
        module,
        "AGENT_SYSTEM_PROMPT",
        None,
    )

    factory = getattr(
        module,
        "get_agent",
        None,
    )

    if not name:
        return None

    if not description:
        return None

    if not system_prompt:
        return None

    if not callable(factory):
        return None

    return AgentSpec(
        name=str(name),
        description=str(description).strip(),
        system_prompt=str(system_prompt).strip(),
        module_name=module.__name__,
        factory=factory,
    )


def discover_agents() -> list[AgentSpec]:
    """
    Automatically discover specialist agents in ~/taskrun.

    Any Python file matching:

        *_agent.py

    can become a TaskRun specialist agent if it exposes:

        AGENT_NAME
        AGENT_DESCRIPTION
        AGENT_SYSTEM_PROMPT
        get_agent(model_id)
    """

    root = _taskrun_directory()

    discovered = []

    for path in sorted(
        root.glob(AGENT_FILE_PATTERN)
    ):

        if path.name.startswith("__"):
            continue

        try:
            module = _load_agent_module(
                path
            )

            spec = _build_agent_spec(
                module
            )

            if spec is not None:
                discovered.append(spec)

        except Exception as exc:

            print(
                f"[AGENT DISCOVERY] "
                f"Could not load {path.name}: "
                f"{exc}"
            )

    return discovered


def get_agent_specs() -> list[AgentSpec]:
    """
    Return all currently discovered specialist agents.
    """

    return discover_agents()


def get_agent_spec(
    name: str,
) -> AgentSpec | None:
    """
    Find a discovered specialist agent by name.
    """

    normalized = name.strip().lower()

    for agent in discover_agents():

        if agent.name.lower() == normalized:
            return agent

    return None


def get_agent_descriptions() -> list[dict]:
    """
    Return discovery information suitable for
    Supervisor routing.
    """

    return [
        {
            "name": agent.name,
            "description": agent.description,
        }
        for agent in discover_agents()
    ]


def create_agent(
    agent: AgentSpec,
    model_id: str,
):
    """
    Instantiate a specialist agent using its own factory.

    The specialist remains responsible for its own:
    - tools
    - system prompt
    - behavior
    - model creation
    """

    return agent.factory(
        model_id
    )
