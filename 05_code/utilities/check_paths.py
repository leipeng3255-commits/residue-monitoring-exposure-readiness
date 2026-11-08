#!/usr/bin/env python3
"""Read the project path configuration and report storage readiness.

This utility uses only the Python standard library. It never creates, deletes,
moves, downloads, or changes scientific data.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


REQUIRED_KEYS = (
    "project_root",
    "data_root",
    "raw_data_root",
    "intermediate_data_root",
    "processed_data_root",
    "outputs_root",
    "plant_trade_raw_root",
    "plant_trade_intermediate_root",
    "plant_trade_processed_root",
    "plant_trade_outputs_root",
    "animal_food_raw_root",
    "animal_food_intermediate_root",
    "animal_food_processed_root",
    "animal_food_outputs_root",
    "multicountry_partial_identification_raw_root",
    "multicountry_partial_identification_intermediate_root",
    "multicountry_partial_identification_processed_root",
    "multicountry_partial_identification_outputs_root",
    "organic_network_toxicology_gbd_raw_root",
    "organic_network_toxicology_gbd_intermediate_root",
    "organic_network_toxicology_gbd_processed_root",
    "organic_network_toxicology_gbd_outputs_root",
    "monitoring_to_health_inference_raw_root",
    "monitoring_to_health_inference_intermediate_root",
    "monitoring_to_health_inference_processed_root",
    "monitoring_to_health_inference_outputs_root",
)

def load_simple_yaml(path: Path) -> dict[str, str]:
    """Parse the flat, quoted scalar mapping used by paths.yaml.

    A dedicated YAML dependency is intentionally avoided for this guard script.
    The project configuration must remain a one-level key-to-path mapping.
    """
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"line {line_number}: expected 'key: value'")
        key, value = (part.strip() for part in line.split(":", 1))
        if key not in REQUIRED_KEYS:
            continue
        if key in values:
            raise ValueError(f"line {line_number}: duplicate key '{key}'")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            raise ValueError(f"line {line_number}: '{key}' has an empty path")
        values[key] = value

    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise ValueError("missing required key(s): " + ", ".join(missing))
    return values


def mount_point(path: Path) -> Path | None:
    """Return the existing filesystem mount that contains *path*."""
    candidate = path.resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.exists():
        return None
    while candidate != candidate.parent:
        if os.path.ismount(candidate):
            return candidate
        candidate = candidate.parent
    return candidate if os.path.ismount(candidate) else None


def is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def report(label: str, passed: bool, detail: str) -> bool:
    state = "PASS" if passed else "FAIL"
    print(f"{state:<4} {label}: {detail}")
    return passed


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "00_admin" / "paths.yaml"
    checks: list[bool] = []

    checks.append(report("configuration", config_path.is_file(), str(config_path)))
    if not config_path.is_file():
        print("FAIL overall: paths.yaml is missing; stopping without changing data.")
        return 1

    try:
        configured = {key: Path(value).expanduser() for key, value in load_simple_yaml(config_path).items()}
    except (OSError, UnicodeError, ValueError) as error:
        print(f"FAIL configuration: {error}")
        return 1

    checks.append(
        report(
            "project_root",
            configured["project_root"].resolve() == project_root,
            f"configured={configured['project_root']} actual={project_root}",
        )
    )

    for key in REQUIRED_KEYS[1:]:
        directory = configured[key]
        checks.append(report(key, directory.is_dir(), str(directory)))

    data_root = configured["data_root"]
    data_mount = mount_point(data_root)
    external_online = data_mount is not None and data_mount != Path("/")
    mount_detail = str(data_mount) if data_mount is not None else "no mounted filesystem found"
    checks.append(report("external_drive_online", external_online, mount_detail))
    checks.append(
        report(
            "external_drive_identity",
            external_online and data_mount.name == "大彭",
            f"mounted volume={data_mount.name if data_mount else 'unavailable'}",
        )
    )

    checks.append(report("data_root_writable", data_root.is_dir() and os.access(data_root, os.W_OK), str(data_root)))

    for key in REQUIRED_KEYS[2:]:
        checks.append(
            report(
                f"{key}_under_data_root",
                is_descendant(configured[key], data_root),
                str(configured[key]),
            )
        )

    for branch, parent_key in (
        ("plant_trade_raw_root", "raw_data_root"),
        ("plant_trade_intermediate_root", "intermediate_data_root"),
        ("plant_trade_processed_root", "processed_data_root"),
        ("plant_trade_outputs_root", "outputs_root"),
        ("animal_food_raw_root", "raw_data_root"),
        ("animal_food_intermediate_root", "intermediate_data_root"),
        ("animal_food_processed_root", "processed_data_root"),
        ("animal_food_outputs_root", "outputs_root"),
        ("multicountry_partial_identification_raw_root", "raw_data_root"),
        ("multicountry_partial_identification_intermediate_root", "intermediate_data_root"),
        ("multicountry_partial_identification_processed_root", "processed_data_root"),
        ("multicountry_partial_identification_outputs_root", "outputs_root"),
        ("organic_network_toxicology_gbd_raw_root", "raw_data_root"),
        ("organic_network_toxicology_gbd_intermediate_root", "intermediate_data_root"),
        ("organic_network_toxicology_gbd_processed_root", "processed_data_root"),
        ("organic_network_toxicology_gbd_outputs_root", "outputs_root"),
        ("monitoring_to_health_inference_raw_root", "raw_data_root"),
        ("monitoring_to_health_inference_intermediate_root", "intermediate_data_root"),
        ("monitoring_to_health_inference_processed_root", "processed_data_root"),
        ("monitoring_to_health_inference_outputs_root", "outputs_root"),
    ):
        checks.append(
            report(
                f"{branch}_under_{parent_key}",
                is_descendant(configured[branch], configured[parent_key]),
                str(configured[branch]),
            )
        )

    all_passed = all(checks)
    print(("PASS" if all_passed else "FAIL") + " overall: path readiness check completed without changing data.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
