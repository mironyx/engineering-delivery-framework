"""Tests for shell script argument parsing and dry-run paths.

These tests invoke shell scripts directly via bash. They test argument validation
and dry-run modes — not live GitHub operations.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

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


gh_required = pytest.mark.skipif(not _gh_available(), reason="gh CLI not authenticated")


# ── gh-create-issue.sh ───────────────────────────────────────────────────────


class TestGhCreateIssue:
    def test_missing_title(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--body", "test body")
        assert result.returncode != 0
        assert "title" in result.stderr.lower()

    def test_missing_body(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--title", "test title")
        assert result.returncode != 0
        assert "body" in result.stderr.lower()

    def test_unknown_option(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh", "--unknown-flag")
        assert result.returncode != 0

    @gh_required
    def test_dry_run_output(self):
        result = _bash(
            BIN_DIR / "gh-create-issue.sh",
            "--title", "Test Issue",
            "--body", "Issue body content",
            "--dry-run",
        )
        assert result.returncode == 0
        assert "dry-run: would create issue" in result.stdout
        assert "Test Issue" in result.stdout
        assert "Issue body content" in result.stdout

    @gh_required
    def test_dry_run_with_labels(self):
        result = _bash(
            BIN_DIR / "gh-create-issue.sh",
            "--title", "Labeled Issue",
            "--body", "Body",
            "--labels", "bug,high-priority",
            "--dry-run",
        )
        assert result.returncode == 0
        assert "bug,high-priority" in result.stdout

    def test_no_args(self):
        result = _bash(BIN_DIR / "gh-create-issue.sh")
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


class TestBriefPackage:
    def test_no_args_shows_usage(self):
        result = _bash(BIN_DIR / "brief-package.sh")
        assert result.returncode == 1
        assert "usage:" in result.stderr

    def test_missing_lld_shows_usage(self):
        result = _bash(BIN_DIR / "brief-package.sh", "--issue", "1")
        assert result.returncode == 1
        assert "usage:" in result.stderr

    def test_issue_requires_a_number(self):
        result = _bash(BIN_DIR / "brief-package.sh", "--issue", "abc", "--lld", "none")
        assert result.returncode == 1
        assert "expects a number" in result.stderr

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

    @gh_required
    def test_full_issue_body_included_even_with_no_ac_heading(self, tmp_path):
        # Issue #1 (merged) has no "## Acceptance criteria" heading at all —
        # a case the old AC-only extraction had to special-case. Now the
        # whole body is always included verbatim, so there is nothing to
        # fall back from: the content is just there.
        out = tmp_path / "brief.md"
        result = _bash(
            BIN_DIR / "brief-package.sh",
            "--issue", "1", "--lld", "none",
            "--out", str(out),
        )
        assert result.returncode == 0
        body = out.read_text()
        assert "schema foundations" in body.lower()
        assert "## Test plan" in body

    @gh_required
    def test_lld_falls_back_to_full_file_when_no_anchor_referenced(self, tmp_path):
        # Issue #1 has no "## Design reference" section and no "#LLD-..."
        # anchor anywhere in its body — resolution must fail closed to the
        # full LLD file, not an empty section.
        out = tmp_path / "brief.md"
        result = _bash(
            BIN_DIR / "brief-package.sh",
            "--issue", "1",
            "--lld", str(_LLD_FIXTURE),
            "--out", str(out),
        )
        assert result.returncode == 0
        assert "lld: fallback-full-file" in result.stdout

        body = out.read_text()
        # A marker from near the end of the real file — proof the whole
        # thing was included, not just an early section.
        assert "## Execution Order" in body

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

    @gh_required
    def test_resolves_every_design_reference_anchor_and_unions_their_reqs(self, tmp_path):
        # No real closed issue in this repo names more than one LLD-<anchor> in its
        # "## Design reference" section, so the redesign's "every anchor, not just
        # the first" resolution and the requirements union across every resolved
        # anchor have no real issue-body fixture. Shims only the `gh issue view`
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
        gh_shim = fake_bin / "gh"
        gh_shim.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *'--json title'*) echo 'Synthetic multi-anchor issue' ;;\n"
            f"  *'--json body'*) cat '{_to_msys2_path(body_file)}' ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n"
        )
        gh_shim.chmod(0o755)

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

    @gh_required
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
        gh_shim = fake_bin / "gh"
        gh_shim.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *'--json title'*) echo 'Synthetic anchorless-design-reference issue' ;;\n"
            f"  *'--json body'*) cat '{_to_msys2_path(body_file)}' ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n"
        )
        gh_shim.chmod(0o755)

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

# ── gh-project-status.sh ─────────────────────────────────────────────────────


class TestGhProjectStatus:
    def test_no_args_shows_usage(self):
        result = _bash(BIN_DIR / "gh-project-status.sh")
        assert result.returncode != 0

    def test_missing_config_file_in_repo(self, tmp_path):
        # Script resolves repo root via `git rev-parse --show-toplevel`, not its own
        # location. From inside a git repo with no .github/project.env, it must look
        # at the *repo's* .github/, not the plugin's.
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        result = _bash(BIN_DIR / "gh-project-status.sh", "add", "42", cwd=tmp_path)
        assert result.returncode != 0
        # The error message should reference the repo's .github path
        assert str(tmp_path).replace("\\", "/").lower() in result.stderr.replace("\\", "/").lower() \
            or ".github/project.env" in result.stderr

    def test_outside_git_repo_fails_clearly(self, tmp_path):
        # When invoked from outside any git repo, the script must fail with a clear
        # message rather than silently looking at the plugin's directory.
        result = _bash(BIN_DIR / "gh-project-status.sh", "add", "42", cwd=tmp_path)
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
