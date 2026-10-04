"""Strict installed API gate using an official Core wheel, without source injection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import sysconfig
import unittest
import zipfile
from pathlib import Path


def run(command, **kwargs):
    subprocess.run(command, check=True, timeout=180, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=root / "dist")
    parser.add_argument("--core-wheel", type=Path)
    parser.add_argument("--core-sha256")
    parser.add_argument("--inside", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    (wheel,) = args.dist.resolve().glob("*.whl")
    clean = os.environ.copy()
    clean.pop("PYTHONPATH", None)
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    if not args.inside:
        if args.core_wheel is None or not args.core_sha256:
            parser.error("an existing official --core-wheel and its --core-sha256 are required")
        core_wheel = args.core_wheel.resolve()
        if digest(core_wheel) != args.core_sha256:
            raise AssertionError("official Core wheel checksum mismatch")
        environment = root / (".published-env-py%d%d" % sys.version_info[:2])
        if environment.exists():
            raise RuntimeError("published dependency gate requires a fresh environment")
        uv = ["vx", "--no-auto-install", "--cache-mode", "offline", "uv@0.12.7"]
        run(uv + ["venv", "--python", sys.executable, str(environment)], env=clean)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        dependencies = [str(core_wheel), str(wheel)]
        if sys.version_info < (3, 8):
            dependencies.append(str(core_wheel.parent / "typing_extensions-4.7.1-py3-none-any.whl"))
        run(
            uv
            + ["pip", "install", "--python", str(python), "--offline", "--no-index", "--no-deps"]
            + dependencies,
            env=clean,
        )
        run(uv + ["pip", "check", "--python", str(python)], env=clean)
        command = [
            str(python),
            "-I",
            str(Path(__file__).resolve()),
            "--inside",
            "--dist",
            str(args.dist.resolve()),
            "--core-wheel",
            str(core_wheel),
            "--core-sha256",
            args.core_sha256,
        ]
        if args.report:
            command += ["--report", str(args.report.resolve())]
        run(command, env=clean)
        return 0

    os.environ.pop("PYTHONPATH", None)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    import auroraview
    import auroraview._core as native

    import auroraview_nuke

    site = Path(sysconfig.get_path("purelib")).resolve()
    core_path = Path(auroraview.__file__).resolve()
    adapter_path = Path(auroraview_nuke.__file__).resolve()
    native_path = Path(native.__file__).resolve()
    assert core_path == (site / "auroraview/__init__.py").resolve()
    assert adapter_path == (site / "auroraview_nuke/__init__.py").resolve()
    assert native_path.parent == core_path.parent
    assert native_path.suffix.lower() in (".pyd", ".so", ".dylib")
    assert auroraview.__version__ == "0.5.11"
    assert "nuke" not in sys.modules
    with zipfile.ZipFile(wheel) as archive:
        for path in adapter_path.parent.glob("*.py"):
            assert path.read_bytes() == archive.read("auroraview_nuke/" + path.name)
    if args.core_wheel:
        assert digest(args.core_wheel) == args.core_sha256
        with zipfile.ZipFile(args.core_wheel) as archive:
            for path in (core_path, native_path):
                assert path.read_bytes() == archive.read("auroraview/" + path.name)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    accepted = result.testsRun > 0 and result.wasSuccessful() and not result.skipped
    report = {
        "accepted": accepted,
        "python": sys.version.split()[0],
        "core_version": "0.5.11",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skips": len(result.skipped),
        "candidate_wheel": wheel.name,
        "candidate_wheel_sha256": digest(wheel),
        "native_sha256": digest(native_path),
        "core_wheel": args.core_wheel.name if args.core_wheel else None,
        "core_wheel_sha256": args.core_sha256,
        "native_import": True,
        "source_core_injection": False,
        "private_core_used": False,
        "real_nuke": False,
        "native_webview_created": False,
        "native_bridge_acceptance": False,
        "dependency_range_all_versions": False,
        "scope": "official Core0.5.11 and installed adapter APIs; mocked Nuke scheduling",
        "candidate_inputs": [
            {"path": str(path.relative_to(root)).replace("\\", "/"), "sha256": digest(path)}
            for path in sorted((root / "src").rglob("*.py"))
        ],
        "test_inputs": [
            {"path": str(path.relative_to(root)).replace("\\", "/"), "sha256": digest(path)}
            for path in sorted((root / "tests").glob("*.py"))
        ],
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("RESULT_JSON=" + json.dumps(report, sort_keys=True))
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
