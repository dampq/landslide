"""Obtain uv's official Linux wheel without requiring pip or ensurepip.

TLS remains enabled. Verify the wheel against the SHA-256 published by PyPI,
then extract only the native uv executable (never arbitrary archive paths).
"""

import hashlib
import io
import json
import os
import platform
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "0.9.5"


def bootstrap(cache):
    executable = cache.resolve() / f"uv-{VERSION}" / "uv"
    if executable.is_file() and os.access(executable, os.X_OK):
        return executable
    if platform.system() != "Linux":
        raise RuntimeError(
            "Install uv or a complete Python 3.12 runtime on this operating system."
        )
    architecture = platform.machine().lower()
    architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(
        architecture, architecture
    )
    with urllib.request.urlopen(
        f"https://pypi.org/pypi/uv/{VERSION}/json", timeout=30
    ) as response:
        metadata = json.load(response)
    prefix = f"uv-{VERSION}-py3-none-manylinux_2_17_{architecture}."
    wheels = [
        f
        for f in metadata["urls"]
        if f["filename"].startswith(prefix) and f["filename"].endswith(".whl")
    ]
    if len(wheels) != 1:
        raise RuntimeError(
            f"No unambiguous uv wheel for Linux {architecture}; install uv manually."
        )
    wheel = wheels[0]
    if not wheel["url"].startswith("https://files.pythonhosted.org/"):
        raise RuntimeError("Unexpected package download destination")
    with urllib.request.urlopen(wheel["url"], timeout=120) as response:
        content = response.read(100_000_001)
    if (
        len(content) > 100_000_000
        or hashlib.sha256(content).hexdigest() != wheel["digests"]["sha256"]
    ):
        raise RuntimeError("uv wheel failed checksum verification")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = [
            name for name in archive.namelist() if name.endswith(".data/scripts/uv")
        ]
        if len(members) != 1:
            raise RuntimeError(
                "Expected one native uv executable in the verified wheel"
            )
        binary = archive.read(members[0])
    executable.parent.mkdir(parents=True, exist_ok=True)
    temporary = executable.with_suffix(".tmp")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.replace(executable)
    return executable


if __name__ == "__main__":
    print(bootstrap(Path(__file__).resolve().parents[1] / ".cache" / "python-tools"))
