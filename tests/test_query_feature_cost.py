"""#148 — query-feature-cost.py label routing (LLD v3 E3.3 §1.1 "Cost labels", story 2.2/2.3).

Issue labels go through `tracker.py` (one `view`, one `edit`); PR labels through
`_tracker_github.set_pr_labels`. The backend is faked underneath: `fake_gh` and `fake_jira`.
`apply_labels` is called in-process (cwd pinned to a throwaway git repo); the gh/Jira traffic is
what is asserted.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
sys.path.insert(0, str(BIN_DIR))

cost = __import__("query-feature-cost")
import _tracker_github  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake_gh and fake_jira are POSIX only")

METRICS = cost.UsageMetrics(cost=1.23456, inp=1000.0, out=200.0, cr=0.0, cc=0.0)
NEW = ["ai-cost-pr:1.2346", "input-tokens-pr:1000", "output-tokens-pr:200"]


def _issue_rule(number: int, labels: list[str]) -> dict:
    node = {"number": number, "title": "T", "body": "", "state": "OPEN",
            "labels": {"nodes": [{"name": n} for n in labels]}, "projectItems": {"nodes": []}}
    return {"argv_prefix": ["api", "graphql"], "argv_contains": [f"number={number}"],
            "stdout": json.dumps({"data": {"repository": {"issue": node}}}) + "\n"}


def _gh_rules(issue_labels: list[str], pr_labels: list[str] | None = None) -> list[dict]:
    rules = [_issue_rule(148, issue_labels)]
    if pr_labels is not None:
        rules.append({"argv_prefix": ["pr", "view"],
                      "stdout": json.dumps({"labels": [{"name": n} for n in pr_labels]})})
    rules += [{"argv_prefix": ["issue", "edit"]}, {"argv_prefix": ["label", "create"]},
              {"argv_prefix": ["api"]}]
    return rules


def _argv(fake_gh, *prefix: str) -> list[list[str]]:
    """Calls whose leading argv elements equal `prefix`; ("api", "repos") matches any repos/... REST path."""
    def match(argv: list[str]) -> bool:
        if prefix == ("api", "repos"):
            return argv[0] == "api" and argv[1].startswith("repos/")
        return argv[: len(prefix)] == list(prefix)
    return [c["argv"] for c in fake_gh.calls() if match(c["argv"])]


def _run_github(fake_gh, monkeypatch, issue_labels, pr=None, pr_labels=None, ref="#148"):
    fake_gh.rules(_gh_rules(issue_labels, pr_labels))
    monkeypatch.chdir(fake_gh.repo)
    cost.apply_labels(ref, METRICS, "pr", pr=pr)


class TestGitHubIssueLabels:
    def test_one_issue_edit_carries_all_adds_and_stale_removes(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, ["kind:task", "ai-cost-pr:0.5", "input-tokens-pr:9"])
        edits = _argv(fake_gh, "issue", "edit")
        assert len(edits) == 1
        argv = edits[0]
        assert argv[:3] == ["issue", "edit", "148"]
        assert argv[argv.index("--add-label") + 1] == ",".join(NEW)
        assert set(argv[argv.index("--remove-label") + 1].split(",")) == {"ai-cost-pr:0.5", "input-tokens-pr:9"}

    def test_current_labels_are_not_removed_nor_other_stages_touched(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, [NEW[0], "ai-cost-final:2.0", "kind:task"])
        argv = _argv(fake_gh, "issue", "edit")[0]
        assert "--remove-label" not in argv

    def test_no_gh_issue_view_or_rest_issue_calls(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, ["ai-cost-pr:0.5"])
        assert _argv(fake_gh, "issue", "view") == []
        assert _argv(fake_gh, "api", "repos") == []

    def test_label_create_runs_once_per_new_label_on_github(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, [])
        created = [a[2] for a in _argv(fake_gh, "label", "create")]
        assert created == NEW

    def test_prints_one_line_per_label(self, fake_gh, monkeypatch, capsys):
        _run_github(fake_gh, monkeypatch, [])
        out = capsys.readouterr().out.splitlines()
        assert out == [f"Label applied: {n} -> issue #148" for n in NEW]

    def test_accepts_a_bare_number_ref(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, [], ref="148")
        assert len(_argv(fake_gh, "issue", "edit")) == 1

    def test_failing_edit_never_raises(self, fake_gh, monkeypatch):
        fake_gh.rules([_issue_rule(148, []), {"argv_prefix": ["issue", "edit"], "exit": 1, "stderr": "boom"}])
        monkeypatch.chdir(fake_gh.repo)
        cost.apply_labels("#148", METRICS, "pr")


class TestGitHubPrLabels:
    def test_pr_labels_route_through_rest_not_gh_pr_edit(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, [], pr=7, pr_labels=["ai-cost-pr:0.5", "bug"])
        assert _argv(fake_gh, "pr", "edit") == []
        deletes = [a for a in _argv(fake_gh, "api", "repos") if "DELETE" in a]
        posts = [a for a in _argv(fake_gh, "api", "repos") if "POST" in a]
        assert [d[1] for d in deletes] == ["repos/{owner}/{repo}/issues/7/labels/ai-cost-pr%3A0.5"]
        assert [p[p.index("-f") + 1] for p in posts] == [f"labels[]={n}" for n in NEW]
        assert all(p[1] == "repos/{owner}/{repo}/issues/7/labels" for p in posts)

    def test_no_pr_means_no_rest_calls(self, fake_gh, monkeypatch):
        _run_github(fake_gh, monkeypatch, [])
        assert _argv(fake_gh, "api", "repos") == []
        assert _argv(fake_gh, "pr", "view") == []

    def test_pr_target_is_named_in_output(self, fake_gh, monkeypatch, capsys):
        _run_github(fake_gh, monkeypatch, [], pr=7, pr_labels=[])
        assert capsys.readouterr().out.splitlines()[0] == f"Label applied: {NEW[0]} -> issue #148, PR #7"


class TestSetPrLabels:
    def test_deletes_encoded_names_then_posts_adds(self, fake_gh, monkeypatch):
        fake_gh.rules([{"argv_prefix": ["api"]}])
        monkeypatch.chdir(fake_gh.repo)
        _tracker_github.set_pr_labels(9, ["a:1"], ["b c:2"])
        calls = [c["argv"] for c in fake_gh.calls()]
        assert calls == [
            ["api", "repos/{owner}/{repo}/issues/9/labels/b%20c%3A2", "--method", "DELETE"],
            ["api", "repos/{owner}/{repo}/issues/9/labels", "--method", "POST", "-f", "labels[]=a:1"],
        ]

    def test_failures_are_swallowed(self, fake_gh, monkeypatch):
        fake_gh.rules([{"argv_prefix": ["api"], "exit": 1, "stderr": "nope"}])
        monkeypatch.chdir(fake_gh.repo)
        _tracker_github.set_pr_labels(9, ["a:1"], ["b:2"])

    def test_nothing_to_do_makes_no_call(self, fake_gh, monkeypatch):
        monkeypatch.chdir(fake_gh.repo)
        _tracker_github.set_pr_labels(9, [], [])
        assert fake_gh.calls() == []


class TestJira:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        path = tmp_path / "jrepo"
        path.mkdir()
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        monkeypatch.chdir(path)
        return path

    def test_stale_labels_replaced_in_one_edit(self, fake_jira, repo):
        key = fake_jira.add_issue("T", labels=["keep", "ai-cost-pr:0.5", "output-tokens-pr:1"])
        cost.apply_labels(key, METRICS, "pr")
        assert sorted(fake_jira.issue(key)["labels"]) == sorted(["keep", *NEW])
        puts = [c for c in fake_jira.calls() if c["method"] == "PUT"]
        assert len(puts) == 1

    def test_no_gh_call_is_made(self, fake_jira, repo, tmp_path, monkeypatch):
        gh_log = tmp_path / "gh.log"
        shim = tmp_path / "bin"
        shim.mkdir()
        (shim / "gh").write_text(f'#!/bin/sh\necho "$@" >> "{gh_log}"\nexit 1\n')
        (shim / "gh").chmod(0o755)
        monkeypatch.setenv("PATH", f"{shim}:{__import__('os').environ['PATH']}")
        key = fake_jira.add_issue("T")
        cost.apply_labels(key, METRICS, "pr")
        assert not gh_log.exists()
        assert sorted(fake_jira.issue(key)["labels"]) == sorted(NEW)

    def test_output_names_the_jira_key(self, fake_jira, repo, capsys):
        key = fake_jira.add_issue("T")
        cost.apply_labels(key, METRICS, "pr")
        assert capsys.readouterr().out.splitlines()[0] == f"Label applied: {NEW[0]} -> issue {key}"


class TestFeatureId:
    def test_issue_flag_resolves_the_feature_id_through_the_resolver(self, fake_gh, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(fake_gh.repo)
        monkeypatch.setenv("EDF_FEATURE_PREFIX", "ZZ")
        monkeypatch.setenv("EDF_FEATURE_PROM_DIR", str(tmp_path))
        (tmp_path / "session_feature.prom").write_text("")
        monkeypatch.setattr(sys, "argv", ["query-feature-cost.py", "--issue", "#148"])
        with pytest.raises(SystemExit):
            cost.main()
        assert "No session data found for ZZ-148" in capsys.readouterr().out

    def test_malformed_ref_prints_error_line_and_exits_1(self, fake_gh, monkeypatch, capsys):
        monkeypatch.chdir(fake_gh.repo)
        monkeypatch.setattr(sys, "argv", ["query-feature-cost.py", "--issue", "not a ref"])
        with pytest.raises(SystemExit) as exc:
            cost.main()
        assert exc.value.code == 1
        assert capsys.readouterr().err.startswith("Error: invalid issue reference")


def test_source_has_no_gh_issue_access():
    src = (BIN_DIR / "query-feature-cost.py").read_text(encoding="utf-8")
    assert '"issue"' not in src
    assert "/issues/" not in src
