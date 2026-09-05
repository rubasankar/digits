import json
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path", "")
    if re.search(r"[/\\]migrations[/\\].*\.py$", file_path):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": (
                            "Migrations are normally generated, not hand-edited. "
                            "Prefer `uv run manage.py makemigrations`, then edit the "
                            "generated file only for data migrations or manual review."
                        ),
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
