"""Tests for shell script argument parsing and dry-run paths.

These tests invoke shell scripts directly via bash. They test argument validation
and dry-run modes — not live GitHub operations.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "bin"
HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "hooks"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf" / "starters" / "scripts"

# Git for Windows provides bash at this path (MSYS2/Cygwin-based).
_BASH_EXE = shutil.which("bash") or "bash"


def _to_msys2_path(p):
    """Convert Windows path to MSYS2/Cygwin format: C:\\foo\\bar → /c/foo/bar"""
    s = str(p).replace("\\", "/")
    if s[1:2] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _bash(script_path, *args, cwd=None):
    """Run a bash script with arguments."""
    result = subprocess.run(
        [_BASH_EXE, _to_msys2_path(script_path), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )
    return result


def _gh_available():
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _tracker(*args, cwd=None):
    """Run tracker.py (the GitHub backend) with arguments."""
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "tracker.py"), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
    )


gh_required = pytest.mark.skipif(not _gh_available(), reason="gh CLI not authenticated")


# ── tracker.py create ────────────────────────────────────────────────────────


class TestTrackerCreate:
    def test_missing_title(self):
        result = _tracker("create", "--body", "test body")
        assert result.returncode != 0
        assert "title" in result.stderr.lower()

    def test_missing_body(self):
        result = _tracker("create", "--title", "test title")
        assert result.returncode != 0
        assert "body" in result.stderr.lower()

    def test_unknown_option(self):
        result = _tracker("create", "--unknown-flag")
        assert result.returncode != 0

    # Dry-run output is covered hermetically by the create-dry-run goldens in test_tracker_github.py
    # (a live-gh dry run dedupes against real issues and is not reproducible).

    def test_no_args(self):
        result = _tracker("create")
        assert result.returncode != 0


# ── create-feature-pr.sh ─────────────────────────────────────────────────────


class TestCreateFeaturePr:
    def test_missing_all_args(self):
        result = _bash(BIN_DIR / "create-feature-pr.sh")
        assert result.returncode != 0

    def test_missing_required_arg(self):
        result = _bash(
            BIN_DIR / "create-feature-pr.sh",
            "--issue", "42",
            "--title", "Test PR",
        )
        assert result.returncode != 0
        assert "Missing required argument" in result.stderr

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "create-feature-pr.sh", "--bogus")
        assert result.returncode != 0

    def test_runs_without_claude_plugin_root_env(self):
        # The script must not depend on $CLAUDE_PLUGIN_ROOT being set in the Bash
        # environment — that variable is only resolved by Claude Code in hooks.json
        # and skill markdown, not exported into tool-invoked commands. We unset it
        # and invoke with a missing-arg path: the script should fail on the missing
        # arg, NOT on "CLAUDE_PLUGIN_ROOT: unbound variable".
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "create-feature-pr.sh"),
             "--issue", "1", "--title", "x"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert "CLAUDE_PLUGIN_ROOT" not in result.stderr
        assert "unbound variable" not in result.stderr
        assert "Missing required argument" in result.stderr


# ── review-package.sh ────────────────────────────────────────────────────────


def _git_repo_with_change(tmp_path):
    """Init a repo with one commit and one uncommitted modification."""
    def run(*args):
        subprocess.run(args, cwd=tmp_path, check=True, capture_output=True)

    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    target = tmp_path / "a.txt"
    target.write_text("line1\nline2\nline3\n")
    run("git", "add", "a.txt")
    run("git", "commit", "-qm", "init")
    target.write_text("line1\nCHANGED\nline3\nline4\n")
    return tmp_path


class TestReviewPackage:
    def test_no_args_shows_usage(self):
        result = _bash(BIN_DIR / "review-package.sh")
        assert result.returncode == 1
        assert "usage:" in result.stderr

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "review-package.sh", "--bogus")
        assert result.returncode == 1
        assert "Unknown option" in result.stderr

    def test_pr_requires_a_number(self):
        result = _bash(BIN_DIR / "review-package.sh", "--pr", "abc")
        assert result.returncode == 1
        assert "expects a number" in result.stderr

    def test_outside_git_repo_fails_clearly(self, tmp_path):
        result = _bash(BIN_DIR / "review-package.sh", "--local", cwd=tmp_path)
        assert result.returncode == 1
        assert "git repository" in result.stderr.lower()

    def test_empty_diff_exits_3(self, tmp_path):
        _git_repo_with_change(tmp_path)
        subprocess.run(["git", "checkout", "-q", "--", "a.txt"], cwd=tmp_path, check=True)
        result = _bash(BIN_DIR / "review-package.sh", "--local", cwd=tmp_path)
        assert result.returncode == 3
        assert "empty" in result.stderr.lower()

    def test_local_mode_writes_package_and_keeps_diff_off_stdout(self, tmp_path):
        _git_repo_with_change(tmp_path)
        result = _bash(BIN_DIR / "review-package.sh", "--local", cwd=tmp_path)
        assert result.returncode == 0

        # stdout carries the path and the numstat table — never the diff itself.
        assert result.stdout.startswith("package: ")
        assert "numstat:" in result.stdout
        assert "2\t1\ta.txt" in result.stdout  # 2 added, 1 removed
        assert "CHANGED" not in result.stdout

        pkg = pathlib.Path(result.stdout.splitlines()[0].split("package: ", 1)[1])
        assert pkg.is_file()
        body = pkg.read_text()
        assert "## Files changed" in body
        assert "## Diff" in body
        assert "+CHANGED" in body

    def test_package_dir_is_self_ignoring(self, tmp_path):
        _git_repo_with_change(tmp_path)
        result = _bash(BIN_DIR / "review-package.sh", "--local", cwd=tmp_path)
        assert result.returncode == 0
        # The package must not show up as an untracked file: a self-ignoring
        # .gitignore inside .edf/ keeps scratch out of `git status` without
        # touching the project's tracked .gitignore.
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_path,
            capture_output=True, text=True, check=True,
        )
        assert ".edf" not in status.stdout

    def test_out_flag_overrides_destination(self, tmp_path):
        _git_repo_with_change(tmp_path)
        dest = tmp_path / "custom.diff"
        result = _bash(
            BIN_DIR / "review-package.sh", "--local", "--out", "custom.diff",
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert dest.is_file()
        assert "+CHANGED" in dest.read_text()


# ── brief-package.sh ─────────────────────────────────────────────────────────


_LLD_FIXTURE = (
    BIN_DIR.parent / "docs" / "design" / "v1" / "lld-v1-e1-2-review-feedback.md"
)
_REQ_FIXTURE = BIN_DIR.parent / "docs" / "requirements" / "v1-requirements.md"


def _write_graphql_gh_shim(fake_bin, title, body_file, log_file=None):
    """Fake `gh` answering `gh api graphql` with the issue envelope the tracker
    GitHub backend parses (data.repository.issue). Any other gh call fails."""
    fake_bin.mkdir(exist_ok=True)
    envelope_py = (
        "import json,sys;"
        "print(json.dumps({'data':{'repository':{'issue':{'number':999999,"
        f"'title':{title!r},'body':open(sys.argv[1]).read(),'state':'OPEN',"
        "'labels':{'nodes':[]},'projectItems':{'nodes':[]}}}}}))"
    )
    log = f"echo \"$*\" >> '{_to_msys2_path(log_file)}'\n" if log_file else ""
    shim = fake_bin / "gh"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        + log
        + "case \"$1 $2\" in\n"
        "  'api graphql')\n"
        f"    python3 -c \"{envelope_py}\" '{_to_msys2_path(body_file)}' ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    shim.chmod(0o755)
    return shim


class TestBriefPackage:
    def test_no_args_shows_usage(self):
        result = _bash(BIN_DIR / "brief-package.sh")
        assert result.returncode == 1
        assert "usage:" in result.stderr

    def test_missing_lld_shows_usage(self):
        result = _bash(BIN_DIR / "brief-package.sh", "--issue", "1")
        assert result.returncode == 1
        assert "usage:" in result.stderr

    def test_bogus_ref_fails_with_clear_message(self, tmp_path):
        # Refs are opaque (12, #12, SCRUM-12): no numeric pre-check, but an
        # unreadable ref must fail with exit 1 and a clear message.
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        gh_shim = fake_bin / "gh"
        gh_shim.write_text("#!/usr/bin/env bash\nexit 1\n")
        gh_shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
             "--issue", "abc", "--lld", "none", "--out", str(tmp_path / "b.md")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 1
        assert "cannot read issue" in result.stderr
        assert "expects a number" not in result.stderr

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "brief-package.sh", "--bogus")
        assert result.returncode == 1
        assert "Unknown option" in result.stderr

    def test_outside_git_repo_fails_clearly(self, tmp_path):
        result = _bash(
            BIN_DIR / "brief-package.sh", "--issue", "1", "--lld", "none",
            cwd=tmp_path,
        )
        assert result.returncode == 1
        assert "git repository" in result.stderr.lower()

    @gh_required
    def test_lld_and_requirements_resolve_via_anchors(self, tmp_path):
        # Issue #50 is closed/merged; its "Design reference" anchor and the
        # matching coverage-manifest `req:` entry are stable fixtures already
        # committed to this repo — a real end-to-end resolution path, not a
        # synthetic one.
        out = tmp_path / "brief.md"
        result = _bash(
            BIN_DIR / "brief-package.sh",
            "--issue", "50",
            "--lld", str(_LLD_FIXTURE),
            "--requirements", str(_REQ_FIXTURE),
            "--out", str(out),
        )
        assert result.returncode == 0
        assert "lld: resolved:LLD-v1-e1-2-command-wiring" in result.stdout
        assert (
            "requirements: resolved:"
            "REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment"
        ) in result.stdout

        body = out.read_text()
        # Full issue body, not just the acceptance-criteria heading — BDD
        # specs, Files to create/modify, etc. must all be present too.
        assert "## BDD specs" in body
        assert "## Files to create/modify" in body
        assert "insertReviewComment" in body and "target resolution" in body

        # Part A (design rationale) is paired with Part B (implementation)
        # for the same story, not just the anchored Part B section alone.
        assert "Part A" in body and "Design rationale" in body and "2.3" in body
        assert "Part B" in body and "Implementation" in body
        assert "## 2.3 Command wiring and target resolution" in body
        assert "Story 2.1: Insert" in body  # from the requirements section
        # Must stop before the next LLD section anchor — no bleed-through
        # into the next story's Part A or Part B content.
        assert "## 2.4 Packaging" not in body
        assert "LLD-v1-e1-2-packaging-security" not in body

    @gh_required
    def test_no_lld_and_no_anchor_falls_back_to_full_requirements(self, tmp_path):
        # Issue #79 has no LLD and references no REQ- anchor directly — both
        # fallback paths in one call. A fallback must include full content,
        # never omit it silently.
        out = tmp_path / "brief.md"
        result = _bash(
            BIN_DIR / "brief-package.sh",
            "--issue", "79",
            "--lld", "none",
            "--requirements", str(_REQ_FIXTURE),
            "--out", str(out),
        )
        assert result.returncode == 0
        assert "lld: none" in result.stdout
        assert "requirements: fallback-full-files:1" in result.stdout

        body = out.read_text()
        assert "(no LLD for this issue)" in body
        assert "brief-package.sh` exists" in body  # from issue #79's own AC list
        # Full body means sibling sections survive too, not just the AC list.
        assert "## Acceptance criteria" in body
        assert "## What to change" in body

    def test_full_issue_body_included_even_with_no_ac_heading(self, tmp_path):
        # A body with no "## Acceptance criteria" heading: the whole body is
        # always included verbatim, so there is nothing to fall back from.
        fake_bin = tmp_path / "fakebin"
        body_file = tmp_path / "body.txt"
        body_file.write_text("Schema foundations summary.\n\n## Test plan\n- run it\n")
        _write_graphql_gh_shim(fake_bin, "Schema foundations", body_file)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        out = tmp_path / "brief.md"
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
             "--issue", "1", "--lld", "none", "--out", str(out)],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, result.stderr
        body = out.read_text()
        assert "schema foundations" in body.lower()
        assert "## Test plan" in body

    def test_lld_falls_back_to_full_file_when_no_anchor_referenced(self, tmp_path):
        # No "## Design reference" section and no "#LLD-..." anchor anywhere in
        # the body: resolution must fail closed to the full LLD file.
        fake_bin = tmp_path / "fakebin"
        body_file = tmp_path / "body.txt"
        body_file.write_text("Plain issue with no design reference.\n")
        _write_graphql_gh_shim(fake_bin, "No anchors", body_file)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        out = tmp_path / "brief.md"
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
             "--issue", "1", "--lld", str(_LLD_FIXTURE), "--out", str(out)],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, result.stderr
        assert "lld: fallback-full-file" in result.stdout
        assert "## Execution Order" in out.read_text()

    @gh_required
    def test_part_a_task_number_matching_is_boundary_exact(self, tmp_path):
        # Regression guard for the redesign's exact-boundary requirement: matching
        # task "2.3" must not also match "2.30" (longer number, same prefix) or
        # "12.3" (same suffix, different epic). No real LLD file in this repo has
        # such a colliding sibling section, so this synthesizes one — reusing
        # issue #50's real, stable "Design reference" anchor (task number "2.3")
        # against a purpose-built LLD file that plants both decoys ahead of the
        # real section.
        lld = tmp_path / "lld-decoy.md"
        lld.write_text(
            "# Part A — Human-Reviewable Design\n\n"
            "## 2.30 Decoy expanded task number\n\n"
            "DECOY-PART-A-BODY-2-30\n\n"
            "## 12.3 Decoy different epic\n\n"
            "DECOY-PART-A-BODY-12-3\n\n"
            "## 2.3 Command wiring and target resolution\n\n"
            "REAL-PART-A-BODY-2-3\n\n"
            "# Part B — Agent Implementation Detail\n\n"
            '<a id="LLD-v1-e1-2-command-wiring"></a>\n\n'
            "## 2.3 Command wiring and target resolution — Implementation\n\n"
            "REAL-PART-B-BODY\n"
        )
        out = tmp_path / "brief.md"
        result = _bash(
            BIN_DIR / "brief-package.sh",
            "--issue", "50",
            "--lld", str(lld),
            "--out", str(out),
        )
        assert result.returncode == 0, result.stderr
        assert "lld: resolved:LLD-v1-e1-2-command-wiring" in result.stdout

        body = out.read_text()
        assert "REAL-PART-A-BODY-2-3" in body
        assert "REAL-PART-B-BODY" in body
        assert "DECOY-PART-A-BODY-2-30" not in body
        assert "DECOY-PART-A-BODY-12-3" not in body

    def test_resolves_every_design_reference_anchor_and_unions_their_reqs(self, tmp_path):
        # No real closed issue in this repo names more than one LLD-<anchor> in its
        # "## Design reference" section, so the redesign's "every anchor, not just
        # the first" resolution and the requirements union across every resolved
        # anchor have no real issue-body fixture. Shims only the tracker's `gh api graphql`
        # transport with a synthetic body naming two real, already-anchored
        # sections of the real LLD fixture; the LLD-file and coverage-manifest
        # extraction underneath stays entirely real.
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        body_file = tmp_path / "body.txt"
        body_file.write_text(
            "## Design reference\n"
            "[a](x#LLD-v1-e1-2-command-wiring) and "
            "[b](y#LLD-v1-e1-2-packaging-security)\n\n"
            "## Acceptance criteria\n- [ ] does a thing\n"
        )
        _write_graphql_gh_shim(fake_bin, 'Synthetic multi-anchor issue', body_file)

        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        out = tmp_path / "brief.md"
        result = subprocess.run(
            [
                _BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
                "--issue", "999999",
                "--lld", str(_LLD_FIXTURE),
                "--requirements", str(_REQ_FIXTURE),
                "--out", str(out),
            ],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, result.stderr
        assert (
            "lld: resolved:"
            "LLD-v1-e1-2-command-wiring,LLD-v1-e1-2-packaging-security"
        ) in result.stdout
        assert (
            "requirements: resolved:"
            "REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment,"
            "REQ-vscode-extension-review-feedback-test-framework-local-packaging"
        ) in result.stdout

        body = out.read_text()
        assert "## 2.3 Command wiring and target resolution" in body
        assert "## 2.4 Packaging, install verification and security review" in body
        # Bounded: neither Part A section bleeds into the next story's.
        assert "## 2.5 Diagram click-through overlay" not in body

    def test_design_reference_section_present_but_anchorless_does_not_widen_search(self, tmp_path):
        # Regression guard for a pr-review finding: a "## Design reference" section
        # that exists but names no #LLD-... anchor must NOT fall back to a
        # whole-body search — that would risk picking up an unrelated anchor-looking
        # mention elsewhere (here, in "## Concerns"). Only a MISSING section
        # ("## Design reference" heading absent entirely, covered by
        # test_lld_falls_back_to_full_file_when_no_anchor_referenced using real
        # issue #1) should trigger the whole-body fallback.
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        body_file = tmp_path / "body.txt"
        body_file.write_text(
            "## Design reference\n"
            "(LLD pending — not yet written)\n\n"
            "## Concerns\n"
            "See also lld-v1-e1-2-review-feedback.md#LLD-v1-e1-2-command-wiring for prior art.\n"
        )
        _write_graphql_gh_shim(fake_bin, 'Synthetic anchorless-design-reference issue', body_file)

        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        out = tmp_path / "brief.md"
        result = subprocess.run(
            [
                _BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
                "--issue", "999998",
                "--lld", str(_LLD_FIXTURE),
                "--out", str(out),
            ],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, result.stderr
        # Must NOT pick up the Concerns-section mention — falls back to the
        # full LLD file instead, same as "no anchor anywhere" would.
        assert "lld: fallback-full-file" in result.stdout

        body = out.read_text()
        assert "## Execution Order" in body  # proof the whole file was included

    @pytest.mark.parametrize("ref,expected", [("12", "12"), ("#12", "12")])
    def test_ref_forms_read_issue_once_via_tracker(self, tmp_path, ref, expected):
        # One tracker call (one `gh api graphql`), no `gh issue view`; output
        # file is named without any leading '#'.
        fake_bin = tmp_path / "fakebin"
        body_file = tmp_path / "body.txt"
        body_file.write_text("## What\nSYNTHETIC-BODY-MARKER\n")
        log = tmp_path / "gh.log"
        _write_graphql_gh_shim(fake_bin, "Synthetic tracker issue", body_file, log)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
             "--issue", ref, "--lld", "none"],
            capture_output=True, text=True, timeout=30, env=env, cwd=repo,
        )
        assert result.returncode == 0, result.stderr
        out = repo / ".edf" / f"brief-{expected}.md"
        assert result.stdout.splitlines()[0] == f"brief: {out}"
        assert "  lld: none" in result.stdout
        assert "  requirements: none" in result.stdout
        text = out.read_text()
        assert "Synthetic tracker issue" in text.splitlines()[0]
        assert "SYNTHETIC-BODY-MARKER" in text
        calls = log.read_text().splitlines()
        assert len(calls) == 1, calls
        assert calls[0].startswith("api graphql")
        assert "issue view" not in log.read_text()

    def test_non_numeric_ref_is_accepted_when_tracker_resolves_it(self, tmp_path):
        # Refs are opaque: the numeric-only check is gone, so a ref the shim
        # cannot resolve fails at the tracker, not at argument validation.
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        gh_shim = fake_bin / "gh"
        gh_shim.write_text("#!/usr/bin/env bash\nexit 1\n")
        gh_shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "brief-package.sh"),
             "--issue", "SCRUM-12", "--lld", "none", "--out", str(tmp_path / "b.md")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 1
        assert "expects a number" not in result.stderr
        assert "cannot read issue" in result.stderr

    def test_script_source_has_no_gh_issue_view(self):
        assert "gh issue view" not in (BIN_DIR / "brief-package.sh").read_text()


    @gh_required
    def test_default_output_path_is_self_ignoring(self):
        # Mirrors review-package.sh's `test_package_dir_is_self_ignoring` (issue #79
        # AC: ".edf/ ... is git-ignored"). No --out given, so the script must fall
        # back to REPO_ROOT/.edf/brief-<issue>.md and keep it out of `git status`
        # via the same self-writing .edf/.gitignore, not by relying on a tracked
        # .gitignore entry.
        repo_root = pathlib.Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
        expected = repo_root / ".edf" / "brief-79.md"
        try:
            result = _bash(
                BIN_DIR / "brief-package.sh",
                "--issue", "79", "--lld", "none",
                "--requirements", str(_REQ_FIXTURE),
            )
            assert result.returncode == 0
            assert result.stdout.startswith("brief: ")
            assert expected.is_file()

            gitignore = repo_root / ".edf" / ".gitignore"
            assert gitignore.is_file()
            assert gitignore.read_text().strip() == "*"

            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo_root,
                capture_output=True, text=True, check=True,
            )
            assert ".edf" not in status.stdout
        finally:
            expected.unlink(missing_ok=True)

# ── EDF-147: no raw issue-access patterns in migrated files ──────────────────

_PLUGIN_DIR = BIN_DIR.parent
_MIGRATED_FILES = [
    BIN_DIR / "brief-package.sh",
    _PLUGIN_DIR / "agents" / "feature-evaluator.md",
    _PLUGIN_DIR / "agents" / "test-author.md",
    BIN_DIR / "update-coverage-manifest.py",
    _PLUGIN_DIR / "starters" / "CLAUDE.md.template",
]


class TestMigratedFilesUseTracker:
    @pytest.mark.parametrize("path", _MIGRATED_FILES, ids=lambda p: p.name)
    @pytest.mark.parametrize("pattern", ["gh issue view", "gh project item-list"])
    def test_no_raw_issue_access_pattern(self, path, pattern):
        assert pattern not in path.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "path",
        [
            _PLUGIN_DIR / "agents" / "feature-evaluator.md",
            _PLUGIN_DIR / "agents" / "test-author.md",
            _PLUGIN_DIR / "starters" / "CLAUDE.md.template",
        ],
        ids=lambda p: p.name,
    )
    def test_mentions_tracker_script(self, path):
        assert "tracker.py" in path.read_text(encoding="utf-8")


# ── tracker.py status ──────────────────────────────────────────────────────


class TestTrackerStatus:
    def test_no_args_shows_usage(self):
        result = _tracker("status")
        assert result.returncode != 0

    def test_missing_config_file_in_repo(self, tmp_path):
        # Script resolves repo root via `git rev-parse --show-toplevel`, not its own
        # location. From inside a git repo with no .github/project.env, it must look
        # at the *repo's* .github/, not the plugin's.
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        result = _tracker("status", "42", "todo", "--add-to-board", cwd=tmp_path)
        assert result.returncode != 0
        # The error message should reference the repo's .github path
        assert str(tmp_path).replace("\\", "/").lower() in result.stderr.replace("\\", "/").lower() \
            or ".github/project.env" in result.stderr

    def test_outside_git_repo_fails_clearly(self, tmp_path):
        # When invoked from outside any git repo, the script must fail with a clear
        # message rather than silently looking at the plugin's directory.
        result = _tracker("status", "42", "todo", "--add-to-board", cwd=tmp_path)
        assert result.returncode != 0
        assert "git repository" in result.stderr.lower()

    def test_loads_config_with_crlf_line_endings(self, tmp_path):
        # Windows clones with core.autocrlf=true check project.env out as CRLF.
        # A CRLF blank line reads as a key of "\r", which must be skipped rather
        # than exported (previously: `export "="` aborted under set -euo pipefail).
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        config = tmp_path / ".github" / "project.env"
        config.parent.mkdir()
        config.write_bytes(
            b"REPO=owner/repo\r\n"
            b"PROJECT_NUMBER=4\r\n"
            b"PROJECT_ID=PVT_abc\r\n"
            b"FIELD_ID=PVTSSF_xyz\r\n"
            b"\r\n"
            b"STATUS_TODO=todo-id\r\n"
            b"STATUS_BLOCKED=blocked-id\r\n"
            b"STATUS_IN_PROGRESS=in-progress-id\r\n"
            b"STATUS_DONE=done-id\r\n"
        )
        # Exercise just the config-loading loop so no gh call is made.
        script = (
            "set -euo pipefail; "
            f"CONFIG_FILE={_to_msys2_path(config)}; "
            "while IFS='=' read -r key value; do "
            "key=$(echo \"$key\" | xargs); value=$(echo \"$value\" | xargs); "
            "[[ \"$key\" =~ ^[[:space:]]*# ]] && continue; "
            "[[ -z \"$key\" ]] && continue; "
            "export \"$key=$value\"; "
            "done < \"$CONFIG_FILE\"; "
            "echo \"STATUS_DONE=$STATUS_DONE\""
        )
        result = subprocess.run(
            [_BASH_EXE, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert "STATUS_DONE=done-id" in result.stdout


# ── run-python.sh ────────────────────────────────────────────────────────────


class TestRunPython:
    def test_runs_python_command(self):
        result = _bash(HOOKS_DIR / "run-python.sh", "-c", "print(42)")
        assert result.returncode == 0
        assert "42" in result.stdout

    def test_python_version(self):
        result = _bash(HOOKS_DIR / "run-python.sh", "--version")
        assert result.returncode == 0


# ── open-in-editor.sh ────────────────────────────────────────────────────────


class TestOpenInEditor:
    def test_skips_gracefully_without_editor(self):
        # This should exit 0 even when neither code nor windsurf is installed
        result = _bash(HOOKS_DIR / "open-in-editor.sh")
        assert result.returncode == 0


# ── starters run-audit.sh dispatcher ─────────────────────────────────────────


class TestRunAuditDispatcher:
    def test_dispatches_without_exec_bit_on_sub_scripts(self, tmp_path):
        # Plugin-cache installs can strip the exec bit from sub-scripts. The
        # dispatcher must invoke them via `bash`, not direct exec, so the audit
        # gate works regardless. On platforms where chmod is honoured, this
        # reproduces the cache bug; where it isn't, the bash-prefixed dispatch
        # still passes.
        workdir = tmp_path / "proj"
        workdir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
        for rel in ("typescript", "python"):
            (tmp_path / rel).mkdir()
        shutil.copy2(SCRIPTS_DIR / "run-audit.sh", tmp_path / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "typescript" / "run-audit.sh", tmp_path / "typescript" / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "python" / "run-audit.sh", tmp_path / "python" / "run-audit.sh")
        for sub in (tmp_path / "typescript" / "run-audit.sh", tmp_path / "python" / "run-audit.sh"):
            sub.chmod(0o644)
        result = _bash(tmp_path / "run-audit.sh", "ts", cwd=workdir)
        assert result.returncode == 0
        assert "audit skipped" in result.stdout

    def test_all_case_without_exec_bit(self, tmp_path):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
        for rel in ("typescript", "python"):
            (tmp_path / rel).mkdir()
        shutil.copy2(SCRIPTS_DIR / "run-audit.sh", tmp_path / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "typescript" / "run-audit.sh", tmp_path / "typescript" / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "python" / "run-audit.sh", tmp_path / "python" / "run-audit.sh")
        for sub in (tmp_path / "typescript" / "run-audit.sh", tmp_path / "python" / "run-audit.sh"):
            sub.chmod(0o644)
        result = _bash(tmp_path / "run-audit.sh", "all", cwd=workdir)
        assert result.returncode == 0
        assert result.stdout.count("audit skipped") == 2


class TestRunAuditTypescriptFailureDetection:
    """The network-failure skip must not swallow real findings (FCS #1296/#1298:
    an advisory mentioning "remote code execution" matched the old
    case-insensitive `code E` pattern and the gate printed PASS on 19 findings)."""

    def _run_with_npm(self, tmp_path, npm_output):
        workdir = tmp_path / "proj"
        workdir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
        (workdir / "package-lock.json").write_text("{}")
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        out_file = tmp_path / "npm-out.txt"
        out_file.write_text(npm_output)
        npm_shim = fake_bin / "npm"
        npm_shim.write_text(f"#!/usr/bin/env bash\ncat '{_to_msys2_path(out_file)}'\nexit 1\n")
        npm_shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        env.pop("EDF_AUDIT_WARN_ONLY", None)
        return subprocess.run(
            [_BASH_EXE, _to_msys2_path(SCRIPTS_DIR / "typescript" / "run-audit.sh")],
            capture_output=True, text=True, timeout=30, cwd=workdir, env=env,
        )

    def test_advisory_mentioning_code_execution_fails_the_gate(self, tmp_path):
        result = self._run_with_npm(
            tmp_path,
            "# npm audit report\n\n"
            "next  <15.2.3\n"
            "Severity: critical\n"
            "Next.js vulnerable to remote Code Execution via crafted request\n"
            "fix available via `npm audit fix --force`\n\n"
            "19 vulnerabilities (2 low, 6 moderate, 8 high, 3 critical)\n",
        )
        assert result.returncode == 1
        assert "audit skipped" not in result.stdout
        assert "19 vulnerabilities" in result.stdout

    def test_network_failure_still_skips(self, tmp_path):
        result = self._run_with_npm(
            tmp_path,
            "npm error code ENOTFOUND\n"
            "npm error audit endpoint returned an error\n",
        )
        assert result.returncode == 0
        assert "audit skipped" in result.stdout


# ── e2e-needed.sh ────────────────────────────────────────────────────────────


class TestE2eNeeded:
    """Step 5 E2E gate decided by changed paths, not by model judgement (FCS #1315:
    E2E launched on an engine-only change, then the session idled ~4.5h)."""

    def _repo(self, tmp_path, conventions_rows):
        repo = tmp_path / "repo"
        (repo / "kb").mkdir(parents=True)
        (repo / "tests" / "e2e").mkdir(parents=True)
        (repo / "tests" / "e2e" / "a.spec.ts").write_text("x")
        (repo / "kb" / "conventions.md").write_text(
            "| Concept | Pattern |\n|---|---|\n" + conventions_rows
        )
        run = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
        run("init", "-q", "-b", "main")
        run("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        run("checkout", "-qb", "feat")
        return repo

    def _change(self, repo, rel):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("changed")

    def _run(self, repo):
        return _bash(BIN_DIR / "e2e-needed.sh", "main", cwd=repo)

    ROWS = "| e2e-dir | `tests/e2e/` |\n| e2e-trigger-paths | `src/app/**`, `src/components/**` |\n"

    def test_skips_when_no_changed_path_matches_a_trigger(self, tmp_path):
        repo = self._repo(tmp_path, self.ROWS)
        self._change(repo, "src/lib/engine/llm/schemas.ts")
        result = self._run(repo)
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("skip")

    def test_runs_when_an_untracked_file_matches_a_trigger(self, tmp_path):
        repo = self._repo(tmp_path, self.ROWS)
        self._change(repo, "src/components/deep/button.tsx")
        result = self._run(repo)
        assert result.stdout.startswith("run")

    def test_runs_when_trigger_paths_not_configured(self, tmp_path):
        # Conservative default: projects that have not opted in keep today's behaviour.
        repo = self._repo(tmp_path, "| e2e-dir | `tests/e2e/` |\n")
        self._change(repo, "src/lib/x.ts")
        assert self._run(repo).stdout.startswith("run")

    def test_skips_when_no_e2e_dir(self, tmp_path):
        repo = self._repo(tmp_path, "| e2e-dir | <!-- e.g. `tests/e2e/` --> |\n")
        self._change(repo, "src/app/page.tsx")
        assert self._run(repo).stdout.startswith("skip")


# ── run-audit.sh --baseline ──────────────────────────────────────────────────


class TestRunAuditBaseline:
    """21 FCS session logs re-derive "8 pre-existing advisories, lockfile unchanged"
    by hand. --baseline makes that a one-line script verdict."""

    NPM_FINDINGS = "next  <15.2.3\nSeverity: critical\n8 vulnerabilities (4 moderate, 3 high, 1 critical)\n"

    def _setup(self, tmp_path):
        scripts = tmp_path / "scripts"
        (scripts / "typescript").mkdir(parents=True)
        (scripts / "python").mkdir()
        shutil.copy2(SCRIPTS_DIR / "run-audit.sh", scripts / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "typescript" / "run-audit.sh", scripts / "typescript" / "run-audit.sh")
        shutil.copy2(SCRIPTS_DIR / "python" / "run-audit.sh", scripts / "python" / "run-audit.sh")
        repo = tmp_path / "repo"
        repo.mkdir()
        run = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                        cwd=repo, check=True, capture_output=True)
        run("init", "-q", "-b", "main")
        (repo / "package-lock.json").write_text("{}")
        (repo / "src.ts").write_text("x")
        run("add", "-A")
        run("commit", "-qm", "base")
        run("checkout", "-qb", "feat")
        fake_bin = tmp_path / "fakebin"
        fake_bin.mkdir()
        out = tmp_path / "npm-out.txt"
        out.write_text(self.NPM_FINDINGS)
        shim = fake_bin / "npm"
        shim.write_text(f"#!/usr/bin/env bash\ncat '{_to_msys2_path(out)}'\nexit 1\n")
        shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{_to_msys2_path(fake_bin)}:{env.get('PATH', '')}"
        env.pop("EDF_AUDIT_WARN_ONLY", None)
        return scripts, repo, env

    def _audit(self, scripts, repo, env, *args):
        return subprocess.run([_BASH_EXE, _to_msys2_path(scripts / "run-audit.sh"), "ts", *args],
                              capture_output=True, text=True, timeout=30, cwd=repo, env=env)

    def test_findings_with_unchanged_dependencies_are_pre_existing(self, tmp_path):
        scripts, repo, env = self._setup(tmp_path)
        (repo / "src.ts").write_text("changed")
        result = self._audit(scripts, repo, env, "--baseline", "main")
        assert result.returncode == 0, result.stdout
        assert result.stdout.startswith("audit: PRE-EXISTING")
        assert "8 vulnerabilities" in result.stdout

    def test_findings_with_changed_lockfile_fail(self, tmp_path):
        scripts, repo, env = self._setup(tmp_path)
        (repo / "package-lock.json").write_text('{"changed": true}')
        result = self._audit(scripts, repo, env, "--baseline", "main")
        assert result.returncode == 1
        assert "dependency files changed on this branch: package-lock.json" in result.stdout

    def test_without_baseline_findings_still_fail(self, tmp_path):
        scripts, repo, env = self._setup(tmp_path)
        assert self._audit(scripts, repo, env).returncode == 1


# ── park-docs.sh ─────────────────────────────────────────────────────────────


class TestParkDocs:
    """Docs never go onto the PR branch at wrap-up: a docs-only push cancels the
    in-flight CI run (FCS-1373: three extra CI cycles)."""

    def _repos(self, tmp_path):
        remote = tmp_path / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        repo = tmp_path / "repo"
        subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
        run = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                        cwd=repo, check=True, capture_output=True, text=True)
        run("checkout", "-qb", "main")
        (repo / "docs").mkdir()
        (repo / "docs" / "lld.md").write_text("v1\n")
        (repo / "src.ts").write_text("x\n")
        run("add", "-A")
        run("commit", "-qm", "base")
        run("push", "-q", "-u", "origin", "main")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        return repo, run

    def test_park_then_land_on_main_commits_docs_only_there(self, tmp_path):
        repo, run = self._repos(tmp_path)
        run("checkout", "-qb", "feat")
        (repo / "docs" / "lld.md").write_text("v2 synced\n")
        (repo / "docs" / "session-log-X-7.md").write_text("log\n")
        (repo / "src.ts").write_text("code change\n")

        parked = _bash(BIN_DIR / "park-docs.sh", "park", "7", cwd=repo)
        assert parked.returncode == 0, parked.stderr
        assert parked.stdout.startswith("park: parked 2")
        status = run("status", "--porcelain").stdout
        assert "docs/" not in status and "src.ts" in status  # code untouched

        run("checkout", "-q", "main")
        run("checkout", "-q", "--", "src.ts")
        landed = _bash(BIN_DIR / "park-docs.sh", "land", "7", cwd=repo)
        assert landed.returncode == 0, landed.stderr
        assert landed.stdout.startswith("land: committed and pushed")
        remote_files = run("ls-tree", "-r", "--name-only", "origin/main").stdout
        assert "docs/session-log-X-7.md" in remote_files
        assert run("show", "origin/main:docs/lld.md").stdout == "v2 synced\n"
        assert "#7" in run("log", "-1", "--format=%s", "origin/main").stdout

    def test_docs_dir_from_dotenv_is_parked_instead_of_root_docs(self, tmp_path):
        repo, run = self._repos(tmp_path)
        (repo / ".env").write_text("EDF_DOCS_DIR=plugins/x/docs\n")
        run("checkout", "-qb", "feat")
        (repo / "plugins" / "x" / "docs" / "sessions").mkdir(parents=True)
        (repo / "plugins" / "x" / "docs" / "sessions" / "log-EDF-7.md").write_text("log\n")
        (repo / "docs" / "lld.md").write_text("root docs edit\n")

        parked = _bash(BIN_DIR / "park-docs.sh", "park", "7", cwd=repo)
        assert parked.returncode == 0, parked.stderr
        assert parked.stdout.startswith("park: parked 1")  # only the configured dir
        assert not (repo / "plugins" / "x" / "docs" / "sessions" / "log-EDF-7.md").exists()
        assert "docs/lld.md" in run("status", "--porcelain").stdout  # root docs/ untouched

    def test_jira_key_ref_parks_and_lands_with_key_in_commit_message(self, tmp_path):
        repo, run = self._repos(tmp_path)
        run("checkout", "-qb", "feat")
        (repo / "docs" / "session-log-SCRUM-7.md").write_text("log\n")
        parked = _bash(BIN_DIR / "park-docs.sh", "park", "SCRUM-7", cwd=repo)
        assert parked.returncode == 0, parked.stderr
        assert parked.stdout.startswith("park: parked 1")
        run("checkout", "-q", "main")
        landed = _bash(BIN_DIR / "park-docs.sh", "land", "SCRUM-7", cwd=repo)
        assert landed.returncode == 0, landed.stderr
        subject = run("log", "-1", "--format=%s", "origin/main").stdout
        assert "SCRUM-7" in subject and "#SCRUM" not in subject

    def test_rejects_malformed_ref(self, tmp_path):
        repo, _ = self._repos(tmp_path)
        bad = _bash(BIN_DIR / "park-docs.sh", "park", "x; rm -rf /", cwd=repo)
        assert bad.returncode == 2

    def test_land_does_not_pick_another_issues_stash(self, tmp_path):
        repo, run = self._repos(tmp_path)
        (repo / "docs" / "lld.md").write_text("for 71\n")
        assert _bash(BIN_DIR / "park-docs.sh", "park", "71", cwd=repo).returncode == 0
        landed = _bash(BIN_DIR / "park-docs.sh", "land", "7", cwd=repo)
        assert landed.returncode == 0
        assert "nothing parked for #7" in landed.stdout

    def test_park_with_nothing_to_park(self, tmp_path):
        repo, _ = self._repos(tmp_path)
        result = _bash(BIN_DIR / "park-docs.sh", "park", "7", cwd=repo)
        assert result.returncode == 0
        assert "nothing to park" in result.stdout

    def test_rejects_bad_usage(self, tmp_path):
        assert _bash(BIN_DIR / "park-docs.sh", "park", "abc", cwd=tmp_path).returncode == 2

    # ── #168 §4: `land` serialises on a lock in the shared git dir ──

    def _lock_path(self, repo):
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo,
                                check=True, capture_output=True, text=True).stdout.strip()
        return (repo / common).resolve() / "edf-park-docs.lock"

    def _hold_lock(self, lock, seconds):
        """Hold the lock from another process; return once it is actually held."""
        holder = subprocess.Popen(["flock", str(lock), "sleep", str(seconds)])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            probe = subprocess.run(["flock", "-n", str(lock), "true"], capture_output=True)
            if probe.returncode != 0:
                return holder
            time.sleep(0.05)
        holder.kill()
        pytest.fail("test could not take the park-docs lock")

    def _land(self, repo, ref, wait=None):
        env = dict(os.environ)
        if wait is not None:
            env["EDF_PARK_DOCS_LOCK_WAIT"] = str(wait)
        return subprocess.Popen([_BASH_EXE, _to_msys2_path(BIN_DIR / "park-docs.sh"), "land", ref],
                                cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

    def _park_on_feat(self, repo, run, ref, name):
        run("checkout", "-qB", f"feat-{ref}", "main")
        (repo / "docs" / name).write_text(f"log {ref}\n")
        parked = _bash(BIN_DIR / "park-docs.sh", "park", ref, cwd=repo)
        assert parked.returncode == 0, parked.stderr
        run("checkout", "-q", "main")

    @pytest.mark.skipif(shutil.which("flock") is None, reason="flock not installed")
    def test_land_waits_for_the_lock_then_completes(self, tmp_path):
        repo, run = self._repos(tmp_path)
        self._park_on_feat(repo, run, "7", "session-log-X-7.md")
        holder = self._hold_lock(self._lock_path(repo), 3)
        try:
            start = time.monotonic()
            land = self._land(repo, "7", wait=30)
            time.sleep(1)
            assert land.poll() is None, "land ran while another land held the lock"
            assert "docs/session-log-X-7.md" not in run("ls-tree", "-r", "--name-only", "origin/main").stdout
            out, err = land.communicate(timeout=30)
            elapsed = time.monotonic() - start
        finally:
            holder.kill()
            holder.wait()
        assert land.returncode == 0, err
        assert out.startswith("land: committed and pushed")
        assert elapsed >= 2
        assert "docs/session-log-X-7.md" in run("ls-tree", "-r", "--name-only", "origin/main").stdout

    @pytest.mark.skipif(shutil.which("flock") is None, reason="flock not installed")
    def test_land_times_out_with_one_line(self, tmp_path):
        repo, run = self._repos(tmp_path)
        self._park_on_feat(repo, run, "7", "session-log-X-7.md")
        holder = self._hold_lock(self._lock_path(repo), 60)
        try:
            start = time.monotonic()
            land = self._land(repo, "7", wait=1)
            out, err = land.communicate(timeout=30)
            elapsed = time.monotonic() - start
        finally:
            holder.kill()
            holder.wait()
        assert land.returncode != 0
        assert elapsed < 20
        lines = [ln for ln in (out + err).splitlines() if ln.strip()]
        assert len(lines) == 1, lines
        assert lines[0].startswith("land:")
        # Nothing was landed: the stash is still parked.
        assert "edf-docs-7" in run("stash", "list").stdout

    @pytest.mark.skipif(shutil.which("flock") is None, reason="flock not installed")
    def test_two_concurrent_lands_both_commit(self, tmp_path):
        repo, run = self._repos(tmp_path)
        self._park_on_feat(repo, run, "7", "session-log-X-7.md")
        self._park_on_feat(repo, run, "8", "session-log-X-8.md")
        holder = self._hold_lock(self._lock_path(repo), 1)
        try:
            first, second = self._land(repo, "7", wait=30), self._land(repo, "8", wait=30)
            out1, err1 = first.communicate(timeout=60)
            out2, err2 = second.communicate(timeout=60)
        finally:
            holder.kill()
            holder.wait()
        assert first.returncode == 0, err1
        assert second.returncode == 0, err2
        remote_files = run("ls-tree", "-r", "--name-only", "origin/main").stdout
        assert "docs/session-log-X-7.md" in remote_files
        assert "docs/session-log-X-8.md" in remote_files


class TestCreateFeaturePrMultiIssue:
    def test_repeated_issue_writes_one_closes_line_each(self):
        # FCS-1373/1374 and 1353/1367 shipped as one PR; only the first issue got
        # a Closes line and the body was patched by hand.
        env = dict(os.environ, EDF_FEATURE_PREFIX="T")
        result = subprocess.run(
            [_BASH_EXE, _to_msys2_path(BIN_DIR / "create-feature-pr.sh"),
             "--issue", "1373", "--issue", "1374", "--title", "x", "--summary", "- y",
             "--tests-added", "1", "--tests-total", "2", "--dry-run"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, result.stderr
        assert "Closes #1373\nCloses #1374\n" in result.stdout


# ── update-coverage-manifest.py --extract-epic-slug (#147) ───────────────────


class TestExtractEpicSlug:
    def test_tracker_view_json_gives_same_slug_as_bare_body(self):
        def run(stdin):
            return subprocess.run(
                [sys.executable, str(BIN_DIR / "update-coverage-manifest.py"), "--extract-epic-slug"],
                input=stdin, capture_output=True, text=True, timeout=30,
            ).stdout.strip()

        body = "see lld-v1-e1-2-review-feedback.md"
        bare = run(body)
        assert bare
        assert run(json.dumps({"ref": "#1", "body": body})) == bare
