from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofalign.benchmark import aegis_runtime


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _fixture(tmp_path: Path) -> tuple[dict, Path]:
    project = tmp_path / "project"
    source = tmp_path / "aegis"
    checkpoint = tmp_path / "checkpoint"
    assets = tmp_path / "assets"
    existing = project / "existing"
    existing.mkdir(parents=True)

    r0_protocol = project / "r0-protocol.json"
    r0_summary = project / "r0-summary.json"
    requirements = source / "requirements.txt"
    simulator_requirements = source / "main" / "requirements.txt"
    override = project / "override.txt"
    config = project / "runtime-config" / "config.yaml"
    implementation = project / "implementation.py"
    metadata = checkpoint / "params" / "_METADATA"
    manifest = checkpoint / "params" / "manifest.ocdbt"
    norm_stats = (
        checkpoint
        / "assets"
        / "physical-intelligence"
        / "libero"
        / "norm_stats.json"
    )
    grounding_config = assets / "GroundingDINO_SwinT_OGC.py"
    grounding_weight = assets / "groundingdino_swint_ogc.pth"

    _write(r0_protocol, b'{}\n')
    _write(r0_summary, b'{"foundation_ready": true}\n')
    _write(requirements, b"policy\n")
    _write(simulator_requirements, b"simulator\n")
    _write(override, b"av==14.2.0\n")
    _write(config, f"assets: {existing}\n".encode())
    _write(implementation, b"implementation\n")
    _write(metadata, b"metadata")
    _write(manifest, b"manifest")
    _write(norm_stats, b"norm")
    _write(grounding_config, b"config")
    _write(grounding_weight, b"weight")

    digest_paths = {
        "r0_protocol": r0_protocol,
        "r0_summary": r0_summary,
        "policy_requirements": requirements,
        "simulator_requirements": simulator_requirements,
        "runtime_override": override,
        "libero_config": config,
        "checkpoint_metadata": metadata,
        "checkpoint_manifest": manifest,
        "checkpoint_norm_stats": norm_stats,
        "groundingdino_config": grounding_config,
        "groundingdino_weight": grounding_weight,
    }
    protocol = {
        "schema": "proofalign.safelibero-aegis-runtime-protocol-v1",
        "protocol_id": "test-runtime-r1",
        "authorization": {"model_load_probe_after_static_gate": True},
        "r0_foundation": {
            "protocol": str(r0_protocol.relative_to(project)),
            "summary": str(r0_summary.relative_to(project)),
        },
        "paths": {
            "source_root": str(source),
            "policy_python": str(source / ".aegis_venv" / "bin" / "python"),
            "simulator_python": str(source / "main" / ".venv" / "bin" / "python"),
            "libero_config": str(config.relative_to(project)),
            "runtime_override": str(override.relative_to(project)),
            "pi05_libero_checkpoint": str(checkpoint),
            "groundingdino_config": str(grounding_config),
            "groundingdino_weight": str(grounding_weight),
        },
        "expected": {
            "source": {"commit": "commit", "tree": "tree"},
            "policy_server": {
                "python": "3.11.15",
                "packages": {"torch": "2.7.1"},
                "distribution_count": 242,
                "inventory_sha256": "policy-inventory",
            },
            "simulator": {
                "python": "3.8.20",
                "packages": {"torch": "1.11.0+cu113"},
                "distribution_count": 152,
                "inventory_sha256": "simulator-inventory",
            },
            "groundingdino": {"weight_bytes": len(b"weight")},
            "sha256": {
                name: aegis_runtime.sha256_file(path)
                for name, path in digest_paths.items()
            },
        },
        "implementation": {
            str(implementation.relative_to(project)): aegis_runtime.sha256_file(
                implementation
            )
        },
    }
    return protocol, project


def _mock_probes(monkeypatch: pytest.MonkeyPatch, source: Path) -> None:
    monkeypatch.setattr(
        aegis_runtime,
        "_git_snapshot",
        lambda _: {"commit": "commit", "tree": "tree", "clean": True},
    )
    monkeypatch.setattr(
        aegis_runtime,
        "_policy_server_probe",
        lambda *_: {
            "probe_ok": True,
            "python": "3.11.15",
            "packages": {"torch": "2.7.1"},
            "distribution_count": 242,
            "inventory_sha256": "policy-inventory",
            "openpi_source": str(source / "openpi" / "src" / "openpi" / "__init__.py"),
            "openpi_client_source": str(
                source / "openpi" / "packages" / "openpi-client" / "client.py"
            ),
        },
    )
    monkeypatch.setattr(
        aegis_runtime,
        "_simulator_probe",
        lambda *_: {
            "probe_ok": True,
            "python": "3.8.20",
            "packages": {"torch": "1.11.0+cu113"},
            "distribution_count": 152,
            "inventory_sha256": "simulator-inventory",
            "libero_source": str(source / "safelibero" / "libero" / "__init__.py"),
            "openpi_client_source": str(
                source / "openpi" / "packages" / "openpi-client" / "client.py"
            ),
            "suite_count": 4,
            "scenario_count": 32,
            "initial_state_count": 1600,
        },
    )


def test_static_runtime_ready_never_authorizes_rollout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, project = _fixture(tmp_path)
    source = Path(protocol["paths"]["source_root"])
    _mock_probes(monkeypatch, source)

    report = aegis_runtime.build_runtime_preflight(protocol, project_root=project)

    assert report["static_runtime_ready"] is True
    assert report["model_load_probe_authorized"] is True
    assert report["formal_rollout_authorized"] is False
    assert set(report["counters"].values()) == {0}


def test_asset_tamper_blocks_static_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, project = _fixture(tmp_path)
    source = Path(protocol["paths"]["source_root"])
    _mock_probes(monkeypatch, source)
    Path(protocol["paths"]["groundingdino_weight"]).write_bytes(b"tampered")

    report = aegis_runtime.build_runtime_preflight(protocol, project_root=project)

    assert report["checks"]["groundingdino_weight_digest"] is False
    assert report["static_runtime_ready"] is False
    assert report["model_load_probe_authorized"] is False


def test_dirty_source_blocks_static_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, project = _fixture(tmp_path)
    source = Path(protocol["paths"]["source_root"])
    _mock_probes(monkeypatch, source)
    monkeypatch.setattr(
        aegis_runtime,
        "_git_snapshot",
        lambda _: {"commit": "commit", "tree": "tree", "clean": False},
    )

    report = aegis_runtime.build_runtime_preflight(protocol, project_root=project)

    assert report["checks"]["source_clean"] is False
    assert report["static_runtime_ready"] is False


def test_missing_python_probe_is_explicit_unknown(tmp_path: Path) -> None:
    result = aegis_runtime._json_python_probe(
        tmp_path / "missing-python", "print('never')", cwd=tmp_path
    )
    assert result["probe_ok"] is False
    assert "missing interpreter" in result["error"]


def test_flat_yaml_rejects_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("missing separator\n", encoding="utf-8")
    with pytest.raises(aegis_runtime.RuntimePreflightError):
        aegis_runtime._flat_yaml_paths(path)


def test_load_json_requires_object(tmp_path: Path) -> None:
    path = tmp_path / "value.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(aegis_runtime.RuntimePreflightError):
        aegis_runtime.load_json(path)
