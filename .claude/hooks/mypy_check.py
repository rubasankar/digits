import json
import subprocess
import sys


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")
    normalized = file_path.replace("\\", "/")
    if not normalized.endswith(".py") or "/migrations/" in normalized:
        return

    result = subprocess.run(
        ["uv", "run", "mypy", file_path], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        reason = f"mypy reports issues in {file_path}:\n{result.stdout}"
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
