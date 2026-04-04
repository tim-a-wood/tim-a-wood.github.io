from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


ARTIFACT_FILENAMES: Dict[str, str] = {
    "reference_pack": "reference_pack.json",
    "stylepack": "stylepack.json",
    "room_semantics": "room_semantics.json",
    "environment_kit": "environment_kit.json",
    "environment_manifest": "environment_manifest.json",
    "validation_report": "validation_report.json",
}

DERIVED_SUBDIR = Path("derived") / "v3"
ARTIFACT_REFERENCE_PACK = ARTIFACT_FILENAMES["reference_pack"]
ARTIFACT_STYLEPACK = ARTIFACT_FILENAMES["stylepack"]
ARTIFACT_ROOM_SEMANTICS = ARTIFACT_FILENAMES["room_semantics"]
ARTIFACT_ENVIRONMENT_KIT = ARTIFACT_FILENAMES["environment_kit"]
ARTIFACT_ENVIRONMENT_MANIFEST = ARTIFACT_FILENAMES["environment_manifest"]
ARTIFACT_VALIDATION_REPORT = ARTIFACT_FILENAMES["validation_report"]


def staged_artifact_root(projects_root: Path, project_id: str, room_id: str) -> Path:
    return projects_root / project_id / "room_environment_assets" / room_id / DERIVED_SUBDIR


def derived_room_dir(room_root: Path, room_id: str) -> Path:
    return room_root / DERIVED_SUBDIR / room_id


def derived_artifact_path(room_root: Path, room_id: str, artifact_filename: str) -> Path:
    return derived_room_dir(room_root, room_id) / artifact_filename


def artifact_path(projects_root: Path, project_id: str, room_id: str, artifact_kind: str) -> Path:
    filename = ARTIFACT_FILENAMES[artifact_kind]
    return staged_artifact_root(projects_root, project_id, room_id) / filename


def save_artifact(
    projects_root: Path,
    project_id: str,
    room_id: str,
    artifact_kind: str,
    payload: Dict[str, Any],
) -> Path:
    path = artifact_path(projects_root, project_id, room_id, artifact_kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_artifact(
    projects_root: Path,
    project_id: str,
    room_id: str,
    artifact_kind: str,
) -> Optional[Dict[str, Any]]:
    path = artifact_path(projects_root, project_id, room_id, artifact_kind)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def default_registry(room_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    registry: Dict[str, Dict[str, Any]] = {}
    for artifact_kind, filename in ARTIFACT_FILENAMES.items():
        registry[artifact_kind] = {
            "artifact_kind": artifact_kind,
            "artifact_id": f"{room_id or 'room'}-{artifact_kind}",
            "status": "idle",
            "relative_path": f"derived/v3/{filename}",
        }
    return registry
