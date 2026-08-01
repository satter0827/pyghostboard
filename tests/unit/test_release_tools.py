"""Release artifact verification tests."""

import tarfile
import zipfile
from pathlib import Path

import pytest
from tools.verify_distribution import verify_distribution


def _write_archives(directory: Path, version: str, commit: str = "a" * 40) -> None:
    wheel = directory / f"pyghostboard-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"pyghostboard-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: pyghostboard\nVersion: {version}\n",
        )
        archive.writestr(
            "pyghostboard/_build_info.py",
            f'from typing import Final\n\nBUILD_COMMIT: Final[str | None] = "{commit}"\n',
        )
    package_info = directory / "PKG-INFO"
    package_info.write_text(
        f"Metadata-Version: 2.4\nName: pyghostboard\nVersion: {version}\n",
        encoding="utf-8",
    )
    source = directory / f"pyghostboard-{version}.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        archive.add(package_info, arcname=f"pyghostboard-{version}/PKG-INFO")
    package_info.unlink()


def test_release_verifier_accepts_exact_archives(tmp_path: Path) -> None:
    _write_archives(tmp_path, "0.1.0")
    verify_distribution(tmp_path, "0.1.0", "a" * 40)


def test_release_verifier_rejects_extra_or_non_release_files(tmp_path: Path) -> None:
    _write_archives(tmp_path, "0.1.0")
    (tmp_path / "unexpected.txt").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="distribution files differ"):
        verify_distribution(tmp_path, "0.1.0")

    with pytest.raises(ValueError, match=r"X\.Y\.Z"):
        verify_distribution(tmp_path, "0.1.0.dev1")


def test_release_verifier_rejects_wrong_build_provenance(tmp_path: Path) -> None:
    _write_archives(tmp_path, "0.1.0")
    with pytest.raises(ValueError, match="provenance"):
        verify_distribution(tmp_path, "0.1.0", "b" * 40)
