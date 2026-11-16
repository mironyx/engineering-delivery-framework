import json
import os
import pathlib
import subprocess
import sys

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "edf"
BIN_DIR = PLUGIN_ROOT / "bin"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(BIN_DIR))


def pytest_addoption(parser):
    parser.addoption("--plugins-root", default=str(PLUGIN_ROOT), help="Path to plugins/edf")


@pytest.fixture
def plugins_root():
    return PLUGIN_ROOT


@pytest.fixture
def bin_dir():
    return BIN_DIR


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def _scrub_jira_env(monkeypatch):
    """A developer's own JIRA_* settings must never select Jira inside the suite."""
    for key in [k for k in os.environ if k.startswith("JIRA_")]:
        monkeypatch.delenv(key)


class FakeGh:
    """Handle returned by the `fake_gh` fixture.

    `repo` is a fresh `git init` directory with no .env — run subprocesses with
    `cwd=fake_gh.repo` so neither the developer's checkout nor its .env leaks in.
    """

    def __init__(self, tmp_path: pathlib.Path):
        self.bin_dir = tmp_path / "bin"
        self.repo = tmp_path / "repo"
        self.scenario = tmp_path / "fake_gh_scenario.json"
        self.log = tmp_path / "fake_gh_log.jsonl"

    def rules(self, rules: list[dict]) -> None:
        self.scenario.write_text(json.dumps(rules), encoding="utf-8")

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    """Put a scenario-driven fake `gh` first on PATH; record every call."""
    if sys.platform == "win32":
        pytest.skip("fake_gh needs a POSIX shell wrapper")
    handle = FakeGh(tmp_path)
    handle.bin_dir.mkdir()
    wrapper = handle.bin_dir / "gh"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "{FIXTURES_DIR / "fake_gh.py"}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    handle.repo.mkdir()
    subprocess.run(["git", "init", "-q", str(handle.repo)], check=True)
    monkeypatch.setenv("PATH", f"{handle.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_GH_SCENARIO", str(handle.scenario))
    monkeypatch.setenv("FAKE_GH_LOG", str(handle.log))
    return handle


@pytest.fixture(scope="session")
def _fake_jira_cert(tmp_path_factory):
    """One throwaway TLS certificate per session. A missing openssl fails the test run — never skips."""
    from tests.fixtures.fake_jira import FakeJiraSetupError, generate_certificate

    try:
        return generate_certificate(tmp_path_factory.mktemp("fake_jira_tls"))
    except FakeJiraSetupError as exc:
        pytest.fail(str(exc), pytrace=False)


@pytest.fixture
def fake_jira(_fake_jira_cert, monkeypatch):
    """Stateful fake Jira over HTTPS on localhost; points JIRA_* and SSL_CERT_FILE at it.

    See tests/fixtures/fake_jira.py. Needs `openssl` (fails, does not skip, without it).
    """
    if sys.platform == "win32":
        pytest.skip("fake_jira is POSIX only, like fake_gh")
    from tests.fixtures.fake_jira import FakeJira

    cert, key = _fake_jira_cert
    server = FakeJira(cert, key)
    server.start()
    for name, value in server.env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    yield server
    server.stop()


@pytest.fixture
def run_script(bin_dir):
    def _run(script_name, stdin_text=None, args=None):
        import subprocess

        script = bin_dir / script_name
        cmd = [sys.executable, str(script)]
        if args:
            cmd.extend(args)
        result = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result

    return _run
