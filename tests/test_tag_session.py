"""Tests for bin/tag-session.py --skill mode — tagging non-issue tasks.

feature-core-style skills tag sessions with "<PREFIX>-<issue>". Skills with no
GitHub issue (requirements, architect, kickoff, discovery, retro, ...) use
--skill instead, which must produce a short, collision-free tag without a
shared counter file.
"""

import json
import pathlib
import re
import subprocess
import sys

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"


def _run(cwd, env, *args):
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "tag-session.py"), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _init_repo_with_session(tmp_path, monkeypatch, session_id="11111111-1111-1111-1111-111111111111"):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    project_key = str(repo.resolve()).lower()
    project_key = project_key.replace(":\\", "--").replace("\\", "-").replace("/", "-").replace(":", "")
    claude_dir = tmp_path / "home" / ".claude" / "projects" / project_key
    claude_dir.mkdir(parents=True)
    (claude_dir / f"{session_id}.jsonl").write_text("", encoding="utf-8")

    env = {**__import__("os").environ, "HOME": str(tmp_path / "home"),
           "USERPROFILE": str(tmp_path / "home"), "CLAUDE_CODE_SESSION_ID": session_id}
    return repo, claude_dir, session_id, env


def test_skill_mode_tags_session_with_short_id(tmp_path, monkeypatch):
    repo, claude_dir, session_id, env = _init_repo_with_session(tmp_path, monkeypatch)

    result = _run(repo, env, "--skill", "requirements")
    assert result.returncode == 0, result.stderr

    jsonl = json.loads((claude_dir / f"{session_id}.jsonl").read_text(encoding="utf-8").strip())
    assert jsonl["type"] == "custom-title"
    assert re.match(r"^REQ-[0-9a-z]{5}$", jsonl["customTitle"])


def test_skill_mode_appends_cont_suffix(tmp_path, monkeypatch):
    repo, claude_dir, session_id, env = _init_repo_with_session(tmp_path, monkeypatch)

    result = _run(repo, env, "--skill", "architect", "--cont")
    assert result.returncode == 0, result.stderr

    jsonl = json.loads((claude_dir / f"{session_id}.jsonl").read_text(encoding="utf-8").strip())
    assert re.match(r"^ARCH-[0-9a-z]{5} \(cont\)$", jsonl["customTitle"])


def test_unmapped_skill_falls_back_to_uppercase_name(tmp_path, monkeypatch):
    repo, claude_dir, session_id, env = _init_repo_with_session(tmp_path, monkeypatch)

    result = _run(repo, env, "--skill", "totally-new-skill")
    assert result.returncode == 0, result.stderr

    jsonl = json.loads((claude_dir / f"{session_id}.jsonl").read_text(encoding="utf-8").strip())
    assert jsonl["customTitle"].startswith("TOTALLYN-")


def test_rejects_both_issue_and_skill(tmp_path, monkeypatch):
    repo, _claude_dir, _session_id, env = _init_repo_with_session(tmp_path, monkeypatch)

    result = _run(repo, env, "55", "--skill", "requirements")
    assert result.returncode != 0
    assert "exactly one of" in result.stderr


def _load_module():
    import importlib.util
    sys.path.insert(0, str(BIN_DIR))
    spec = importlib.util.spec_from_file_location("tag_session", BIN_DIR / "tag-session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retagging_a_session_replaces_its_previous_feature(tmp_path):
    # One session running /drift-scan then /retro used to end up with two
    # feature_id rows for the same session_id, which breaks the dashboard's
    # `* on(session_id)` join with "many-to-many matching not allowed".
    mod = _load_module()
    prom = tmp_path / "session_feature.prom"
    mod.update_prom_file(prom, "s1", "DRIFT-aaaaa")
    mod.update_prom_file(prom, "s2", "EDF-7")
    mod.update_prom_file(prom, "s1", "RETRO-bbbbb")

    lines = [l for l in prom.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    assert lines == [
        'claude_session_feature{session_id="s2",feature_id="EDF-7"} 1',
        'claude_session_feature{session_id="s1",feature_id="RETRO-bbbbb"} 1',
    ]


def test_rejects_neither_issue_nor_skill(tmp_path, monkeypatch):
    repo, _claude_dir, _session_id, env = _init_repo_with_session(tmp_path, monkeypatch)

    result = _run(repo, env)
    assert result.returncode != 0
    assert "exactly one of" in result.stderr
