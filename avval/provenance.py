"""Provenance: code identity, runtime fingerprint and the record stored with every campaign.

The release identity (policy, parsed configuration, code) is computed by
`avval.config.Release` from the objects a simulation actually uses. This module supplies
the pieces that are not configuration:

- `code_hash`: one SHA-256 over every `avval/*.py` source file (LF-normalised). It changes
  with any code change, and not with docs or results.
- `runtime_fingerprint`: Python, platform and the versions of every material dependency
  (numerical simulation, statistics, YAML parsing, database, model training, plotting,
  the agent client). `runtime_id` hashes the subset that can change stored results.
- `check_lock`: compares installed versions with `requirements-lock.txt`.

The git commit is recorded for traceability but is never part of an identity: a docs-only
commit must not invalidate results.
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from importlib import metadata

from . import ROOT
from .frozen import content_hash
from .policy import POLICY_PATH

# Distribution names. RESULT_PACKAGES can change a stored campaign result or statistic and are
# hashed into the runtime ID: simulation and statistics (numpy, scipy), data handling
# (pandas, pyarrow, duckdb), configuration parsing (PyYAML), scikit-learn (the
# Bayesian-optimisation baseline chooses its runs with it, so it changes benchmark campaigns,
# not only policy training) and the anthropic client (it builds and parses the agent's API
# traffic, and agent campaigns are stored results). matplotlib only renders figures from
# stored data: it is recorded, not hashed.
RESULT_PACKAGES = ("numpy", "scipy", "pandas", "pyarrow", "duckdb", "PyYAML", "scikit-learn",
                   "anthropic")
OTHER_PACKAGES = ("matplotlib",)
LOCK_PATH = ROOT / "requirements-lock.txt"
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
    `LearnedACC.save()` writes, so the hash describes the policy actually simulated. Without
    one, hashes the file.
    """
    if policy is not None:
        return sha256_bytes(policy.to_json().encode())
    return sha256_file(POLICY_PATH)


def code_hash() -> str:
    """One SHA-256 over every `avval/*.py` source file (name and LF-normalised content)."""
    h = hashlib.sha256()
    for p in sorted((ROOT / "avval").glob("*.py")):
        h.update(f"{p.name}:{sha256_file(p, text=True)};".encode())
    return h.hexdigest()


def git_commit() -> str:
    """HEAD commit hash, or "uncommitted" if there is no git or tracked source files are dirty.

    Files under `results/` are excluded from the dirty check: reports and figures are
    outputs of a run.
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


def source_tree_problems() -> list[str]:
    """Why the source tree is not clean enough for final evidence (empty = clean): tracked
    changes anywhere outside results/, or untracked files in code, configuration, scripts or
    requirements, which would change behaviour without being committed."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=20)
    try:
        if git("rev-parse", "HEAD").returncode != 0:
            return ["not a git repository with a commit"]
        dirty = git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!results")
        untracked = git("status", "--porcelain", "--untracked-files=all", "--", "avval",
                        "config", "scripts", "requirements.txt", "requirements-dev.txt",
                        "requirements-lock.txt")
    except (OSError, subprocess.SubprocessError) as e:
        return [f"git unavailable: {e}"]
    out = [f"uncommitted change: {ln.strip()}" for ln in dirty.stdout.splitlines() if ln.strip()]
    out += [f"untracked source file: {ln[3:]}" for ln in untracked.stdout.splitlines()
            if ln.startswith("??")]
    return out


def final_evidence_problems() -> list[str]:
    """Everything that prevents a final-evidence campaign (empty = allowed): a dirty source
    tree, no commit, or an environment that does not match the lock file."""
    from .config import rehearsal_active
    problems = source_tree_problems()
    if rehearsal_active():
        problems.insert(0, "rehearsal mode is active (AVVAL_REHEARSAL=1): rehearsal sizes "
                           "are never final evidence")
    if not problems and git_commit() == "uncommitted":
        problems.append("no valid commit hash")
    return problems + [f"lock: {p}" for p in check_lock()]


def package_versions(packages=RESULT_PACKAGES + OTHER_PACKAGES) -> dict[str, str | None]:
    out = {}
    for pkg in packages:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def runtime_fingerprint() -> dict:
    return {"python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(), "machine": platform.machine(),
            "packages": package_versions()}


def runtime_id(fp: dict | None = None) -> str:
    """Hash of the runtime components that can change stored results: Python, OS, machine
    architecture and RESULT_PACKAGES. Evidence from different runtimes is not combined."""
    fp = fp or runtime_fingerprint()
    return content_hash({k: fp[k] for k in ("python", "implementation", "system", "machine")}
                        | {"packages": {p: fp["packages"].get(p) for p in RESULT_PACKAGES}})


def read_lock(path=LOCK_PATH) -> dict[str, str]:
    """{distribution (lower-case): version} from a pip-style lock file."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# python=="):  # the interpreter, recorded as a comment
            out["python"] = line.split("==", 1)[1].split()[0]
            continue
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, ver = line.split("==", 1)
            out[name.strip().lower()] = ver.strip()
    return out


def check_lock(path=LOCK_PATH) -> list[str]:
    """Differences between the installed environment and the lock file (empty = matches)."""
    lock = read_lock(path)
    if not lock:
        return [f"no lock file at {path}"]
    problems = []
    for name, want in sorted(lock.items()):
        if name == "python":
            continue
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            problems.append(f"{name}: locked {want}, not installed")
            continue
        if have != want:
            problems.append(f"{name}: locked {want}, installed {have}")
    want_py = lock.get("python")
    if want_py and want_py != platform.python_version():
        problems.append(f"python: locked {want_py}, running {platform.python_version()}")
    return problems


def provenance(release, evidence_mode: str = "development") -> dict:
    """The provenance record stored with a campaign: the release manifest summary, the runtime
    fingerprint and identity, the lock-file status and the git commit (traceability only)."""
    fp = runtime_fingerprint()
    return {"release_id": release.release_id,
            "policy_sha256": release.policy_sha256,
            "code_sha256": release.code_sha256,
            "config_sha256": release.config_sha256,
            "overrides": release.manifest()["overrides"],
            "nominal": release.is_nominal,
            "exposure_model_id": release.exposure_model_id,
            "runtime": fp, "runtime_id": runtime_id(fp),
            "lock_mismatches": check_lock(),
            "git_commit": git_commit(), "evidence_mode": evidence_mode,
            "rehearsal": os.environ.get("AVVAL_REHEARSAL") == "1",
            "argv": list(sys.argv[:1])}
