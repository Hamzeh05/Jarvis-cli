from dataclasses import dataclass
from enum import Enum
import re


# ============================================================
# REQUEST INTENT
# ============================================================

class RequestIntent(str, Enum):

    CASUAL = "casual"
    GENERAL = "general"
    WORK = "work"


@dataclass(frozen=True)
class Classification:

    intent: RequestIntent
    reason: str


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize(request: str) -> str:

    text = request.strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


# ============================================================
# WORK INDICATORS
#
# These are checked FIRST.
#
# This is important because a message can contain casual
# language while still asking TaskRun to perform real work.
#
# Example:
#
# "hey, can you check WUK-2312?"
#
# must be WORK, not CASUAL.
# ============================================================

_WORK_PATTERNS = (

    # --------------------------------------------------------
    # Jira
    # --------------------------------------------------------

    r"\b[A-Z]{2,10}-\d+\b",

    r"\bjira\b",

    r"\bjql\b",

    r"\bissue\b",

    r"\bticket\b",

    # --------------------------------------------------------
    # Splunk
    # --------------------------------------------------------

    r"\bsplunk\b",

    r"\bspl\b",

    r"\bindex(?:es)?\b",

    r"\blog(?:s)?\b",

    r"\bevents?\b",

    r"\bauthentication\b",

    r"\bauth(?:entication)?\s+(?:failure|failures|error|errors)\b",

    # --------------------------------------------------------
    # Computer / filesystem
    # --------------------------------------------------------

    r"\bfile\b",

    r"\bfiles\b",

    r"\bfolder\b",

    r"\bdirectory\b",

    r"\bpath\b",

    r"\bfilesystem\b",

    r"\bfilesystem\b",

    r"\bhome directory\b",

    r"\bworking directory\b",

    # --------------------------------------------------------
    # Shell / command execution
    # --------------------------------------------------------

    r"\brun\b",

    r"\bexecute\b",

    r"\bcommand\b",

    r"\bshell\b",

    r"\bterminal\b",

    r"\bbash\b",

    r"\bscript\b",

    # --------------------------------------------------------
    # Docker
    # --------------------------------------------------------

    r"\bdocker\b",

    r"\bcontainer(?:s)?\b",

    # --------------------------------------------------------
    # File/system operations
    # --------------------------------------------------------

    r"\bcreate\b",

    r"\bdelete\b",

    r"\bremove\b",

    r"\bmove\b",

    r"\bcopy\b",

    r"\brename\b",

    r"\bwrite\b",

    r"\bread\b",

    r"\blist\b",

    r"\bsearch\b",

    r"\bfind\b",

    r"\bopen\b",

    r"\bdownload\b",

    r"\bupload\b",

    r"\binstall\b",

    # --------------------------------------------------------
    # System information / processes
    # --------------------------------------------------------

    r"\bsystem info\b",

    r"\bsystem information\b",

    r"\bprocess(?:es)?\b",

    r"\bmemory usage\b",

    r"\bcpu usage\b",

    r"\bdisk usage\b",

    r"\bdisk space\b",

    # --------------------------------------------------------
    # TaskRun-specific work
    # --------------------------------------------------------

    r"\btaskrun\b",

    r"\bworkspace\b",

    r"\brepository\b",

    r"\brepo\b",

    r"\bproject files\b",
)


_COMPILED_WORK_PATTERNS = tuple(
    re.compile(
        pattern,
        re.IGNORECASE,
    )
    for pattern in _WORK_PATTERNS
)


# ============================================================
# CASUAL INDICATORS
#
# These describe normal social/conversational interaction.
#
# This is intentionally broader than a list of exact phrases.
# ============================================================

_CASUAL_PATTERNS = (

    # Greetings
    r"^(?:hi|hello|hey|hiya|howdy|yo)[!.]?$",

    r"^(?:hi|hello|hey)\s+(?:there|taskrun)[!.]?$",

    r"^good\s+(?:morning|afternoon|evening)[!.]?$",

    # Small talk
    r"^how\s+are\s+you(?:\s+doing)?[!?]?$",

    r"^how(?:'s| is)\s+it\s+going[!?]?$",

    r"^what(?:'s| is)\s+up[!?]?$",

    r"^how\s+have\s+you\s+been[!?]?$",

    r"^nice\s+to\s+meet\s+you[!.]?$",

    r"^nice\s+talking\s+to\s+you[!.]?$",

    # Thanks
    r"^(?:thanks|thank\s+you|thx|ty)[!.]?$",

    r"^(?:thanks|thank\s+you)\s+(?:a\s+lot|so\s+much)[!.]?$",

    # Farewells
    r"^(?:bye|goodbye|see\s+you|see\s+ya)[!.]?$",

    r"^good\s+night[!.]?$",

    r"^talk\s+to\s+you\s+(?:later|soon)[!.]?$",

    # Simple social acknowledgements
    r"^(?:cool|great|awesome|nice)[!.]?$",

    r"^(?:sounds\s+good|that\s+sounds\s+good)[!.]?$",

    r"^(?:got\s+it|gotcha)[!.]?$",

)


_COMPILED_CASUAL_PATTERNS = tuple(
    re.compile(
        pattern,
        re.IGNORECASE,
    )
    for pattern in _CASUAL_PATTERNS
)


# ============================================================
# GENERAL KNOWLEDGE INDICATORS
#
# These are NOT fast-path responses.
#
# They mean:
#
# "The user wants an answer, but there is no external
# system/computer work required."
#
# The main LLM can answer these without Supervisor/MCP.
# ============================================================

_GENERAL_PATTERNS = (

    r"^what\s+is\b",

    r"^what\s+are\b",

    r"^what\s+does\b",

    r"^what\s+do\b",

    r"^why\s+does\b",

    r"^why\s+do\b",

    r"^why\s+is\b",

    r"^why\s+are\b",

    r"^how\s+does\b",

    r"^how\s+do\b",

    r"^how\s+can\s+i\b",

    r"^how\s+would\b",

    r"^explain\b",

    r"^describe\b",

    r"^define\b",

    r"^tell\s+me\s+about\b",

    r"^difference\s+between\b",

    r"^compare\b",

    r"^give\s+me\s+an?\s+explanation\b",

    r"^help\s+me\s+understand\b",

)


_COMPILED_GENERAL_PATTERNS = tuple(
    re.compile(
        pattern,
        re.IGNORECASE,
    )
    for pattern in _GENERAL_PATTERNS
)


# ============================================================
# HELPERS
# ============================================================

def _matches_any(
    text: str,
    patterns,
) -> bool:

    return any(
        pattern.search(text)
        for pattern in patterns
    )


def _looks_like_work(text: str) -> bool:

    return _matches_any(
        text,
        _COMPILED_WORK_PATTERNS,
    )


def _looks_casual(text: str) -> bool:

    return _matches_any(
        text,
        _COMPILED_CASUAL_PATTERNS,
    )


def _looks_general(text: str) -> bool:

    return _matches_any(
        text,
        _COMPILED_GENERAL_PATTERNS,
    )


# ============================================================
# PUBLIC CLASSIFIER
# ============================================================

def classify_request(
    request: str,
) -> Classification:

    """
    Classify a TaskRun request before expensive processing.

    Classification order:

        1. WORK
        2. CASUAL
        3. GENERAL
        4. GENERAL fallback

    WORK is checked first so that a request containing casual
    language but asking TaskRun to perform an operation is
    never accidentally treated as casual.

    Examples:

        "hi"
            -> CASUAL

        "how are you doing?"
            -> CASUAL

        "what is machine learning?"
            -> GENERAL

        "explain Docker"
            -> GENERAL

        "hey, check WUK-2312"
            -> WORK

        "can you list ~/taskrun?"
            -> WORK

        "search Splunk for errors"
            -> WORK
    """

    text = _normalize(request)

    if not text:

        return Classification(
            intent=RequestIntent.GENERAL,
            reason="Empty request.",
        )

    # --------------------------------------------------------
    # WORK MUST WIN
    # --------------------------------------------------------

    if _looks_like_work(text):

        return Classification(
            intent=RequestIntent.WORK,
            reason=(
                "Request contains indicators of "
                "external-system, computer, "
                "filesystem, Jira, Splunk, or "
                "execution work."
            ),
        )

    # --------------------------------------------------------
    # CASUAL
    # --------------------------------------------------------

    if _looks_casual(text):

        return Classification(
            intent=RequestIntent.CASUAL,
            reason=(
                "Request is normal social or "
                "conversational interaction."
            ),
        )

    # --------------------------------------------------------
    # GENERAL
    # --------------------------------------------------------

    if _looks_general(text):

        return Classification(
            intent=RequestIntent.GENERAL,
            reason=(
                "Request asks for general information "
                "or explanation without requiring "
                "external system work."
            ),
        )

    # --------------------------------------------------------
    # SAFE DEFAULT
    #
    # Unknown requests should NOT automatically become WORK.
    #
    # The main LLM can handle ambiguous/general conversation,
    # while explicit work indicators above still enter TaskRun.
    # --------------------------------------------------------

    return Classification(
        intent=RequestIntent.GENERAL,
        reason=(
            "No explicit work indicators detected; "
            "treating the request as general conversation."
        ),
    )


# ============================================================
# CONVENIENCE HELPERS
# ============================================================

def is_casual_request(
    request: str,
) -> bool:

    return (
        classify_request(request).intent
        == RequestIntent.CASUAL
    )


def is_general_request(
    request: str,
) -> bool:

    return (
        classify_request(request).intent
        == RequestIntent.GENERAL
    )


def is_work_request(
    request: str,
) -> bool:

    return (
        classify_request(request).intent
        == RequestIntent.WORK
    )
