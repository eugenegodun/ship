"""Regression coverage for restoring headings without importing template prose."""
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def reporting():
    path = Path(__file__).parents[1] / "agents" / "qa" / "test_qa_agent.py"
    spec = importlib.util.spec_from_file_location("qa_reporting_assertions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def restoration(reporting):
    case = next(c.copy() for c in reporting.REPORTING_CASES if c["id"] == "restore_template_evidence")
    records = json.loads((reporting.FIXTURES / "pr_reporting_ci_regressions.json").read_text())
    report = next(c["report"] for c in records["cases"] if c["case_id"] == case["id"])
    body = case["body"] + "\n## Evidence\n" + report + "\n"
    return case, body


def test_restores_only_heading_and_results(reporting, restoration):
    case, body = restoration
    reporting.assert_reporting_body(case, body)


def test_rejects_imported_template_placeholder(reporting, restoration):
    case, body = restoration
    body = body.replace("## Evidence\n", "## Evidence\nAttach evidence.\n")
    with pytest.raises(AssertionError, match="outside the results block"):
        reporting.assert_reporting_body(case, body)


def test_preserves_guidance_already_in_pr_body(reporting, restoration):
    case, body = restoration
    guidance = "## Evidence\nAttach evidence.\n"
    case["body"] += "\n" + guidance
    case.pop("added_heading")
    body = body.replace("## Evidence\n", guidance)
    reporting.assert_reporting_body(case, body)
    with pytest.raises(AssertionError, match="outside the results block"):
        reporting.assert_reporting_body(case, body.replace("Attach evidence.\n", ""))
