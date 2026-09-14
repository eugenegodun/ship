#!/usr/bin/env python3
"""
Parses Claude Code transcript files on disk to compute real per-agent token
totals for a /ship pipeline run. Stdlib only. Prints one JSON object to stdout.

Per-subagent transcripts live at:
  ~/.claude/projects/<project-dir>/<session-id>/subagents/agent-<agentId>.jsonl
with a sidecar agent-<agentId>.meta.json carrying agentType/description.

Do NOT trust the inline toolUseResult.usage / totalTokens summary in the
parent session file for token totals -- it reflects only the subagent's last
turn and undercounts by up to ~40x. It is used here only for metadata
(status, tool-use count, duration, resolvedModel).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

USAGE_KEYS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_creation", "cache_creation_input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
)


def empty_tokens():
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "total": 0}


def add_usage(tokens, usage):
    for key, usage_key in USAGE_KEYS:
        tokens[key] += usage.get(usage_key, 0) or 0
    tokens["total"] = tokens["input"] + tokens["output"] + tokens["cache_creation"] + tokens["cache_read"]


def parse_ts(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_transcript(path, max_excerpt):
    tokens = empty_tokens()
    turns = 0
    model = None
    tool_error_count = 0
    final_text = None
    first_ts = last_ts = None

    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            msg = obj.get("message") or {}
            content = msg.get("content")

            if obj.get("type") == "assistant":
                turns += 1
                model = msg.get("model", model)
                usage = msg.get("usage") or {}
                add_usage(tokens, usage)
                if isinstance(content, list):
                    text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    if text_parts:
                        final_text = "\n".join(text_parts)

            tur = obj.get("toolUseResult")
            if isinstance(tur, dict) and (tur.get("is_error") or tur.get("status") == "error"):
                tool_error_count += 1
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                        tool_error_count += 1

    duration_ms = None
    if first_ts and last_ts:
        try:
            duration_ms = int((parse_ts(last_ts) - parse_ts(first_ts)).total_seconds() * 1000)
        except ValueError:
            duration_ms = None

    excerpt = None
    if final_text:
        excerpt = final_text[:max_excerpt] + ("…" if len(final_text) > max_excerpt else "")

    return {
        "turns": turns,
        "model": model,
        "tokens": tokens,
        "duration_ms": duration_ms,
        "tool_error_count": tool_error_count,
        "final_message_excerpt": excerpt,
    }


def scan_parent_for_agent_summaries(parent_path):
    summaries = {}
    with open(parent_path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            tur = obj.get("toolUseResult")
            if isinstance(tur, dict) and tur.get("agentId"):
                summaries[tur["agentId"]] = {
                    "agentType": tur.get("agentType"),
                    "resolvedModel": tur.get("resolvedModel"),
                    "status": tur.get("status"),
                    "totalToolUseCount": tur.get("totalToolUseCount"),
                    "totalDurationMs": tur.get("totalDurationMs"),
                }
    return summaries


def project_dir_name(project_path):
    return re.sub(r"[^A-Za-z0-9]", "-", project_path)


def find_session_by_ticket(projects_dir, session_files, ticket):
    needle = ticket.lower()
    for sp in session_files:
        sid = sp.stem
        subs = projects_dir / sid / "subagents"
        if subs.exists():
            for mp in subs.glob("agent-*.meta.json"):
                try:
                    meta = json.loads(mp.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                if needle in json.dumps(meta).lower():
                    return sp
        try:
            if needle in sp.read_text(errors="replace").lower():
                return sp
        except OSError:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="explicit session id to analyze")
    parser.add_argument("--ticket", help="Jira ticket key to locate the session by")
    parser.add_argument("--project-path", help="repo path (defaults to cwd)")
    parser.add_argument("--max-excerpt", type=int, default=500)
    args = parser.parse_args()

    project_path = args.project_path or os.getcwd()
    projects_dir = Path.home() / ".claude" / "projects" / project_dir_name(project_path)

    if not projects_dir.exists():
        print(json.dumps({"error": f"no project transcripts dir at {projects_dir}"}))
        sys.exit(1)

    session_files = sorted(projects_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not session_files:
        print(json.dumps({"error": f"no session .jsonl files under {projects_dir}"}))
        sys.exit(1)

    if args.session:
        session_path = projects_dir / f"{args.session}.jsonl"
        if not session_path.exists():
            print(json.dumps({"error": f"no session file for id {args.session}"}))
            sys.exit(1)
    elif args.ticket:
        session_path = find_session_by_ticket(projects_dir, session_files, args.ticket)
        if session_path is None:
            print(json.dumps({"error": f"no session found mentioning ticket {args.ticket}"}))
            sys.exit(1)
    else:
        session_path = session_files[0]

    session_id = session_path.stem
    subagents_dir = projects_dir / session_id / "subagents"

    parent_summaries = scan_parent_for_agent_summaries(session_path)
    coordinator = parse_transcript(session_path, args.max_excerpt)

    agents = []
    note = None
    if subagents_dir.exists():
        for agent_file in sorted(subagents_dir.glob("agent-*.jsonl")):
            agent_id = agent_file.stem[len("agent-"):]
            meta_path = subagents_dir / f"agent-{agent_id}.meta.json"
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except (json.JSONDecodeError, OSError):
                    meta = {}

            parsed = parse_transcript(agent_file, args.max_excerpt)
            parent_info = parent_summaries.get(agent_id, {})

            agents.append({
                "agentId": agent_id,
                "agentType": meta.get("agentType") or parent_info.get("agentType") or "unknown",
                "description": meta.get("description"),
                "resolvedModel": parent_info.get("resolvedModel") or parsed["model"],
                "status": parent_info.get("status"),
                "turns": parsed["turns"],
                "duration_ms": parsed["duration_ms"] or parent_info.get("totalDurationMs"),
                "tool_error_count": parsed["tool_error_count"],
                "tokens": parsed["tokens"],
                "final_message_excerpt": parsed["final_message_excerpt"],
            })
    else:
        note = "no subagents directory found for this session -- it may not have run any Task-tool agents"

    by_role = {}
    for a in agents:
        role = a["agentType"]
        acc = by_role.setdefault(role, {**empty_tokens(), "count": 0})
        for key in ("input", "output", "cache_creation", "cache_read", "total"):
            acc[key] += a["tokens"][key]
        acc["count"] += 1

    grand_total = coordinator["tokens"]["total"] + sum(a["tokens"]["total"] for a in agents)

    result = {
        "project_dir": str(projects_dir),
        "session_id": session_id,
        "session_file": str(session_path),
        "coordinator": coordinator,
        "agents": agents,
        "by_role": by_role,
        "grand_total_tokens": grand_total,
    }
    if note:
        result["note"] = note

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
