"""V1A-0 gate: no Docker usage in the build/runtime path.

Comments may mention the no-Docker policy; executable content must not
invoke or define containers.
"""

import pathlib

import pytest

pytestmark = pytest.mark.unit

SCAN_ROOTS = ["scripts", "apps/api", "apps/worker", "apps/scheduler", "requirements"]
SCAN_FILES = ["package.json", "pytest.ini", "apps/web/package.json", "apps/web/next.config.mjs"]


def _executable_lines(text: str) -> str:
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # strip trailing comments in shell/yaml/ts config lines
        if "#" in stripped and not stripped.startswith(("{", "[")):
            stripped = stripped.split("#", 1)[0]
        kept.append(stripped)
    return "\n".join(kept).lower()


def _violations(paths):
    needles = ("docker", "dockerfile", "compose", "container")
    found = []
    for path in paths:
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        content = _executable_lines(text)
        for needle in needles:
            if needle in content:
                found.append(f"{path}: {needle}")
    return found


def _all_paths():
    paths = []
    for root in SCAN_ROOTS:
        for path in pathlib.Path(root).rglob("*"):
            if not path.is_file() or "node_modules" in path.parts or ".next" in path.parts:
                continue
            paths.append(path)
    for f in SCAN_FILES:
        p = pathlib.Path(f)
        if p.exists():
            paths.append(p)
    return paths


def test_no_docker_usage_in_build_or_runtime_paths():
    violations = _violations(_all_paths())
    assert violations == [], f"container references found: {violations}"


def test_service_scripts_only_manage_native_pids():
    """Start/stop scripts must act on recorded native PIDs and native CLIs."""
    start = pathlib.Path("scripts/start-services.sh").read_text()
    for native in ("pg_ctl", "valkey-server", "uvicorn", "celery", "next"):
        assert native in start, f"native service missing from start script: {native}"
    stop = pathlib.Path("scripts/stop-services.sh").read_text()
    assert "docker" not in _executable_lines(stop)
