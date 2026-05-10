import pathlib
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
