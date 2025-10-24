#!/usr/bin/env python3
"""Update pyproject.toml dependency constraints to match uv.lock versions."""

import re
import tomllib

from pathlib import Path


VERSION_PATTERN = re.compile(
    r'(?P<key>[\w\-]+)\s=\s\[(?P<dependencies>"(?P<name>[\w\-]+)(?P<operator>[<>=!]+)(?P<version>[\d\.]+)",?\s?)+\]|(?P<indent>[\s\t]+)"(?P<single_name>[\w\-]+)(?P<single_operator>[<>=!]+)(?P<single_version>[\d\.]+)",?'
)


def main() -> None:
    """Update pyproject.toml dependencies to match uv.lock versions."""
    lock_data = tomllib.loads(Path("uv.lock").read_text())
    packages = lock_data["package"]
    locked_versions: dict[str, str] = {
        pkg["name"]: pkg["version"] for pkg in packages if "name" in pkg and "version" in pkg
    }
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if match := VERSION_PATTERN.search(line):
            if match.group("name"):
                pkg_name = match.group("name")
                if pkg_name in locked_versions:
                    new_version = locked_versions[pkg_name]
                    operator = match.group("operator")
                    lines[i] = re.sub(
                        rf'("{pkg_name}{operator})([\d\.]+)"', f'"\1{new_version}"', line
                    )
            elif match.group("single_name"):
                pkg_name = match.group("single_name")
                if pkg_name in locked_versions:
                    new_version = locked_versions[pkg_name]
                    operator = match.group("single_operator")
                    lines[i] = re.sub(
                        rf'("{pkg_name}{operator})([\d\.]+)"', f'"\1{new_version}"', line
                    )
    print("Updated pyproject.toml with locked versions")


if __name__ == "__main__":
    main()  #!/usr/bin/env python3
    # Read locked versions from uv.lock
    # Read pyproject.toml
    # Update each dependency line
    # Match lines like:    "requests>=2.28.0",
    # Extract package name (before any operator)
