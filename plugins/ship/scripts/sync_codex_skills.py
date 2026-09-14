#!/usr/bin/env python3
"""Generate the Codex plugin's skill entrypoints and bundled resources.

Shared skills in skills/ remain the source of truth for frontmatter and the
engineering-insights/workflow-retro skills. Only the generated ship body is
replaced, using skills/ship/references/codex-dispatch.md as its source of truth.
Claude continues to load skills/; the Codex manifest loads codex-skills/.

The entire codex-skills/ tree is generated. Do not edit it directly. This script
copies every resource byte-for-byte and removes obsolete generated files.

  python3 plugins/ship/scripts/sync_codex_skills.py
  python3 plugins/ship/scripts/sync_codex_skills.py --check
"""
import argparse
import sys
from pathlib import Path


def generate(plugin_dir):
    source = Path(plugin_dir) / "skills"
    output = {
        path.relative_to(source): path.read_bytes()
        for path in sorted(source.rglob("*")) if path.is_file()
    }
    shared = output[Path("ship/SKILL.md")]
    if not shared.startswith(b"---\n") or b"\n---\n" not in shared:
        raise ValueError("skills/ship/SKILL.md has no YAML frontmatter")
    frontmatter = shared.split(b"\n---\n", 1)[0] + b"\n---\n"
    output[Path("ship/SKILL.md")] = (
        frontmatter + b"\n" + output[Path("ship/references/codex-dispatch.md")]
    )
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report drift without changing files")
    parser.add_argument("--plugin-dir", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    plugin = Path(args.plugin_dir)
    destination = plugin / "codex-skills"
    try:
        output = generate(plugin)
        existing = {path.relative_to(destination) for path in destination.rglob("*") if path.is_file()}
        obsolete = existing - output.keys()
        changed = [path for path, content in output.items()
                   if path not in existing or (destination / path).read_bytes() != content]
        if args.check:
            if changed or obsolete:
                print("codex skills are out of date - run plugins/ship/scripts/sync_codex_skills.py:", file=sys.stderr)
                for path in sorted(set(changed) | obsolete):
                    print(f"  {path}", file=sys.stderr)
                return 1
            return 0
        for path in changed:
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(output[path])
            target.chmod((plugin / "skills" / path).stat().st_mode & 0o777)
            print(f"wrote {target}")
        for path in sorted(obsolete):
            (destination / path).unlink()
            print(f"removed {destination / path}")
        for directory in sorted(destination.rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    except (OSError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
