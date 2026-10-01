import asyncio
import json
import time
import uuid

from harness.config import (
    DEFAULT_THREAD_PREFIX,
    MAX_REQUEST_LENGTH,
    TASKRUN_CONTEXT_WINDOW,
    CONTEXT_COMPACTION_THRESHOLD,
    CONTEXT_SYSTEM_OVERHEAD_TOKENS,
    CONTEXT_KEEP_RECENT_MESSAGES,
    CONTEXT_MIN_OLD_MESSAGES,
)

from harness.context import (
    reset_runtime_context,
    set_runtime_context,
)

from harness.logger import log_event

from harness.memory import MemoryStore

from harness.queue import CommandQueue

from harness.undo import UndoManager

from harness.model_selector import (
    record_model_result,
    select_model,
)

from harness.model_registry import (
    create_llm,
    get_model,
)

from harness.router_gate import (
    classify_request as classify_router_request,
)

from Supervisor import get_supervisor

from langchain_core.messages import (
    RemoveMessage,
    SystemMessage,
)


# ============================================================
# SESSION ID
# ============================================================

def generate_session_id():

    return (
        f"{DEFAULT_THREAD_PREFIX}-"
        f"{uuid.uuid4().hex[:8]}"
    )


# ============================================================
# REQUEST VALIDATION
# ============================================================

def validate_request(
    request: str,
):

    request = request.strip()

    if not request:

        raise ValueError(
            "Request cannot be empty."
        )

    if len(request) > MAX_REQUEST_LENGTH:

        raise ValueError(
            f"Request is too long. "
            f"Maximum length is "
            f"{MAX_REQUEST_LENGTH} characters."
        )

    return request


# ============================================================
# FAST LOCAL CONVERSATION CLASSIFIER
# ============================================================

def classify_fast_path(
    request: str,
) -> str | None:

    """
    Detect requests that can be answered without:

        - model selection
        - Supervisor creation
        - MCP routing
        - Jira/Splunk specialist setup
        - LangGraph agent execution
        - an LLM call

    This function MUST remain local and deterministic.

    Returns:
        A fast-path response string when the request is an
        obvious lightweight conversational message.

        None when the request should continue through the
        normal TaskRun routing flow.
    """

    normalized = " ".join(
        request.strip().lower().split()
    )

    if not normalized:

        return None

    # --------------------------------------------------------
    # Exact/simple greetings
    # --------------------------------------------------------

    greetings = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "howdy",
        "yo",
    }

    if normalized in greetings:

        return "Hi! How can I help?"

    # --------------------------------------------------------
    # Greeting variations
    # --------------------------------------------------------

    greeting_prefixes = (
        "hi taskrun",
        "hello taskrun",
        "hey taskrun",
        "hi there",
        "hello there",
        "hey there",
    )

    if normalized in greeting_prefixes:

        return "Hi! How can I help?"

    # --------------------------------------------------------
    # Common polite/conversational messages
    # --------------------------------------------------------

    thanks_messages = {
        "thanks",
        "thank you",
        "thanks!",
        "thank you!",
        "thx",
        "ty",
    }

    if normalized in thanks_messages:

        return "You're welcome!"

    goodbye_messages = {
        "bye",
        "goodbye",
        "see you",
        "see ya",
        "good night",
    }

    if normalized in goodbye_messages:

        return "Goodbye!"

    # --------------------------------------------------------
    # Common greetings by time of day
    # --------------------------------------------------------

    time_greetings = {
        "good morning",
        "good afternoon",
        "good evening",
    }

    if normalized in time_greetings:

        return "Hi! How can I help?"

    # --------------------------------------------------------
    # Very small conversational questions
    # --------------------------------------------------------

    casual_questions = {
        "how are you",
        "how are you?",
        "how's it going",
        "how is it going",
        "what's up",
        "whats up",
    }

    if normalized in casual_questions:

        return "I'm doing well! What would you like to work on?"

    # --------------------------------------------------------
    # Not a fast-path request.
    # --------------------------------------------------------

    return None


# ============================================================
# CONTEXT ESTIMATION
# ============================================================

def _content_to_text(
    content,
) -> str:

    if content is None:

        return ""

    if isinstance(
        content,
        str,
    ):

        return content

    try:

        return json.dumps(
            content,
            ensure_ascii=False,
            default=str,
        )

    except Exception:

        return str(content)


def _message_to_text(
    message,
) -> str:

    message_type = getattr(
        message,
        "type",
        "message",
    )

    content = _content_to_text(
        getattr(
            message,
            "content",
            "",
        )
    )

    return (
        f"[{message_type}]\n"
        f"{content}"
    )


def _estimate_tokens(
    text: str,
) -> int:

    if not text:

        return 0

    return max(
        1,
        (len(text) + 3) // 4,
    )


def _estimate_messages_tokens(
    messages,
) -> int:

    total = 0

    for message in messages:

        total += _estimate_tokens(
            _message_to_text(
                message
            )
        )

    return total


def _context_limit_tokens() -> int:

    return max(
        1,
        int(
            TASKRUN_CONTEXT_WINDOW
            * CONTEXT_COMPACTION_THRESHOLD
        ),
    )


def _context_usage(
    messages,
    request: str | None = None,
):

    message_tokens = (
        _estimate_messages_tokens(
            messages
        )
    )

    request_tokens = _estimate_tokens(
        request or ""
    )

    estimated_tokens = (
        CONTEXT_SYSTEM_OVERHEAD_TOKENS
        + message_tokens
        + request_tokens
    )

    limit = _context_limit_tokens()

    ratio = (
        estimated_tokens
        / max(
            1,
            TASKRUN_CONTEXT_WINDOW,
        )
    )

    return {
        "estimated_tokens":
            estimated_tokens,

        "context_window":
            TASKRUN_CONTEXT_WINDOW,

        "threshold_tokens":
            limit,

        "ratio":
            ratio,

        "percent":
            ratio * 100,

        "over_threshold":
            estimated_tokens >= limit,
    }


# ============================================================
# BACKGROUND JOB
# ============================================================

class BackgroundJob:

    def __init__(
        self,
        job_id: str,
        request: str,
        task=None,
    ):

        self.job_id = job_id
        self.request = request
        self.task = task
        self.created_at = time.time()
        self.completed_at = None
        self.result = None
        self.error = None
        self.model_id = None

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        if self.task is None:

            return "pending"

        if self.task.cancelled():

            return "cancelled"

        if self.error is not None:

            return "failed"

        if self.result is not None:

            return "completed"

        if self.task.done():

            return "completed"

        return "running"


# ============================================================
# TASKRUN SESSION
# ============================================================

class TaskRunSession:

    def __init__(self):

        self.session_id = (
            generate_session_id()
        )

        self.config = {

            "configurable": {

                "thread_id":
                    self.session_id
            }
        }

        self.waiting_for_followup = False

        self.dry_run = False

        self.queue_mode = False

        self.memory = MemoryStore()

        self.queue = CommandQueue()

        self.undo = UndoManager()

        self.background_jobs = {}

        self.last_context_usage = None

        self.compaction_count = 0

        log_event(
            "session_started",
            self.session_id,
            dry_run=self.dry_run,
            queue_mode=self.queue_mode,
        )

    # ========================================================
    # CONFIRMATIONS
    # ========================================================

    def is_simple_confirmation(
        self,
        request: str,
    ) -> bool:

        return (
            request.strip().lower()
            in {
                "yes",
                "yeah",
                "yep",
                "sure",
                "okay",
                "ok",
                "yes please",
                "go ahead",
                "do it",
                "continue",
                "please do",
            }
        )

    # ========================================================
    # MODES
    # ========================================================

    def set_dry_run(
        self,
        enabled: bool,
    ):

        self.dry_run = enabled

        log_event(
            "dry_run_changed",
            self.session_id,
            enabled=enabled,
        )

    def set_queue_mode(
        self,
        enabled: bool,
    ):

        self.queue_mode = enabled

        log_event(
            "queue_mode_changed",
            self.session_id,
            enabled=enabled,
        )

    # ========================================================
    # MODEL PREPARATION
    # ========================================================

    async def prepare_model(
        self,
        request: str,
    ):

        selection = await select_model(
            request
        )

        model_id = selection["model"]

        print()
        print(
            "  Model: "
            f"{model_id}"
        )

        print(
            "    Provider: "
            f"{selection['provider']}"
        )

        print(
            "    Mode: "
            f"{selection['mode']}"
        )

        print(
            "    Reason: "
            f"{selection['reason']}"
        )

        print()

        log_event(
            "request_model_prepared",
            self.session_id,
            model=model_id,
            mode=selection["mode"],
            provider=selection["provider"],
            reason=selection["reason"],
            confidence=selection.get(
                "confidence",
                0.0,
            ),
        )

        return selection

    # ========================================================
    # DIRECT NO-WORK REQUEST
    # ========================================================

    async def _execute_no_work_request(
        self,
        request: str,
        selected_model_id: str,
        selection: dict,
        start_time: float,
        model_selection_duration: float,
    ):

        log_event(
            "message_started",
            self.session_id,
            request=request,
            dry_run=self.dry_run,
            queue_mode=self.queue_mode,
            model=selected_model_id,
            model_mode=selection["mode"],
            fast_path=False,
            router_gate="NO_WORK",
        )

        tokens = set_runtime_context(
            self.session_id,
            self.dry_run,
            self.queue_mode,
            selected_model_id,
        )

        model_start = time.time()

        try:

            # ------------------------------------------------
            # MEMORY
            # ------------------------------------------------

            memory_start = time.time()

            memory_context = (
                self.memory.get_context(
                    self.session_id
                )
            )

            if memory_context:

                prompt = (
                    "Relevant TaskRun memory follows. "
                    "Use it only when relevant.\n\n"
                    + memory_context
                    + "\n\nCURRENT USER REQUEST:\n"
                    + request
                )

            else:

                prompt = request

            memory_duration = (
                time.time()
                - memory_start
            )

            # ------------------------------------------------
            # DIRECT LLM
            # ------------------------------------------------

            agent_start = time.time()

            llm = create_llm(
                selected_model_id
            )

            result = await llm.ainvoke(
                prompt
            )

            agent_duration = (
                time.time()
                - agent_start
            )

            answer = _content_to_text(
                getattr(
                    result,
                    "content",
                    "",
                )
            ).strip()

            if not answer:

                answer = (
                    "(The model returned "
                    "no visible response.)"
                )

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                True,
            )

            duration = (
                time.time()
                - start_time
            )

            timing_data = {

                "total":
                    round(
                        duration,
                        3,
                    ),

                "model_selection":
                    round(
                        model_selection_duration,
                        3,
                    ),

                "supervisor_setup":
                    0.0,

                "pre_compaction":
                    0.0,

                "memory":
                    round(
                        memory_duration,
                        3,
                    ),

                "agent_execution":
                    round(
                        agent_duration,
                        3,
                    ),

                "post_compaction":
                    0.0,
            }

            log_event(
                "router_gate_bypass",
                self.session_id,
                request=request,
                router_result="NO_WORK",
                model=selected_model_id,
            )

            # router_gate is intentionally supplied only once.
            log_event(
                "request_timing",
                self.session_id,
                model=selected_model_id,
                router_gate="NO_WORK",
                total=timing_data["total"],
                model_selection=timing_data["model_selection"],
                supervisor_setup=timing_data["supervisor_setup"],
                pre_compaction=timing_data["pre_compaction"],
                memory=timing_data["memory"],
                agent_execution=timing_data["agent_execution"],
                post_compaction=timing_data["post_compaction"],
            )

            print()
            print(
                "  TaskRun timing:"
            )

            print(
                f"    Model selection: "
                f"{timing_data['model_selection']:.3f}s"
            )

            print(
                "    Router gate: "
                "NO_WORK"
            )

            print(
                "    Supervisor setup: "
                "0.000s"
            )

            print(
                f"    Memory: "
                f"{timing_data['memory']:.3f}s"
            )

            print(
                f"    Direct LLM execution: "
                f"{timing_data['agent_execution']:.3f}s"
            )

            print(
                f"    Total: "
                f"{timing_data['total']:.3f}s"
            )

            print()

            log_event(
                "message_completed",
                self.session_id,
                duration_seconds=
                    round(
                        duration,
                        3,
                    ),
                waiting_for_followup=False,
                model=selected_model_id,
                context_compactions=
                    self.compaction_count,
                fast_path=False,
                router_gate="NO_WORK",
            )

            return answer

        except asyncio.CancelledError:

            log_event(
                "message_cancelled",
                self.session_id,
                request=request,
                model=selected_model_id,
                router_gate="NO_WORK",
            )

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                False,
                "cancelled",
            )

            raise

        except Exception as exc:

            duration = (
                time.time()
                - start_time
            )

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                False,
                str(exc),
            )

            log_event(
                "message_failed",
                self.session_id,
                duration_seconds=
                    round(
                        duration,
                        3,
                    ),
                error=str(exc),
                model=selected_model_id,
                router_gate="NO_WORK",
            )

            raise

        finally:

            reset_runtime_context(
                tokens
            )

    # ========================================================
    # GET CURRENT GRAPH MESSAGES
    # ========================================================

    async def _get_graph_messages(
        self,
        supervisor,
    ):

        state = await supervisor.aget_state(
            self.config
        )

        if state is None:

            return []

        values = getattr(
            state,
            "values",
            None,
        )

        if not isinstance(
            values,
            dict,
        ):

            return []

        messages = values.get(
            "messages",
            [],
        )

        if not isinstance(
            messages,
            list,
        ):

            return []

        return messages

    # ========================================================
    # BUILD COMPACTION SUMMARY
    # ========================================================

    def _build_summary_prompt(
        self,
        old_messages,
    ):

        conversation = []

        for index, message in enumerate(
            old_messages,
            start=1,
        ):

            conversation.append(
                f"--- MESSAGE {index} ---\n"
                f"{_message_to_text(message)}"
            )

        conversation_text = (
            "\n\n".join(
                conversation
            )
        )

        return f"""
You are TaskRun's conversation compactor.

Create a compact but information-dense summary of the older
conversation below.

The summary will replace these messages in the agent's
long-term conversation context.

Preserve information that is useful for continuing the task:

- What the user is trying to accomplish.
- Important decisions already made.
- Files, paths, projects, systems, APIs, models, or tools involved.
- Important configuration details.
- Commands or operations already performed.
- Results that matter.
- Errors and their causes if established.
- Pending work.
- User requirements and constraints.
- Important facts the agent should not forget.

Do NOT invent anything.

Do NOT describe this as a summary of a summary.

Do NOT include unnecessary conversational filler.

Use concise structured sections.

OLDER CONVERSATION:

{conversation_text}
""".strip()

    # ========================================================
    # COMPACT CONTEXT
    # ========================================================

    async def compact_context(
        self,
        supervisor,
        selected_model_id: str,
        request: str | None = None,
        force: bool = False,
    ) -> bool:

        messages = await self._get_graph_messages(
            supervisor
        )

        if not messages:

            return False

        usage = _context_usage(
            messages,
            request,
        )

        self.last_context_usage = usage

        if not force and not usage[
            "over_threshold"
        ]:

            return False

        if len(messages) < (
            CONTEXT_MIN_OLD_MESSAGES
            + 1
        ):

            return False

        # ----------------------------------------------------
        # Find a safe boundary.
        # ----------------------------------------------------

        keep_count = max(
            1,
            CONTEXT_KEEP_RECENT_MESSAGES,
        )

        tentative_start = max(
            0,
            len(messages) - keep_count,
        )

        keep_from = tentative_start

        for index in range(
            tentative_start,
            len(messages),
        ):

            message = messages[index]

            message_type = getattr(
                message,
                "type",
                "",
            )

            if message_type in {
                "human",
                "user",
            }:

                keep_from = index

                break

        if keep_from <= 0:

            return False

        old_messages = messages[
            :keep_from
        ]

        recent_messages = messages[
            keep_from:
        ]

        if len(old_messages) < (
            CONTEXT_MIN_OLD_MESSAGES
        ):

            return False

        print()
        print(
            "  Context is near its limit."
        )

        print(
            "    Creating compact conversation summary..."
        )

        log_event(
            "context_compaction_started",
            self.session_id,
            model=selected_model_id,
            estimated_tokens=
                usage["estimated_tokens"],
            context_window=
                usage["context_window"],
            threshold_tokens=
                usage["threshold_tokens"],
            percent=
                round(
                    usage["percent"],
                    2,
                ),
            old_messages=
                len(old_messages),
            retained_messages=
                len(recent_messages),
        )

        summary_llm = create_llm(
            selected_model_id
        )

        summary_prompt = (
            self._build_summary_prompt(
                old_messages
            )
        )

        summary_result = await summary_llm.ainvoke(
            summary_prompt
        )

        summary = _content_to_text(
            getattr(
                summary_result,
                "content",
                "",
            )
        ).strip()

        if not summary:

            print(
                "    Compaction skipped: "
                "summary model returned no content."
            )

            log_event(
                "context_compaction_failed",
                self.session_id,
                model=selected_model_id,
                error=(
                    "Summary model returned "
                    "empty content."
                ),
            )

            return False

        removal_messages = []

        for message in old_messages:

            message_id = getattr(
                message,
                "id",
                None,
            )

            if message_id:

                removal_messages.append(
                    RemoveMessage(
                        id=message_id
                    )
                )

        if not removal_messages:

            print(
                "    Compaction skipped: "
                "old messages have no IDs."
            )

            log_event(
                "context_compaction_failed",
                self.session_id,
                model=selected_model_id,
                error=(
                    "Old messages did not "
                    "contain message IDs."
                ),
            )

            return False

        compacted_summary = (
            "TASKRUN CONVERSATION SUMMARY\n\n"
            "The following is a compacted summary "
            "of earlier conversation context. "
            "Use it as background when relevant.\n\n"
            + summary
        )

        update_messages = (
            removal_messages
            + [
                SystemMessage(
                    content=
                        compacted_summary
                )
            ]
        )

        await supervisor.aupdate_state(
            self.config,
            {
                "messages":
                    update_messages
            },
        )

        self.compaction_count += 1

        new_messages = (
            await self._get_graph_messages(
                supervisor
            )
        )

        new_usage = _context_usage(
            new_messages
        )

        self.last_context_usage = (
            new_usage
        )

        print(
            "    Context compacted."
        )

        print(
            "    Before: "
            f"~{usage['estimated_tokens']:,} "
            "tokens"
        )

        print(
            "    After:  "
            f"~{new_usage['estimated_tokens']:,} "
            "tokens"
        )

        print()

        log_event(
            "context_compaction_completed",
            self.session_id,
            model=selected_model_id,
            before_tokens=
                usage["estimated_tokens"],
            after_tokens=
                new_usage["estimated_tokens"],
            context_window=
                new_usage["context_window"],
            threshold_tokens=
                new_usage["threshold_tokens"],
            removed_messages=
                len(old_messages),
            retained_messages=
                len(recent_messages),
            compaction_count=
                self.compaction_count,
        )

        return True

    # ========================================================
    # INTERNAL REQUEST EXECUTION
    # ========================================================

    async def _execute_request(
        self,
        request: str,
        selected_model_id: str | None = None,
    ):

        request = validate_request(
            request
        )

        start_time = time.time()

        # ----------------------------------------------------
        # EXACT LOCAL FAST PATH
        # ----------------------------------------------------

        fast_response = classify_fast_path(
            request
        )

        if fast_response is not None:

            duration = (
                time.time()
                - start_time
            )

            log_event(
                "message_fast_path",
                self.session_id,
                request=request,
                response=fast_response,
                duration_seconds=
                    round(
                        duration,
                        6,
                    ),
            )

            log_event(
                "message_completed",
                self.session_id,
                duration_seconds=
                    round(
                        duration,
                        6,
                    ),
                waiting_for_followup=False,
                model=None,
                context_compactions=
                    self.compaction_count,
                fast_path=True,
            )

            print(
                f"  Fast path: "
                f"{duration * 1000:.2f} ms"
            )

            return fast_response

        # ----------------------------------------------------
        # AURELIO ROUTER GATE
        # ----------------------------------------------------

        router_start = time.time()

        router_result = classify_router_request(
            request
        )

        router_duration = (
            time.time()
            - router_start
        )

        log_event(
            "router_gate_classified",
            self.session_id,
            request=request,
            result=router_result,
            duration_seconds=
                round(
                    router_duration,
                    6,
                ),
        )

        # ----------------------------------------------------
        # NO_WORK
        # ----------------------------------------------------

        if router_result == "NO_WORK":

            model_selection_start = time.time()

            if selected_model_id is None:

                selection = await self.prepare_model(
                    request
                )

                selected_model_id = (
                    selection["model"]
                )

            else:

                spec = get_model(
                    selected_model_id
                )

                selection = {
                    "model":
                        selected_model_id,

                    "reason":
                        "Model selected before "
                        "request execution.",

                    "mode":
                        "MANUAL/RESOLVED",

                    "confidence":
                        1.0,

                    "provider":
                        spec.provider,
                }

            model_selection_duration = (
                time.time()
                - model_selection_start
            )

            return await self._execute_no_work_request(
                request=request,
                selected_model_id=selected_model_id,
                selection=selection,
                start_time=start_time,
                model_selection_duration=(
                    model_selection_duration
                ),
            )

        # ----------------------------------------------------
        # WORK
        # ----------------------------------------------------

        model_selection_start = time.time()

        if selected_model_id is None:

            selection = await self.prepare_model(
                request
            )

            selected_model_id = (
                selection["model"]
            )

        else:

            spec = get_model(
                selected_model_id
            )

            selection = {
                "model":
                    selected_model_id,

                "reason":
                    "Model selected before "
                    "request execution.",

                "mode":
                    "MANUAL/RESOLVED",

                "confidence":
                    1.0,

                "provider":
                    spec.provider,
            }

        model_selection_duration = (
            time.time()
            - model_selection_start
        )

        # ----------------------------------------------------
        # MESSAGE START
        # ----------------------------------------------------

        log_event(
            "message_started",
            self.session_id,
            request=request,
            dry_run=self.dry_run,
            queue_mode=self.queue_mode,
            model=selected_model_id,
            model_mode=selection["mode"],
            fast_path=False,
            router_gate="WORK",
        )

        tokens = set_runtime_context(
            self.session_id,
            self.dry_run,
            self.queue_mode,
            selected_model_id,
        )

        model_start = time.time()

        supervisor_start = time.time()

        try:

            is_followup = (
                self.waiting_for_followup
                and
                self.is_simple_confirmation(
                    request
                )
            )

            if is_followup:

                log_event(
                    "followup_detected",
                    self.session_id,
                    request=request,
                )

            # ------------------------------------------------
            # SUPERVISOR
            # ------------------------------------------------

            supervisor = await get_supervisor(
                request,
                model_id=selected_model_id,
            )

            supervisor_duration = (
                time.time()
                - supervisor_start
            )

            # ------------------------------------------------
            # AUTOMATIC CONTEXT COMPACTION
            # ------------------------------------------------

            pre_compaction_start = time.time()

            await self.compact_context(
                supervisor,
                selected_model_id,
                request=request,
            )

            pre_compaction_duration = (
                time.time()
                - pre_compaction_start
            )

            # ------------------------------------------------
            # MEMORY
            # ------------------------------------------------

            memory_start = time.time()

            memory_context = (
                self.memory.get_context(
                    self.session_id
                )
            )

            if memory_context:

                request_for_agent = (
                    "Relevant TaskRun memory follows. "
                    "Use it only when relevant.\n\n"
                    + memory_context
                    + "\n\nCURRENT USER REQUEST:\n"
                    + request
                )

            else:

                request_for_agent = request

            memory_duration = (
                time.time()
                - memory_start
            )

            # ------------------------------------------------
            # AGENT
            # ------------------------------------------------

            agent_start = time.time()

            result = await supervisor.ainvoke(
                {
                    "messages": [
                        {
                            "role":
                                "user",

                            "content":
                                request_for_agent,
                        }
                    ]
                },
                config=self.config,
            )

            agent_duration = (
                time.time()
                - agent_start
            )

            answer = (
                result[
                    "messages"
                ][-1].content
            )

            if not answer:

                answer = (
                    "(The agent returned "
                    "no visible response.)"
                )

            # ------------------------------------------------
            # MODEL PERFORMANCE
            # ------------------------------------------------

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                True,
            )

            # ------------------------------------------------
            # POST-REQUEST CONTEXT CHECK
            # ------------------------------------------------

            post_compaction_start = time.time()

            await self.compact_context(
                supervisor,
                selected_model_id,
            )

            post_compaction_duration = (
                time.time()
                - post_compaction_start
            )

            # ------------------------------------------------
            # FOLLOW-UP DETECTION
            # ------------------------------------------------

            lower_answer = (
                answer.lower()
            )

            question_mark = (
                "?" in answer
            )

            followup_phrases = [
                "would you like",
                "do you want",
                "should i",
                "shall i",
                "shall i proceed",
                "should i proceed",
            ]

            self.waiting_for_followup = (
                question_mark
                and
                any(
                    phrase in lower_answer
                    for phrase
                    in followup_phrases
                )
            )

            duration = (
                time.time()
                - start_time
            )

            # ------------------------------------------------
            # LATENCY INSTRUMENTATION
            # ------------------------------------------------

            timing_data = {

                "total":
                    round(
                        duration,
                        3,
                    ),

                "model_selection":
                    round(
                        model_selection_duration,
                        3,
                    ),

                "router_gate_duration":
                    round(
                        router_duration,
                        3,
                    ),

                "supervisor_setup":
                    round(
                        supervisor_duration,
                        3,
                    ),

                "pre_compaction":
                    round(
                        pre_compaction_duration,
                        3,
                    ),

                "memory":
                    round(
                        memory_duration,
                        3,
                    ),

                "agent_execution":
                    round(
                        agent_duration,
                        3,
                    ),

                "post_compaction":
                    round(
                        post_compaction_duration,
                        3,
                    ),
            }

            # IMPORTANT:
            # "router_gate" is the classification result
            # and "router_gate_duration" is the elapsed time.
            #
            # Keeping these as separate fields prevents
            # duplicate keyword arguments and also makes the
            # log semantically clearer.
            log_event(
                "request_timing",
                self.session_id,
                model=selected_model_id,
                router_gate="WORK",
                total=timing_data["total"],
                model_selection=timing_data[
                    "model_selection"
                ],
                router_gate_duration=timing_data[
                    "router_gate_duration"
                ],
                supervisor_setup=timing_data[
                    "supervisor_setup"
                ],
                pre_compaction=timing_data[
                    "pre_compaction"
                ],
                memory=timing_data[
                    "memory"
                ],
                agent_execution=timing_data[
                    "agent_execution"
                ],
                post_compaction=timing_data[
                    "post_compaction"
                ],
            )

            print()
            print(
                "  TaskRun timing:"
            )

            print(
                f"    Router gate: "
                f"{timing_data['router_gate_duration']:.3f}s"
            )

            print(
                f"    Model selection: "
                f"{timing_data['model_selection']:.3f}s"
            )

            print(
                f"    Supervisor setup: "
                f"{timing_data['supervisor_setup']:.3f}s"
            )

            print(
                f"    Pre-compaction: "
                f"{timing_data['pre_compaction']:.3f}s"
            )

            print(
                f"    Memory: "
                f"{timing_data['memory']:.3f}s"
            )

            print(
                f"    Agent execution: "
                f"{timing_data['agent_execution']:.3f}s"
            )

            print(
                f"    Post-compaction: "
                f"{timing_data['post_compaction']:.3f}s"
            )

            print(
                f"    Total: "
                f"{timing_data['total']:.3f}s"
            )

            print()

            log_event(
                "message_completed",
                self.session_id,
                duration_seconds=
                    round(
                        duration,
                        3,
                    ),
                waiting_for_followup=
                    self.waiting_for_followup,
                model=selected_model_id,
                context_compactions=
                    self.compaction_count,
                fast_path=False,
                router_gate="WORK",
            )

            return answer

        except asyncio.CancelledError:

            log_event(
                "message_cancelled",
                self.session_id,
                request=request,
                model=selected_model_id,
                router_gate="WORK",
            )

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                False,
                "cancelled",
            )

            raise

        except Exception as exc:

            duration = (
                time.time()
                - start_time
            )

            record_model_result(
                selected_model_id,
                time.time()
                - model_start,
                False,
                str(exc),
            )

            log_event(
                "message_failed",
                self.session_id,
                duration_seconds=
                    round(
                        duration,
                        3,
                    ),
                error=str(exc),
                model=selected_model_id,
                router_gate="WORK",
            )

            raise

        finally:

            reset_runtime_context(
                tokens
            )

    # ========================================================
    # SEND
    # ========================================================

    async def send(
        self,
        request: str,
        selected_model_id: str | None = None,
    ):

        return await self._execute_request(
            request,
            selected_model_id,
        )

    # ========================================================
    # BACKGROUND JOB
    # ========================================================

    async def _background_runner(
        self,
        job: BackgroundJob,
    ):

        try:

            log_event(
                "background_job_started",
                self.session_id,
                job_id=job.job_id,
                request=job.request,
            )

            result = await self._execute_request(
                job.request
            )

            job.result = result

            job.completed_at = time.time()

            log_event(
                "background_job_completed",
                self.session_id,
                job_id=job.job_id,
                model=job.model_id,
            )

            return result

        except asyncio.CancelledError:

            job.completed_at = time.time()

            log_event(
                "background_job_cancelled",
                self.session_id,
                job_id=job.job_id,
            )

            raise

        except Exception as exc:

            job.error = str(exc)

            job.completed_at = time.time()

            log_event(
                "background_job_failed",
                self.session_id,
                job_id=job.job_id,
                error=str(exc),
                model=job.model_id,
            )

            return None

    # ========================================================
    # START BACKGROUND
    # ========================================================

    def start_background(
        self,
        request: str,
    ):

        request = validate_request(
            request
        )

        job_id = (
            uuid.uuid4().hex[:8]
        )

        job = BackgroundJob(
            job_id=job_id,
            request=request,
        )

        task = asyncio.create_task(
            self._background_runner(
                job
            )
        )

        job.task = task

        self.background_jobs[
            job_id
        ] = job

        log_event(
            "background_job_created",
            self.session_id,
            job_id=job_id,
            request=request,
        )

        return job

    # ========================================================
    # GET JOB
    # ========================================================

    def get_job(
        self,
        job_id: str,
    ):

        return self.background_jobs.get(
            job_id
        )

    # ========================================================
    # LIST JOBS
    # ========================================================

    def list_jobs(self):

        return list(
            self.background_jobs.values()
        )

    # ========================================================
    # CANCEL JOB
    # ========================================================

    def cancel_job(
        self,
        job_id: str,
    ):

        job = self.get_job(
            job_id
        )

        if job is None:

            return (
                False,
                f"Job {job_id} was not found."
            )

        if job.task is None:

            return (
                False,
                f"Job {job_id} has not started."
            )

        if job.task.done():

            return (
                False,
                f"Job {job_id} is already "
                f"{job.status()}."
            )

        job.task.cancel()

        log_event(
            "background_job_cancel_requested",
            self.session_id,
            job_id=job_id,
        )

        return (
            True,
            f"Cancellation requested for job {job_id}."
        )

    # ========================================================
    # CLOSE
    # ========================================================

    async def close(self):

        jobs = list(
            self.background_jobs.values()
        )

        for job in jobs:

            if (
                job.task is not None
                and not job.task.done()
            ):

                job.task.cancel()

        if jobs:

            await asyncio.gather(
                *[
                    job.task
                    for job in jobs
                    if job.task is not None
                ],
                return_exceptions=True,
            )

        log_event(
            "session_ended",
            self.session_id,
        )
