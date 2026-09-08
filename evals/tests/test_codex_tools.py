from ship_evals.codex_tools import CODEX_ORCHESTRATOR_TOOLS


def test_codex_tool_set_matches_multi_agent_v2():
    names = {t["function"]["name"] for t in CODEX_ORCHESTRATOR_TOOLS}
    assert names == {"spawn_agent", "followup_task", "send_message", "wait_agent",
                     "interrupt_agent", "list_agents", "update_plan", "shell"}
    spawn = next(t for t in CODEX_ORCHESTRATOR_TOOLS if t["function"]["name"] == "spawn_agent")
    props = spawn["function"]["parameters"]["properties"]
    assert set(props) == {"task_name", "message", "fork_turns", "agent_type"}
    assert "model" not in props, "V2 spawn_agent has no model override"
