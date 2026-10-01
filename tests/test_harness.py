import tempfile

from pathlib import Path

from harness.policy import (
    classify_operation,
    protected_reason,
)

from harness.safety import (
    classify_command,
)

from harness.verification import (
    verify_operation,
)


# ============================================================
# SAFETY
# ============================================================

def test_blocked_rm_rf():

    result = classify_command(
        "rm -rf important"
    )

    assert result.level == "BLOCKED"


def test_blocked_mkfs():

    result = classify_command(
        "mkfs.ext4 /dev/sda"
    )

    assert result.level == "BLOCKED"


def test_safe_pwd():

    result = classify_command(
        "pwd"
    )

    assert result.level == "SAFE"


def test_risky_rm():

    result = classify_command(
        "rm test.txt"
    )

    assert result.level == "RISKY"


# ============================================================
# PROTECTED PATHS
# ============================================================

def test_protected_ssh():

    path = (
        Path.home()
        / ".ssh"
        / "id_test"
    )

    result = protected_reason(
        str(path)
    )

    assert result is not None


def test_protected_env():

    result = protected_reason(
        str(
            Path.cwd()
            / ".env"
        )
    )

    assert result is not None


def test_protected_write_operation():

    result = classify_operation(

        "write_file",

        {
            "path":
                str(
                    Path.home()
                    / ".ssh"
                    / "test"
                ),

            "content":
                "x",
        },
    )

    assert result.level == "BLOCKED"


# ============================================================
# VERIFICATION
# ============================================================

def test_directory_verification():

    with tempfile.TemporaryDirectory() as tmp:

        path = (
            Path(tmp)
            / "created"
        )

        path.mkdir()

        ok, message = (
            verify_operation(

                "make_directory",

                {
                    "path":
                        str(path)
                },

                "Created directory",
            )
        )

        assert ok is True

        assert (
            "exists"
            in message.lower()
        )


def test_file_verification():

    with tempfile.TemporaryDirectory() as tmp:

        path = (
            Path(tmp)
            / "test.txt"
        )

        content = "hello TaskRun"

        path.write_text(
            content,
            encoding="utf-8",
        )

        ok, message = (
            verify_operation(

                "write_file",

                {
                    "path":
                        str(path),

                    "content":
                        content,
                },

                "Wrote file",
            )
        )

        assert ok is True


# ============================================================
# DELETE VERIFICATION
# ============================================================

def test_delete_verification():

    with tempfile.TemporaryDirectory() as tmp:

        path = (
            Path(tmp)
            / "deleted.txt"
        )

        ok, message = (
            verify_operation(

                "delete_path",

                {
                    "path":
                        str(path)
                },

                "Deleted",
            )
        )

        assert ok is True


# ============================================================
# COPY VERIFICATION
# ============================================================

def test_copy_verification():

    with tempfile.TemporaryDirectory() as tmp:

        source = (
            Path(tmp)
            / "source.txt"
        )

        destination = (
            Path(tmp)
            / "destination.txt"
        )

        source.write_text(
            "TaskRun",
            encoding="utf-8",
        )

        destination.write_text(
            "TaskRun",
            encoding="utf-8",
        )

        ok, message = (
            verify_operation(

                "copy_path",

                {
                    "source":
                        str(source),

                    "destination":
                        str(destination),
                },

                "Copied",
            )
        )

        assert ok is True
