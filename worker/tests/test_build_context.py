"""Local virtual environments must never enter Linux service image contexts."""

from pathlib import Path


def test_python_image_context_excludes_host_virtual_environment():
    ignore = Path(__file__).resolve().parents[1] / ".dockerignore"
    assert (
        ignore.is_file()
    ), "Docker build traverses the host .venv without a context exclusion"
    assert ".venv" in ignore.read_text(encoding="utf-8").splitlines()
