from ship_evals.artifacts import load_agent, load_skill


def test_load_skill_strips_frontmatter_and_keeps_body():
    body = load_skill("ship")
    assert not body.startswith("---")
    assert "name: ship" not in body.split("\n\n")[0]
    assert "# ship — feature pipeline orchestrator" in body
    assert "GATE 2" in body


def test_load_agent_reads_each_pipeline_agent():
    for name in ("spec-agent", "task-planner-agent", "reviewer-agent", "qa-agent"):
        body = load_agent(name)
        assert not body.startswith("---")
        assert len(body) > 500


def test_reviewer_contract_line_present():
    assert "Ready to commit? [Yes | No | With fixes]" in load_agent("reviewer-agent")
