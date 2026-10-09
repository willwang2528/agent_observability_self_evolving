"""Isolated Codex invocation and auditable event accounting for a small pilot."""
from pathlib import Path

CODEX_BINARY = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
MODEL = "gpt-6-astra"
REASONING_EFFORT = "xhigh"


def build_command(cwd: Path, schema: Path, output: Path, instructions: Path) -> list[str]:
    command = [CODEX_BINARY, "--no-daemon", "exec", "--ignore-user-config", "--ephemeral",
               "--skip-git-repo-check", "--sandbox", "read-only", "--json",
               "--model", MODEL, "--cd", str(cwd),
               "--output-schema", str(schema), "--output-last-message", str(output)]
    settings = [f'model_reasoning_effort="{REASONING_EFFORT}"',
                f'model_instructions_file="{instructions}"',
                'web_search="disabled"', "project_doc_max_bytes=0",
                "memories.use_memories=false", "memories.generate_memories=false",
                "features.view_image=false", "features.memories=false",
                "features.shell_tool=false", "features.unified_exec=false",
                "features.multi_agent=false", "features.apps=false",
                "features.plugins=false", "features.remote_plugin=false",
                "features.skill_search=false", "features.skip_host_skill_discovery=true",
                "skills.include_instructions=false", "features.code_mode_host=false",
                "features.computer_use=false", "features.browser_use=false",
                "features.browser_use_external=false", "features.in_app_browser=false",
                "features.image_generation=false", "features.sleep_tool=false",
                "features.hooks=false",
                "features.shell_snapshot=false", "features.goals=false"]
    for setting in settings:
        command.extend(["--config", setting])
    command.append("-")
    return command


def summarize_events(events: list[dict]) -> dict:
    tools = []
    failures = []
    warnings = []
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    completed = False
    allowed_items = {"agent_message", "reasoning"}
    for event in events:
        kind = event.get("type")
        if kind in {"item.started", "item.completed", "item.updated"}:
            item_kind = event.get("item", {}).get("type", "unknown")
            if item_kind == "error":
                message = str(event.get("item", {}).get("message", ""))
                if message not in warnings:
                    warnings.append(message)
            elif item_kind not in allowed_items and item_kind not in tools:
                tools.append(item_kind)
        if kind == "turn.completed":
            completed = True
            for key in usage:
                usage[key] += int(event.get("usage", {}).get(key, 0))
        if kind in {"turn.failed", "error"}:
            error = event.get("error", event)
            failures.append(str(error.get("message", error)))
    return {"completed": completed, "usage": usage,
            "tool_item_types": tools, "failures": failures, "warnings": warnings}
