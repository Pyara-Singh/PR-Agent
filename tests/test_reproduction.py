from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from PR_Agent.agents.reproduction import ReproductionAgent


def test_archive_extraction_rejects_path_traversal(tmp_path: Path) -> None:
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../outside.txt", "blocked")
    payload.seek(0)

    with ZipFile(payload) as archive, pytest.raises(ValueError, match="unsafe"):
        ReproductionAgent._safe_extract(archive, tmp_path / "workspace")


def test_archive_extraction_keeps_normal_files_in_workspace(tmp_path: Path) -> None:
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("repo/src/main.cpp", "int main() {}")
    payload.seek(0)
    destination = tmp_path / "workspace"

    with ZipFile(payload) as archive:
        ReproductionAgent._safe_extract(archive, destination)

    assert (destination / "repo/src/main.cpp").read_text(encoding="utf-8") == "int main() {}"
