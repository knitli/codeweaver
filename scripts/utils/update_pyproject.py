#!/usr/bin/env python3
"""Update pyproject.toml dependency constraints to match uv.lock versions."""

import tomllib

from pathlib import Path


def main() -> None:
    """Update pyproject.toml dependencies to match uv.lock versions."""
    lock_data = tomllib.loads(Path("uv.lock").read_text())
    locked_versions: dict[str, str] = {
        pkg["name"]: pkg["version"] for pkg in lock_data.get("package", [])
    }
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('"') and any(
            op in stripped for op in (">=", "==", "<=", ">", "<", "~=", "!=") if ";" not in stripped
        ):
            pkg_name = (
                stripped.split('"')[1].split(">")[0].split("<")[0].split("=")[0].split("[")[0]
            )
            if pkg_name in locked_versions:
                indent = line[: len(line) - len(line.lstrip())]
                lines[i] = f'{indent}"{pkg_name}>={locked_versions[pkg_name]}",'
                _ = pyproject_path.write_text("\n".join(lines) + "\n")
    print("Updated pyproject.toml with locked versions")


if __name__ == "__main__":
    main()  #!/usr/bin/env python3
    # Read locked versions from uv.lock
    # Read pyproject.toml
    # Update each dependency line
    # Match lines like:    "requests>=2.28.0",
    # Extract package name (before any operator)
