#!/usr/bin/env python3
"""Build or verify deterministic, instruction-only skill/plugin ZIP packages.

No third-party Python packages, network requests, skill execution, or extraction.
Only the explicit resource allowlists below can enter a package.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = {
    "continue-work": (
        "SKILL.md",
        "agents/openai.yaml",
        "references/SETUP.md",
        "snippets/AGENTS.md",
        "snippets/gitignore.txt",
        "templates/continuation.json",
        "templates/continuation-handover.md",
    ),
    "reuse-scout": (
        "SKILL.md",
        "agents/openai.yaml",
        "THIRD_PARTY_NOTICES.md",
        "LICENSE.upstream.txt",
    ),
}


def read_sources() -> dict[str, dict[str, bytes]]:
    result = {}
    skills_root = ROOT / "skills"
    if skills_root.is_symlink():
        raise ValueError("The skills directory must not be a symlink")
    actual_skills = {p.name for p in skills_root.iterdir() if p.is_dir()}
    if actual_skills != set(RESOURCES):
        raise ValueError(f"Unexpected skill directories: {actual_skills}")
    for name, expected in RESOURCES.items():
        folder = skills_root / name
        if folder.is_symlink():
            raise ValueError(f"Skill folder is a symlink: {name}")
        actual = set()
        for item in folder.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Symlink refused: {item.relative_to(ROOT)}")
            if item.is_file():
                actual.add(item.relative_to(folder).as_posix())
        if actual != set(expected):
            raise ValueError(
                f"Resource allowlist mismatch for {name}; "
                f"extra={sorted(actual - set(expected))}, "
                f"missing={sorted(set(expected) - actual)}"
            )
        contents = {rel: (folder / rel).read_bytes() for rel in expected}
        text = contents["SKILL.md"].decode("utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        if not match:
            raise ValueError(f"Missing frontmatter in {name}")
        fields = {}
        for line in match.group(1).splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key.strip()] = value.strip().strip('"\'')
        if fields.get("name") != name or not fields.get("description"):
            raise ValueError(f"Invalid name/description metadata in {name}")
        if any(len(data) > 2_000_000 for data in contents.values()):
            raise ValueError(f"Unexpectedly large instruction resource in {name}")
        result[name] = contents
    checkpoint = json.loads(result["continue-work"]["templates/continuation.json"])
    if checkpoint["status"] != "idle" or checkpoint["projectRoot"] is not None:
        raise ValueError("A private or initialized checkpoint must not be packaged")
    if checkpoint["task"] is not None or checkpoint["nextUnit"] is not None:
        raise ValueError("The checkpoint template must not contain a task")
    for field in (
        "authoritativePaths", "outstandingRequests", "completed", "inFlight",
        "pendingMutations", "blockers", "activeWorkers", "restrictions",
    ):
        if checkpoint.get(field) != []:
            raise ValueError(f"Checkpoint template contains state: {field}")
    if checkpoint["handover"] != ".scratch/continuation-handover.md":
        raise ValueError("Checkpoint handover path does not match the template")
    policy = result["continue-work"]["agents/openai.yaml"].decode("utf-8")
    if not re.search(r"^  allow_implicit_invocation: false\r?$", policy, re.M):
        raise ValueError("Continue Work's Codex explicit-only policy is missing")
    return result


def make_zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(entries.items()):
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise ValueError(f"Unsafe archive path: {name}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def verify_archive(data: bytes, expected: dict[str, bytes]) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("Archive entries differ from the explicit resource list")
        if archive.testzip() is not None:
            raise ValueError("Archive CRC validation failed")
        for name, content in expected.items():
            if archive.read(name) != content:
                raise ValueError(f"Archive content differs from source: {name}")


def build(check: bool) -> None:
    sources = read_sources()
    manifest_path = ROOT / "plugin.json"
    if manifest_path.is_symlink():
        raise ValueError("Plugin manifest must not be a symlink")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("name") != "mdraf1-skills":
        raise ValueError("Unexpected portable plugin name")
    if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        raise ValueError("Unexpected portable plugin schema reference")
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")):
        raise ValueError("Plugin version must be a simple semantic version")
    artifacts = {}
    plugin_entries = {"plugin.json": manifest_bytes}
    for name, files in sources.items():
        entries = {f"{name}/{rel}": data for rel, data in files.items()}
        payload = make_zip(entries)
        for extension in ("zip", "skill"):
            artifacts[f"{name}.{extension}"] = (payload, entries)
        plugin_entries.update({f"skills/{name}/{rel}": data for rel, data in files.items()})
    artifacts["skills-plugin.zip"] = (make_zip(plugin_entries), plugin_entries)
    out = ROOT / "dist"
    if out.is_symlink():
        raise ValueError("Distribution directory must not be a symlink")
    if not check:
        out.mkdir(exist_ok=True)
    for filename, (generated, entries) in sorted(artifacts.items()):
        target = out / filename
        if target.is_symlink():
            raise ValueError(f"Distribution target is a symlink: {filename}")
        previous = target.read_bytes() if target.exists() else None
        if check:
            if previous is None:
                raise ValueError(f"Missing distribution: {filename}")
            verify_archive(previous, entries)
            print(f"OK {filename}: {len(entries)} entries, {len(previous)} bytes")
        else:
            verify_archive(generated, entries)
            if previous != generated:
                target.write_bytes(generated)
            digest = hashlib.sha256(generated).hexdigest()[:16]
            print(f"BUILT {filename}: {len(entries)} entries, sha256 {digest}")
    for name in RESOURCES:
        if (out / f"{name}.zip").read_bytes() != (out / f"{name}.skill").read_bytes():
            raise ValueError(f"ZIP and .skill copies differ for {name}")
    print("PASS: two skills; source/package parity; private-state checks; ZIP/.skill parity.")
    print("Not tested: installation or execution in any destination AI product.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing packages without rewriting them")
    args = parser.parse_args()
    try:
        build(args.check)
    except (OSError, ValueError, KeyError, UnicodeError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
