"""Read-only runtime readiness checks for the pinned AEGIS/SafeLIBERO stack.

This module deliberately stops before policy construction, socket binding,
simulator construction, or environment stepping.  It is the second gate after
``safelibero_foundation``: R0 establishes source/data/metric semantics, while
this R1 gate establishes that the isolated runtimes and immutable assets have
the identities declared by a frozen protocol.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence


RUNTIME_REPORT_SCHEMA = "proofalign.safelibero-aegis-runtime-report-v1"
_PROBE_MARKER = "PROOFALIGN_RUNTIME_JSON="


class RuntimePreflightError(RuntimeError):
    """Raised when a read-only probe cannot produce trustworthy evidence."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimePreflightError(f"expected JSON object: {path}")
    return value


def _flat_yaml_paths(path: Path) -> dict[str, str]:
    """Parse the intentionally flat runtime config without adding a dependency."""

    result: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise RuntimePreflightError(f"invalid flat YAML at {path}:{line_number}")
        result[key.strip()] = value.strip()
    return result


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    merged_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        merged_env.update(env)
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _git_snapshot(source_root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        result = _run(["git", *args], cwd=source_root)
        if result.returncode != 0:
            raise RuntimePreflightError(result.stderr.strip() or "git probe failed")
        return result.stdout.strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "clean": not bool(git("status", "--porcelain", "--untracked-files=all")),
    }


def _json_python_probe(
    python: Path,
    code: str,
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if not python.is_file():
        return {
            "probe_ok": False,
            "error": f"missing interpreter: {python}",
        }
    result = _run(
        [str(python), "-c", code],
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    marker_lines = [
        line[len(_PROBE_MARKER) :]
        for line in result.stdout.splitlines()
        if line.startswith(_PROBE_MARKER)
    ]
    if result.returncode != 0 or len(marker_lines) != 1:
        return {
            "probe_ok": False,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        }
    try:
        payload = json.loads(marker_lines[0])
    except json.JSONDecodeError as exc:
        raise RuntimePreflightError(f"invalid subprocess probe JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimePreflightError("subprocess probe did not emit a JSON object")
    payload["probe_ok"] = True
    return payload


def _policy_server_probe(python: Path, source_root: Path) -> dict[str, Any]:
    code = f"""
import hashlib
import importlib.metadata as m
import json
from pathlib import Path
import sys
import openpi
import openpi_client
names = ['av', 'jax', 'jaxlib', 'openpi', 'openpi-client', 'torch', 'websockets']
inventory = sorted(
    f"{{dist.metadata['Name'].lower().replace('_', '-')}}=={{dist.version}}"
    for dist in m.distributions()
)
payload = {{
    'python': '.'.join(map(str, sys.version_info[:3])),
    'packages': {{name: m.version(name) for name in names}},
    'distribution_count': len(inventory),
    'inventory_sha256': hashlib.sha256(('\\n'.join(inventory) + '\\n').encode()).hexdigest(),
    'openpi_source': str(Path(openpi.__file__).resolve()),
    'openpi_client_source': str(Path(openpi_client.__file__).resolve()),
}}
print('{_PROBE_MARKER}' + json.dumps(payload, sort_keys=True))
"""
    return _json_python_probe(python, code, cwd=source_root)


def _simulator_probe(
    python: Path,
    source_root: Path,
    libero_config_dir: Path,
) -> dict[str, Any]:
    code = f"""
import hashlib
import importlib.metadata as m
import json
from pathlib import Path
import sys
from libero.libero import benchmark
import libero.libero as libero_impl
import groundingdino
import openpi_client
names = ['groundingdino-py', 'mujoco', 'numpy', 'openpi-client', 'robosuite', 'torch', 'websockets']
inventory = sorted(
    f"{{dist.metadata['Name'].lower().replace('_', '-')}}=={{dist.version}}"
    for dist in m.distributions()
)
suites = {{}}
total = 0
for key in sorted(k for k in benchmark.get_benchmark_dict() if k.startswith('safelibero_')):
    suites[key] = {{}}
    for level in ['I', 'II']:
        suite = benchmark.get_benchmark_dict()[key](safety_level=level)
        counts = [len(suite.get_task_init_states(index)) for index in range(suite.n_tasks)]
        suites[key][level] = {{'tasks': suite.n_tasks, 'init_counts': counts}}
        total += sum(counts)
payload = {{
    'python': '.'.join(map(str, sys.version_info[:3])),
    'packages': {{name: m.version(name) for name in names}},
    'distribution_count': len(inventory),
    'inventory_sha256': hashlib.sha256(('\\n'.join(inventory) + '\\n').encode()).hexdigest(),
    'libero_source': str(Path(libero_impl.__file__).resolve()),
    'groundingdino_source': str(Path(groundingdino.__file__).resolve()),
    'openpi_client_source': str(Path(openpi_client.__file__).resolve()),
    'suites': suites,
    'suite_count': len(suites),
    'scenario_count': sum(len(levels) * 4 for levels in suites.values()),
    'initial_state_count': total,
}}
print('{_PROBE_MARKER}' + json.dumps(payload, sort_keys=True))
"""
    env = {
        "LIBERO_CONFIG_PATH": str(libero_config_dir),
        "PYTHONPATH": str(source_root / "safelibero"),
        "MPLCONFIGDIR": "/tmp/proofalign-aegis-matplotlib",
    }
    return _json_python_probe(
        python,
        code,
        cwd=source_root,
        env=env,
        timeout_seconds=180,
    )


def _packages_match(actual: Any, expected: Any) -> bool:
    return isinstance(actual, dict) and isinstance(expected, dict) and all(
        actual.get(name) == version for name, version in expected.items()
    )


def build_runtime_preflight(
    protocol: Mapping[str, Any],
    *,
    project_root: Path,
) -> dict[str, Any]:
    """Build a static R1 report without constructing policies or environments."""

    if protocol.get("schema") != "proofalign.safelibero-aegis-runtime-protocol-v1":
        raise RuntimePreflightError("unsupported runtime protocol schema")

    paths = protocol["paths"]
    source_root = Path(paths["source_root"])
    policy_python = Path(paths["policy_python"])
    simulator_python = Path(paths["simulator_python"])
    config_path = project_root / paths["libero_config"]
    config_dir = config_path.parent
    checkpoint_root = Path(paths["pi05_libero_checkpoint"])
    grounding_config = Path(paths["groundingdino_config"])
    grounding_weight = Path(paths["groundingdino_weight"])

    r0 = protocol["r0_foundation"]
    r0_protocol_path = project_root / r0["protocol"]
    r0_summary_path = project_root / r0["summary"]
    r0_summary = load_json(r0_summary_path)
    source = _git_snapshot(source_root)
    policy = _policy_server_probe(policy_python, source_root)
    simulator = _simulator_probe(simulator_python, source_root, config_dir)

    config_values = _flat_yaml_paths(config_path)
    config_paths_exist = bool(config_values) and all(
        Path(value).exists() for value in config_values.values()
    )

    expected = protocol["expected"]
    digests = expected["sha256"]
    checkpoint_files = {
        "metadata": checkpoint_root / "params" / "_METADATA",
        "manifest": checkpoint_root / "params" / "manifest.ocdbt",
        "norm_stats": checkpoint_root
        / "assets"
        / "physical-intelligence"
        / "libero"
        / "norm_stats.json",
    }

    observed_digests: dict[str, str | None] = {}
    digest_paths = {
        "r0_protocol": r0_protocol_path,
        "r0_summary": r0_summary_path,
        "policy_requirements": source_root / "requirements.txt",
        "simulator_requirements": source_root / "main" / "requirements.txt",
        "runtime_override": project_root / paths["runtime_override"],
        "libero_config": config_path,
        "checkpoint_metadata": checkpoint_files["metadata"],
        "checkpoint_manifest": checkpoint_files["manifest"],
        "checkpoint_norm_stats": checkpoint_files["norm_stats"],
        "groundingdino_config": grounding_config,
        "groundingdino_weight": grounding_weight,
    }
    for name, path in digest_paths.items():
        observed_digests[name] = sha256_file(path) if path.is_file() else None

    implementation_hashes: dict[str, str | None] = {}
    for relative, pinned in protocol["implementation"].items():
        implementation_path = project_root / relative
        implementation_hashes[relative] = (
            sha256_file(implementation_path) if implementation_path.is_file() else None
        )

    checks = {
        "r0_foundation_ready": r0_summary.get("foundation_ready") is True,
        "r0_protocol_digest": observed_digests["r0_protocol"] == digests["r0_protocol"],
        "r0_summary_digest": observed_digests["r0_summary"] == digests["r0_summary"],
        "source_commit": source["commit"] == expected["source"]["commit"],
        "source_tree": source["tree"] == expected["source"]["tree"],
        "source_clean": source["clean"] is True,
        "policy_requirements_digest": observed_digests["policy_requirements"]
        == digests["policy_requirements"],
        "simulator_requirements_digest": observed_digests["simulator_requirements"]
        == digests["simulator_requirements"],
        "runtime_override_digest": observed_digests["runtime_override"]
        == digests["runtime_override"],
        "libero_config_digest": observed_digests["libero_config"]
        == digests["libero_config"],
        "libero_config_paths_exist": config_paths_exist,
        "policy_probe": policy.get("probe_ok") is True,
        "policy_python": policy.get("python") == expected["policy_server"]["python"],
        "policy_packages": _packages_match(
            policy.get("packages"), expected["policy_server"]["packages"]
        ),
        "policy_distribution_count": policy.get("distribution_count")
        == expected["policy_server"]["distribution_count"],
        "policy_inventory_digest": policy.get("inventory_sha256")
        == expected["policy_server"]["inventory_sha256"],
        "policy_source_identity": str(source_root / "openpi")
        in str(policy.get("openpi_source", "")),
        "policy_client_source_identity": str(source_root / "openpi")
        in str(policy.get("openpi_client_source", "")),
        "simulator_probe": simulator.get("probe_ok") is True,
        "simulator_python": simulator.get("python") == expected["simulator"]["python"],
        "simulator_packages": _packages_match(
            simulator.get("packages"), expected["simulator"]["packages"]
        ),
        "simulator_distribution_count": simulator.get("distribution_count")
        == expected["simulator"]["distribution_count"],
        "simulator_inventory_digest": simulator.get("inventory_sha256")
        == expected["simulator"]["inventory_sha256"],
        "simulator_source_identity": str(source_root / "safelibero")
        in str(simulator.get("libero_source", "")),
        "simulator_client_source_identity": str(source_root / "openpi")
        in str(simulator.get("openpi_client_source", "")),
        "suite_count": simulator.get("suite_count") == 4,
        "scenario_count": simulator.get("scenario_count") == 32,
        "initial_state_count": simulator.get("initial_state_count") == 1600,
        "checkpoint_metadata_digest": observed_digests["checkpoint_metadata"]
        == digests["checkpoint_metadata"],
        "checkpoint_manifest_digest": observed_digests["checkpoint_manifest"]
        == digests["checkpoint_manifest"],
        "checkpoint_norm_stats_digest": observed_digests["checkpoint_norm_stats"]
        == digests["checkpoint_norm_stats"],
        "groundingdino_config_digest": observed_digests["groundingdino_config"]
        == digests["groundingdino_config"],
        "groundingdino_weight_digest": observed_digests["groundingdino_weight"]
        == digests["groundingdino_weight"],
        "groundingdino_weight_size": grounding_weight.is_file()
        and grounding_weight.stat().st_size == expected["groundingdino"]["weight_bytes"],
        "implementation_hashes": all(
            implementation_hashes.get(relative) == pinned
            for relative, pinned in protocol["implementation"].items()
        ),
    }
    static_ready = all(checks.values())

    counters = {
        "policy_construction_count": 0,
        "model_inference_call_count": 0,
        "server_socket_bind_count": 0,
        "simulator_construction_count": 0,
        "env_step_count": 0,
    }
    return {
        "schema": RUNTIME_REPORT_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "authorization": protocol["authorization"],
        "checks": checks,
        "source": source,
        "policy_server": policy,
        "simulator": simulator,
        "config": {
            "path": str(config_path),
            "values": config_values,
            "all_paths_exist": config_paths_exist,
        },
        "assets": {
            "pi05_libero_checkpoint": str(checkpoint_root),
            "groundingdino_config": str(grounding_config),
            "groundingdino_weight": str(grounding_weight),
            "observed_sha256": observed_digests,
        },
        "implementation_sha256": implementation_hashes,
        "counters": counters,
        "static_runtime_ready": static_ready,
        "model_load_probe_authorized": static_ready
        and protocol["authorization"].get("model_load_probe_after_static_gate") is True,
        "formal_rollout_authorized": False,
        "status": (
            "static_runtime_ready_model_probe_pending"
            if static_ready
            else "static_runtime_blocked"
        ),
    }


def dump_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
