import pytest


@pytest.mark.codex
def test_roles_installed_first_dispatch_is_planner_role_with_clean_fork_and_no_model_question(run_codex_decision):
    d = run_codex_decision("roles_installed_invoke")
    planner = d.spawns("ship-task-planner-agent")
    assert planner, "first dispatch must be spawn_agent with agent_type ship-task-planner-agent " + d.diagnostics()
    assert planner[0].input_parameters.get("fork_turns") == "none"
    assert "LEX-1398" in planner[0].input_parameters.get("task_name", "")
    assert "which model" not in d.text.lower() and "planner model" not in d.text.lower(), (
        "Stage 0 model questions are skipped on Codex " + d.diagnostics())
    assert not d.named("shell"), "preflight already passed - no second check"


@pytest.mark.codex
def test_roles_missing_stops_and_names_the_installer(run_codex_decision):
    d = run_codex_decision("roles_missing_invoke")
    assert not d.named("spawn_agent"), "never spawn with roles missing " + d.diagnostics()
    assert "install-codex-agents.sh" in d.text, d.diagnostics()


@pytest.mark.codex
def test_first_verified_tree_spawns_qa_role_with_deferred_pr_brief(run_codex_decision):
    d = run_codex_decision("impl_verified")
    qa = d.spawns("ship-qa-agent")
    assert qa, "qa-agent Phase A is launched after the first verified tree " + d.diagnostics()
    assert qa[0].input_parameters.get("fork_turns") == "none"
    brief = qa[0].input_parameters["message"].lower()
    assert "pr" in brief and any(k in brief for k in ("does not exist", "not exist", "no pr", "deferred", "not yet")), (
        "the deferred-PR instruction must be in the qa brief " + d.diagnostics())
    assert not [c for c in d.named("followup_task") if "implementator" in c.input_parameters.get("target", "")]


@pytest.mark.codex
def test_critical_finding_resumes_implementator_via_followup_task(run_codex_decision):
    d = run_codex_decision("review_critical_round1")
    follow = d.named("followup_task")
    assert follow and follow[0].input_parameters.get("target", "").endswith("LEX-1398-implementator"), (
        "fix rounds resume the SAME implementator task " + d.diagnostics())
    assert "refund" in follow[0].input_parameters["message"].lower()
    assert not d.spawns("ship-implementator-agent"), "never a fresh implementator per round"


@pytest.mark.codex
def test_clean_review_spawns_git_role_with_worktree_draft_and_no_coauthor(run_codex_decision):
    d = run_codex_decision("review_clean")
    git = d.spawns("ship-git-agent")
    assert git, "clean verdict exits the loop into Stage 5's git role " + d.diagnostics()
    brief = git[0].input_parameters["message"].lower()
    assert "/tmp/worktrees/lex-1398" in brief and "draft" in brief and "co-author" in brief
    assert git[0].input_parameters.get("fork_turns") == "none"
