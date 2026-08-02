"""Verify that release archives exactly match the requested public version."""

from __future__ import annotations

import argparse
import ast
import re
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def verify_distribution(directory: Path, version: str, expected_commit: str | None = None) -> None:
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("release version must use X.Y.Z format")
    wheel = directory / f"pyghostboard-{version}-py3-none-any.whl"
    source = directory / f"pyghostboard-{version}.tar.gz"
    actual = {
        path.name
        for path in directory.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }
    expected = {wheel.name, source.name}
    if actual != expected:
        raise ValueError(
            f"distribution files differ: expected {sorted(expected)}, got {sorted(actual)}"
        )

    with zipfile.ZipFile(wheel) as archive:
        required_package_data = {
            "pyghostboard/locale/pyghostboard.pot",
            "pyghostboard/locale/ja/LC_MESSAGES/pyghostboard.po",
            "pyghostboard/locale/ja/LC_MESSAGES/pyghostboard.mo",
            "pyghostboard/schemas/arena-analysis-0.1.0.schema.json",
            "pyghostboard/schemas/arena-config-0.1.0.schema.json",
            "pyghostboard/schemas/arena-manifest-0.1.0.schema.json",
            "pyghostboard/schemas/arena-result-0.1.0.schema.json",
        }
        if not required_package_data <= set(archive.namelist()):
            raise ValueError("wheel does not contain all required package data")
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        wheel_metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
    if wheel_metadata["Version"] != version:
        raise ValueError("wheel metadata version does not match the release version")
    if expected_commit is not None:
        if re.fullmatch(r"[0-9a-f]{40}", expected_commit) is None:
            raise ValueError("release commit must be a complete lowercase Git SHA")
        with zipfile.ZipFile(wheel) as archive:
            build_info = archive.read("pyghostboard/_build_info.py").decode("utf-8")
        tree = ast.parse(build_info, filename="pyghostboard/_build_info.py")
        assignments = (
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "BUILD_COMMIT"
        )
        assignment = next(assignments, None)
        if (
            assignment is None
            or not isinstance(assignment.value, ast.Constant)
            or assignment.value.value != expected_commit
        ):
            raise ValueError("wheel build provenance does not match the release commit")

    with tarfile.open(source, mode="r:gz") as archive:
        member = archive.getmember(f"pyghostboard-{version}/PKG-INFO")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError("source distribution does not contain PKG-INFO")
        source_metadata = BytesParser().parsebytes(extracted.read())
    if source_metadata["Version"] != version:
        raise ValueError("source metadata version does not match the release version")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("directory", type=Path, nargs="?", default=Path("dist"))
    parser.add_argument("--commit")
    arguments = parser.parse_args()
    verify_distribution(arguments.directory, arguments.version, arguments.commit)


if __name__ == "__main__":
    main()
