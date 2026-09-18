#!/usr/bin/env python3
"""Read-only insights target preflight. Does not establish user approval or lock files."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess


def validate_target(repo_root, target, kind):
    root, candidate = Path(repo_root), Path(target)
    if not root.is_absolute() or not candidate.is_absolute():
        raise ValueError('Repository root and target must be absolute paths')
    if '..' in root.parts or '..' in candidate.parts:
        raise ValueError('Traversal components are not allowed')
    resolved_root = root.resolve(strict=True)
    if root != resolved_root:
        raise ValueError('Use the canonical worktree root with approval for that exact root')
    # Do not let inherited Git routing variables select a different repository/index.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True, env=env, check=True)
    if Path(result.stdout.strip()).resolve(strict=True) != root:
        raise ValueError('Repository root must be the exact Git worktree root')
    if candidate.parent != root:
        raise ValueError('Target must be directly inside the approved repository root')
    allowed = {'insights': {'INSIGHTS.md'}, 'map': {'AGENTS.md', 'CLAUDE.md'}}
    if kind not in allowed or candidate.name not in allowed[kind]:
        raise ValueError('Target filename is not allowed for this operation')
    try:
        info = candidate.lstat()
    except FileNotFoundError:
        if kind == 'map':
            raise ValueError('Map file must already exist') from None
    else:
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Target must be a regular file, not a symlink or special file')
        if info.st_nlink != 1:
            raise ValueError('Multiply-linked targets are not allowed')
    return {'repo_root': str(root), 'target': str(candidate), 'kind': kind}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--kind', required=True, choices=['insights', 'map'])
    args = parser.parse_args()
    try:
        result = validate_target(args.repo_root, args.target, args.kind)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(json.dumps({'error': str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
