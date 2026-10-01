"""Provenance: record exactly which policy, configuration and code produced a result.

A verdict is only meaningful for the release it was computed on. Every campaign stores
this record when it is created, and every report prints it, so a result can be traced
back to the policy weights, config files and code version that produced it.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from importlib import metadata

from . import CONFIG_DIR, ROOT
from .policy import POLICY_PATH

PACKAGES = ("numpy", "scikit-learn", "duckdb")
CRLF, LF = bytes([13, 10]), bytes([10])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, text: bool = False) -> str | None:
    """Hash of a file's bytes. With `text`, CRLF is normalised to LF first, so a checkout on
    Windows and one on Linux hash identically."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    return sha256_bytes(data.replace(CRLF, LF) if text else data)


def policy_hash(policy=None) -> str | None:
    """SHA-256 of the policy as serialised to `results/policy.json`.

    With a policy object, hashes its serialisation, which is byte-identical to the file
    `LearnedACC.save()` writes. That way the hash describes the policy actually simulated,
    even when it was trained in memory and never saved. Without one, hashes the file.
    """
    if policy is not None:
        return sha256_bytes(policy.to_json().encode())
    return sha256_file(POLICY_PATH)


def config_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p, text=True) for p in sorted(CONFIG_DIR.iterdir())
            if p.is_file()}


def code_hash() -> str:
    """One SHA-256 over every `avval/*.py` source file (name and content, LF-normalised).

    Unlike the git commit, it does not change when only docs or results are committed, so it
    is what decides whether results still belong to the current code (see `same_release`).
    """
    h = hashlib.sha256()
    for p in sorted((ROOT / "avval").glob("*.py")):
        h.update(f"{p.name}:{sha256_file(p, text=True)};".encode())
    return h.hexdigest()


def git_commit() -> str:
    """HEAD commit hash, or "uncommitted" if there is no git or tracked source files are dirty.

    Files under `results/` are excluded from the dirty check: reports and figures are
    outputs of a run, and regenerating them should not make the code look uncommitted.
    The policy weights are covered separately by their own hash.
    """
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=10)
    try:
        head = git("rev-parse", "HEAD")
        if head.returncode != 0:
            return "uncommitted"
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!results")
        if dirty.returncode != 0 or dirty.stdout.strip():
            return "uncommitted"
        return head.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "uncommitted"


def package_versions() -> dict[str, str | None]:
    out = {}
    for pkg in PACKAGES:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def provenance(policy=None) -> dict:
    return {"policy_sha256": policy_hash(policy),
            "config_sha256": config_hashes(),
            "code_sha256": code_hash(),
            "git_commit": git_commit(),
            "python": platform.python_version(),
            "packages": package_versions()}


# Everything that can change a simulation result. The git commit is recorded for traceability
# but not compared: a docs-only commit must not invalidate results.
RELEASE_KEYS = ("policy_sha256", "config_sha256", "code_sha256", "python", "packages")


def same_release(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in RELEASE_KEYS)
