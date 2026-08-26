"""Anthropic tool schemas mirroring the Claude Code tools ship/SKILL.md drives."""

AGENT = {
    "name": "Agent",
    "description": "Launch a new agent to handle a task. Runs in the background when "
                   "run_in_background is true. Returns the agent's final report and its agent id.",
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short 3-5 word task description"},
            "prompt": {"type": "string", "description": "The task brief for the agent"},
            "subagent_type": {"type": "string", "description": "Agent type, e.g. task-planner-agent"},
            "model": {"type": "string", "description": "Optional model override"},
            "run_in_background": {"type": "boolean"},
        },
        "required": ["description", "prompt"],
    },
}

SEND_MESSAGE = {
    "name": "SendMessage",
    "description": "Send a follow-up message to a previously spawned agent, continuing it "
                   "with its context intact.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "Id or name of the agent to resume"},
            "message": {"type": "string"},
        },
        "required": ["agent_id", "message"],
    },
}

ASK_USER_QUESTION = {
    "name": "AskUserQuestion",
    "description": "Ask the user one to four questions, each with 2-4 options. The user can "
                   "always answer 'Other' with free text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "header": {"type": "string"},
                        "multiSelect": {"type": "boolean"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["label", "description"],
                            },
                        },
                    },
                    "required": ["question", "header", "options", "multiSelect"],
                },
            }
        },
        "required": ["questions"],
    },
}

SKILL = {
    "name": "Skill",
    "description": "Invoke a skill by name with optional args.",
    "input_schema": {
        "type": "object",
        "properties": {"skill": {"type": "string"}, "args": {"type": "string"}},
        "required": ["skill"],
    },
}

TODO_WRITE = {
    "name": "TodoWrite",
    "description": "Create or update the session todo checklist.",
    "input_schema": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["todos"],
    },
}

TASK_OUTPUT = {
    "name": "TaskOutput",
    "description": "Retrieve the current output/result of a background agent by id.",
    "input_schema": {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    },
}

ORCHESTRATOR_TOOLS = [AGENT, SEND_MESSAGE, ASK_USER_QUESTION, SKILL, TODO_WRITE, TASK_OUTPUT]
