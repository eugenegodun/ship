"""Exercise actual filesystem boundaries, including linked Git worktrees."""
import types
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'plugins/ship/skills/engineering-insights/scripts/validate_target.py'
module = types.ModuleType('insights_target')
exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'), module.__dict__)
validate = module.validate_target


@pytest.fixture
def repo(tmp_path):
    path = tmp_path.resolve() / 'repo with spaces'
    path.mkdir()
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    return path


def test_missing_and_existing_notes_are_not_modified(repo):
    target = repo / 'INSIGHTS.md'
    assert validate(str(repo), str(target), 'insights')['target'] == str(target.resolve())
    assert not target.exists()
    target.write_text('existing notes')
    validate(str(repo), str(target), 'insights')
    assert target.read_text() == 'existing notes'


@pytest.mark.parametrize('name', ['other.md', 'AGENTS.md', 'CLAUDE.md'])
def test_wrong_notes_name(repo, name):
    with pytest.raises(ValueError):
        validate(str(repo), str(repo / name), 'insights')


def test_external_nested_and_traversal_targets(repo):
    nested = repo / 'nested'
    nested.mkdir()
    for target in [repo.parent / 'INSIGHTS.md', nested / 'INSIGHTS.md', repo / '..' / repo.name / 'INSIGHTS.md']:
        with pytest.raises(ValueError):
            validate(str(repo), str(target), 'insights')
    with pytest.raises(ValueError):
        validate(str(nested), str(nested / 'INSIGHTS.md'), 'insights')


@pytest.mark.parametrize('kind', ['directory', 'symlink', 'dangling', 'hardlink', 'fifo'])
def test_unsafe_leaf(repo, kind):
    target = repo / 'INSIGHTS.md'
    outside = repo.parent / 'outside'
    outside.write_text('untouched')
    if kind == 'directory':
        target.mkdir()
    elif kind == 'symlink':
        target.symlink_to(outside)
    elif kind == 'dangling':
        target.symlink_to(repo.parent / 'missing')
    elif kind == 'hardlink':
        os.link(outside, target)
    else:
        os.mkfifo(target)
    with pytest.raises(ValueError):
        validate(str(repo), str(target), 'insights')
    assert outside.read_text() == 'untouched'


@pytest.mark.parametrize('name', ['AGENTS.md', 'CLAUDE.md'])
def test_map_requires_existing_file(repo, name):
    target = repo / name
    with pytest.raises(ValueError):
        validate(str(repo), str(target), 'map')
    target.write_text('original instructions')
    validate(str(repo), str(target), 'map')
    assert target.read_text() == 'original instructions'


def test_relative_paths_and_nonrepo_rejected(repo):
    with pytest.raises(ValueError):
        validate('.', 'INSIGHTS.md', 'insights')
    with pytest.raises(subprocess.CalledProcessError):
        validate(str(repo.parent), str(repo.parent / 'INSIGHTS.md'), 'insights')


def test_linked_worktree_and_git_env(repo, monkeypatch):
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'initial'], check=True)
    worktree = repo.parent / 'linked worktree'
    subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-q', '-b', 'test-linked', str(worktree)], check=True)
    monkeypatch.setenv('GIT_WORK_TREE', str(repo.parent))
    assert validate(str(worktree), str(worktree / 'INSIGHTS.md'), 'insights')['repo_root'] == str(worktree.resolve())
    with pytest.raises(ValueError):
        validate(str(worktree), str(repo / 'INSIGHTS.md'), 'insights')


def test_cli_failure_does_not_create_file(repo):
    target = repo / 'other.md'
    result = subprocess.run(['python3', str(SCRIPT), '--repo-root', str(repo), '--target', str(target),
                             '--kind', 'insights'], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'error' in result.stdout
    assert not target.exists()


def test_symlink_root_and_parent_cannot_retarget_approval(repo):
    alias = repo / 'alias'
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError):
        validate(str(repo), str(alias / 'INSIGHTS.md'), 'insights')
    other = repo.parent / 'other-repo'
    other.mkdir()
    subprocess.run(['git', 'init', '-q', str(other)], check=True)
    alias.unlink()
    alias.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        validate(str(alias), str(alias / 'INSIGHTS.md'), 'insights')
    assert not (other / 'INSIGHTS.md').exists()


def test_symlink_loop_is_concise_cli_failure(repo):
    loop = repo / 'loop'
    loop.symlink_to(loop)
    result = subprocess.run(['python3', str(SCRIPT), '--repo-root', str(loop),
                             '--target', str(loop / 'INSIGHTS.md'), '--kind', 'insights'],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert 'error' in result.stdout
    assert 'Traceback' not in result.stderr
