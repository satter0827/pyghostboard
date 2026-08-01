"""Release artifact verification tests."""

import tarfile
import zipfile
from pathlib import Path

import pytest
from scripts import release_gate
from tools.generate_schemas import check_schemas, write_schemas
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
        for path in (
            "pyghostboard/locale/pyghostboard.pot",
            "pyghostboard/locale/ja/LC_MESSAGES/pyghostboard.po",
            "pyghostboard/locale/ja/LC_MESSAGES/pyghostboard.mo",
        ):
            archive.writestr(path, b"catalog")
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


def test_release_verifier_rejects_missing_translation_catalog(tmp_path: Path) -> None:
    _write_archives(tmp_path, "0.1.0")
    wheel = tmp_path / "pyghostboard-0.1.0-py3-none-any.whl"
    # Rebuild without one required member because ZipFile cannot delete in place.
    replacement = tmp_path / "replacement.whl"
    with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(replacement, "w") as target:
        for name in source.namelist():
            if name != "pyghostboard/locale/pyghostboard.pot":
                target.writestr(name, source.read(name))
    replacement.replace(wheel)

    with pytest.raises(ValueError, match="translation catalogs"):
        verify_distribution(tmp_path, "0.1.0")


def test_schema_check_detects_stale_generated_document(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    check_schemas(tmp_path)
    schema = next(tmp_path.glob("*.schema.json"))
    schema.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="generated schemas are stale"):
        check_schemas(tmp_path)


def test_quality_configuration_produces_supported_matrix() -> None:
    matrix = release_gate.compatibility_matrix()

    assert {entry["python-version"] for entry in matrix} == {"3.11", "3.12", "3.13", "3.14"}
    assert {entry["scope"] for entry in matrix} == {"full", "domain"}
    assert any(entry["os"] == "windows-2025" for entry in matrix)
    assert release_gate.primary_python() == "3.13"


def test_gate_stops_on_failed_command(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        returncode = 7

    monkeypatch.setattr("scripts.release_gate.subprocess.run", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError, match=r"failed \(7\)"):
        release_gate.run(["failing-command"])


@pytest.mark.parametrize("version", ["1", "1.2", "v1.2.3", "1.2.3.dev1"])
def test_release_version_must_be_stable_semver(version: str) -> None:
    with pytest.raises(ValueError, match=r"X\.Y\.Z"):
        release_gate.validate_version(version)
