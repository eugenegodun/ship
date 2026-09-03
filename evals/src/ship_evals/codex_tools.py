"""OpenAI function-tool schemas mirroring Codex multi-agent V2 (codex-cli 0.147)."""


def _fn(name, description, properties, required):
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": {"type": "object", "properties": properties,
                                        "required": required}}}


SPAWN_AGENT = _fn(
    "spawn_agent",
    "Spawns an agent to work on the specified task. Returns its canonical task name. The agent's "
    "final answer arrives later in your mailbox or via wait_agent.",
    {
        "task_name": {"type": "string", "description": "Short unique name for the child task"},
        "message": {"type": "string", "description": "The task brief"},
        "fork_turns": {"type": "string",
                       "description": "'none' (clean context), 'all', or a positive integer string"},
        "agent_type": {"type": "string",
                       "description": "Agent role override. Only allowed when fork_turns is not 'all'."},
    },
    ["task_name", "message"],
)

FOLLOWUP_TASK = _fn(
    "followup_task",
    "Give an existing agent a new task and trigger a turn, keeping its context.",
    {"target": {"type": "string", "description": "task_name of the agent"},
     "message": {"type": "string"}},
    ["target", "message"],
)

SEND_MESSAGE = _fn(
    "send_message",
    "Pass a message to a running agent without triggering a turn.",
    {"target": {"type": "string"}, "message": {"type": "string"}},
    ["target", "message"],
)

WAIT_AGENT = _fn(
    "wait_agent",
    "Wait for mailbox activity from child agents, up to timeout_ms.",
    {"timeout_ms": {"type": "integer"}},
    ["timeout_ms"],
)

INTERRUPT_AGENT = _fn("interrupt_agent", "Interrupt a running child agent.",
                      {"target": {"type": "string"}}, ["target"])

LIST_AGENTS = _fn("list_agents", "List child agents and their states.", {}, [])

UPDATE_PLAN = _fn(
    "update_plan",
    "Create or update the step checklist shown to the user.",
    {"plan": {"type": "array",
              "items": {"type": "object",
                        "properties": {"step": {"type": "string"},
                                       "status": {"type": "string",
                                                  "enum": ["pending", "in_progress", "completed"]}},
                        "required": ["step", "status"]}}},
    ["plan"],
)

SHELL = _fn("shell", "Run a shell command and return its output.",
            {"command": {"type": "string"}}, ["command"])

CODEX_ORCHESTRATOR_TOOLS = [SPAWN_AGENT, FOLLOWUP_TASK, SEND_MESSAGE, WAIT_AGENT, INTERRUPT_AGENT,
                            LIST_AGENTS, UPDATE_PLAN, SHELL]
