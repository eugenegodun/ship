"""Temporary reproduction: five independent samples per revision, no retries or prompt fixes."""
import json
import os
from pathlib import Path
import re
import runpy
import subprocess

from ship_evals.codex_harness import call_codex_model
from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("OPENAI_API_KEY is missing")

fixture_dir = Path("orchestrator_codex/fixtures/transcripts")
conftest = runpy.run_path("orchestrator_codex/conftest.py")
Decision = conftest["CodexDecision"]
test = runpy.run_path("orchestrator_codex/test_codex_dispatch.py")[
    "test_critical_finding_resumes_implementator_via_followup_task"
]


def system_at(ref):
    def read(path):
        return subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
    skill = re.sub(r"\A---\n.*?\n---\n", "", read("plugins/ship/skills/ship/SKILL.md"), flags=re.S).lstrip("\n")
    return skill + "\n\n" + read("plugins/ship/skills/ship/references/codex-dispatch.md")


records = []
for sample in range(1, 6):
    for revision, ref in [("pr26", "2877c66"), ("base", "c70a63e")]:
        response = None

        def run_case(name):
            global response
            messages = json.loads((fixture_dir / f"{name}.json").read_text())["messages"]
            response = call_codex_model(system_at(ref), messages, CODEX_ORCHESTRATOR_TOOLS, model="gpt-4.1")
            return Decision(response)

        failure = None
        try:
            test(run_case)
        except AssertionError as exc:
            failure = str(exc)
        choice = response.choices[0]
        record = {
            "revision": revision,
            "ref": ref,
            "sample": sample,
            "passed": failure is None,
            "assertion": failure,
            "model": response.model,
            "response_id": response.id,
            "system_fingerprint": response.system_fingerprint,
            "finish_reason": choice.finish_reason,
            "usage": response.usage.model_dump() if response.usage else None,
            "message": choice.message.model_dump(),
        }
        records.append(record)
        Path("pr26-diagnostics.json").write_text(json.dumps(records, indent=2))
        print(json.dumps(record), flush=True)

lines = ["## PR #26 diagnostic samples", "", "These are independent model samples; no automatic retries.", "",
         "| Revision | Passed | Failed |", "|---|---:|---:|"]
for revision in ("pr26", "base"):
    rows = [r for r in records if r["revision"] == revision]
    passed = sum(r["passed"] for r in rows)
    lines.append(f"| {revision} | {passed} | {len(rows) - passed} |")
summary = "\n".join(lines) + "\n"
print(summary)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
        output.write(summary)
