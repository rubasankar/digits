import json
import subprocess
import sys


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return

    subprocess.run(
        ["uv", "run", "ruff", "check", "--fix", file_path],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["uv", "run", "ruff", "format", file_path], capture_output=True, check=False
    )

    remaining = subprocess.run(
        ["uv", "run", "ruff", "check", file_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if remaining.returncode != 0:
        reason = f"ruff still reports issues in {file_path}:\n{remaining.stdout}"
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": reason,
                    "hookSpecificOutput": {"hookEventName": "PostToolUse"},
                }
            )
        )


if __name__ == "__main__":
    main()
