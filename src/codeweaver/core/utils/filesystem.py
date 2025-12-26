# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Git and filesystem-related utility functions."""

# ruff: noqa: S603
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess

from functools import cache
from pathlib import Path
from typing import cast

from codeweaver.core.types.aliases import DevToolName, DevToolNameT, LlmToolName, LlmToolNameT
from codeweaver.core.types.sentinel import MISSING, Missing


@cache
def get_user_config_dir(*, base_only: bool = False) -> Path:
    """Get the user configuration directory based on the operating system."""
    import platform

    if (system := platform.system()) == "Windows":
        config_dir = Path(os.getenv("APPDATA", Path("~\\AppData\\Roaming").expanduser()))
    elif system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support"
    else:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_dir if base_only else config_dir / "codeweaver"


def try_git_rev_parse() -> Path | None:
    """Attempt to use git to get the root directory of the current git repository."""
    git = shutil.which("git")
    if not git:
        return None
    with contextlib.suppress(subprocess.CalledProcessError):
        # Try superproject first (for submodules)
        output = subprocess.run(
            [git, "rev-parse", "--show-superproject-working-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if output.returncode == 0 and output.stdout.strip():
            return Path(output.stdout.strip())

        # Fall back to toplevel
        output = subprocess.run(
            [git, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
        if output.returncode == 0 and output.stdout.strip():
            return Path(output.stdout.strip())
    return None


def is_git_dir(directory: Path | None = None) -> bool:
    """Is the given directory version-controlled with git?"""
    directory = directory or Path.cwd()
    git_path = directory / ".git"
    return git_path.is_dir() or git_path.is_file() if git_path.exists() else False


def _root_path_checks_out(path: Path) -> bool:
    """Check if the given path is a valid git repository root."""
    return path.is_dir() and is_git_dir(path)


def _walk_up_to_git_root(path: Path | None = None) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    path = path or Path.cwd()
    if path.is_file():
        path = path.parent
    while path != path.parent:
        if is_git_dir(path):
            return path
        path = path.parent
    msg = (
        "No .git directory found in the path hierarchy.\n"
        "CodeWeaver requires a git repository to determine the project root."
    )
    raise FileNotFoundError(msg)


def get_project_path(root_path: Path | None = None) -> Path:
    """Get the root directory of the project."""
    if (
        root_path is None
        and (git_root := try_git_rev_parse())
        and (git_root.is_dir() and is_git_dir(git_root))
    ):
        return git_root
    if isinstance(root_path, Path) and root_path.is_dir() and is_git_dir(root_path):
        return root_path

    if (env_path := os.environ.get("CODEWEAVER_PROJECT_PATH")) and (
        path := Path(env_path)
    ).is_dir():
        return path

    return _walk_up_to_git_root(root_path)


def set_relative_path(path: Path | str | None, base_path: Path | None = None) -> Path | None:
    """Validates a path and makes it relative to the project root if the path is absolute."""
    if path is None:
        return None
    path_obj = Path(path).resolve()
    if not path_obj.is_absolute():
        return path_obj

    try:
        base_path = (base_path or get_project_path()).resolve()
    except FileNotFoundError:
        return path_obj

    try:
        return path_obj.relative_to(base_path)
    except ValueError:
        return path_obj


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    # Verify git command works
    output = subprocess.run([git, "--version"], capture_output=True, check=False)
    return output.returncode == 0


@cache
def normalize_ext(ext: str) -> str:
    """Normalize a file extension to a standard format. Cached because of hot/repetitive use."""
    return ext.lower().strip() if ext.startswith(".") else f".{ext.lower().strip()}"


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return (
        "codeweaver" in str(path).lower()
        or "code-weaver" in str(path).lower()
        or bool((rev_dir := try_git_rev_parse()) and "codeweaver" in rev_dir.name.lower())
    )


def _get_git_dir(directory: Path) -> Path | Missing:
    """Get the .git directory of a git repository."""
    if not is_git_dir(directory):
        try:
            directory = get_project_path()
        except FileNotFoundError:
            return MISSING
        if not is_git_dir(directory):
            return MISSING
    return directory


def get_git_revision(directory: Path) -> str | Missing:
    """Get the SHA-1 of the HEAD of a git repository."""
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        if not git:
            return MISSING
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                [git, "rev-parse", "--short", "HEAD"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
            return output.stdout.strip()
    return MISSING


def _get_branch_from_origin(directory: Path) -> str | Missing:
    """Get the branch name from the origin remote."""
    git = shutil.which("git")
    if not git:
        return MISSING
    try:
        output = subprocess.run(
            [git, "rev-parse", "--abbrev-ref", "origin/HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        branch: str = output.stdout.strip().removeprefix("origin/")
    except Exception:
        return MISSING
    else:
        return branch or MISSING


def get_git_branch(directory: Path) -> str:
    """Get the current branch name of a git repository."""
    if not is_git_dir(directory):
        try:
            directory = get_project_path(directory)
        except Exception:
            return "detached"

    if not shutil.which("git"):
        return "detached"

    git = shutil.which("git")
    try:
        output = subprocess.run(
            [cast(str, git), "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        branch = output.stdout.strip()

        if not branch or branch == "HEAD":
            origin_branch = _get_branch_from_origin(directory)
            if origin_branch not in ("HEAD", MISSING):
                return cast(str, origin_branch)
            return "detached"
    except Exception:
        return "detached"
    else:
        return branch


# ===========================================================================
# *                            Tooling Path Constants
# ===========================================================================

_tooling_dirs: set[Path] | None = None


COMMON_TOOLING_PATHS: tuple[tuple[DevToolNameT, tuple[Path, ...]], ...] = (
    (DevToolName("ast-grep"), (Path("sgconfig.yml"),)),
    (DevToolName("cargo"), (Path("Cargo.toml"), Path("Cargo.lock"), Path(".cargo"))),
    (
        DevToolName("docker"),
        (
            Path("Dockerfile"),
            Path("docker-compose.yml"),
            Path("docker-compose.yaml"),
            Path("docker"),
        ),
    ),
    (
        DevToolName("devcontainer"),
        (
            Path(".devcontainer"),
            Path(".devcontainer/devcontainer.json"),
            Path(".devcontainer/devcontainer.local.json"),
        ),
    ),
    (DevToolName("bazel"), (Path("WORKSPACE"), Path("BUILD.bazel"), Path("BUILD"))),
    (
        DevToolName("cmake"),
        (
            Path("CMakeLists.txt"),
            Path("CMakeCache.txt"),
            Path("cmake-build-debug"),
            Path("CMakeFiles"),
        ),
    ),
    (DevToolName("biome"), (Path("biome.json"), Path("biome.config.js"))),
    (
        DevToolName("bun"),
        (Path("bun.lockb"), Path("bunfig.toml"), Path("bunfig.json"), Path("bun.lock")),
    ),
    (DevToolName("changesets"), (Path(".changeset"),)),
    (DevToolName("composer"), (Path("composer.json"), Path("composer.lock"))),
    (DevToolName("esbuild"), (Path("esbuild.config.js"), Path("esbuild.config.ts"))),
    (
        DevToolName("gradle"),
        (
            Path("build.gradle"),
            Path("build.gradle.kts"),
            Path("gradlew"),
            Path("gradlew.bat"),
            Path("gradle"),
            Path("settings.gradle"),
            Path("settings.gradle.kts"),
        ),
    ),
    (DevToolName("deno"), (Path("deno.json"), Path("deno.jsonc"), Path("deno.lock"))),
    (DevToolName("hardhat"), (Path("hardhat.config.js"), Path("hardhat.config.ts"))),
    (DevToolName("hk"), (Path("hk.pkl"),)),
    (DevToolName("husky"), (Path(".husky"), Path(".husky/pre-commit"), Path(".husky/pre-push"))),
    (DevToolName("intellij"), (Path(".idea"), Path(".idea/misc.xml"), Path(".idea/modules.xml"))),
    (DevToolName("just"), (Path("Justfile"), Path("justfile"))),
    (DevToolName("lerna"), (Path("lerna.json"),)),
    (
        DevToolName("maven"),
        (Path("pom.xml"), Path("settings.xml"), Path(".mvn"), Path("mvnw"), Path("mvnw.cmd")),
    ),
    (DevToolName("mise"), (Path("mise.toml"),)),
    (DevToolName("moon"), (Path("moon.yml"), Path("moon.yaml"), Path(".moon"))),
    (DevToolName("nextjs"), (Path("next.config.js"), Path("next.config.ts"))),
    (DevToolName("npm"), (Path("package-lock.json"), Path(".npmrc"))),
    (DevToolName("nuxt"), (Path("nuxt.config.js"), Path("nuxt.config.ts"))),
    (DevToolName("nx"), (Path("nx.json"), Path("workspace.json"), Path("angular.json"))),
    (DevToolName("pnpm"), (Path("pnpm-lock.yaml"), Path("pnpm-workspace.yaml"))),
    (DevToolName("poetry"), (Path("poetry.lock"),)),
    (DevToolName("pre-commit"), (Path(".pre-commit-config.yaml"), Path(".pre-commit-config.yml"))),
    (
        DevToolName("proto"),
        (Path("proto.toml"), Path("proto.pkl"), Path("prototools.toml"), Path("prototools.pkl")),
    ),
    (DevToolName("rollbar"), (Path("rollbar.config.js"), Path("rollbar.config.ts"))),
    (DevToolName("rollup"), (Path("rollup.config.js"), Path("rollup.config.ts"))),
    (DevToolName("ruff"), (Path("ruff.toml"), Path(".ruff.toml"))),
    (DevToolName("rush"), (Path("rush.json"),)),
    (
        DevToolName("sbt"),
        (Path("build.sbt"), Path("project/build.properties"), Path("project/plugins.sbt")),
    ),
    (DevToolName("skaffold"), (Path("skaffold.yaml"), Path("skaffold.yml"))),
    (
        DevToolName("stylelint"),
        (
            Path(".stylelintrc"),
            Path(".stylelintrc.json"),
            Path(".stylelintrc.yaml"),
            Path(".stylelintrc.yml"),
        ),
    ),
    (DevToolName("tailwind"), (Path("tailwind.config.js"), Path("tailwind.config.ts"))),
    (DevToolName("typos"), (Path("_typos.toml"), Path(".typos.toml"), Path("typos.toml"))),
    (DevToolName("turborepo"), (Path("turbo.json"),)),
    (DevToolName("uv"), (Path("uv.toml"), Path("uv.lock"))),
    (DevToolName("vite"), (Path("vite.config.js"), Path("vite.config.ts"))),
    (DevToolName("vitest"), (Path("vitest.config.js"), Path("vitest.config.ts"))),
    (
        DevToolName("vscode"),
        (Path(".vscode"), Path(".vscode/settings.json"), Path(".vscode/launch.json")),
    ),
    (DevToolName("webpack"), (Path("webpack.config.js"), Path("webpack.config.ts"))),
    (DevToolName("xtask"), (Path("xtask"), Path("xtask/src/main.rs"))),
    (DevToolName("yarn"), (Path("yarn.lock"), Path(".yarn"), Path(".yarnrc"), Path(".yarnrc.yml"))),
)

COMMON_LLM_TOOLING_PATHS: tuple[tuple[LlmToolNameT, tuple[Path, ...]], ...] = (
    (LlmToolName("agents"), (Path("AGENTS.md"),)),
    (LlmToolName("codex"), (Path(".codex"),)),
    (
        LlmToolName("claude"),
        (Path("CLAUDE.md"), Path(".claude"), Path("claudedocs"), Path(".claude/commands")),
    ),
    (
        LlmToolName("codeweaver"),
        (
            Path("codeweaver.local.toml"),
            Path("codeweaver.local.yaml"),
            Path("codeweaver.local.json"),
            Path(".codeweaver"),
        ),
    ),
    (LlmToolName("continue"), (Path(".continue"),)),
    (LlmToolName("copilot"), (Path(".github/chatmodes"), Path(".github/prompts"))),
    (LlmToolName("cursor"), (Path(".cursor"), Path(".cursor/config.yml"))),
    (
        LlmToolName("mcp"),
        (Path(".mcp.json"), Path("mcp.json"), Path(".roo/mcp.json"), Path(".vscode/mcp.json")),
    ),
    (LlmToolName("roo"), (Path(".roo"), Path(".roomodes"), Path(".roo/commands"))),
    (LlmToolName("serena"), (Path(".serena"), Path(".serena/project.yml"))),
    (
        LlmToolName("specify"),
        (
            Path(".specify"),
            Path(".specify/memory"),
            Path(".specify/scripts/bash"),
            Path(".specify/templates"),
        ),
    ),
)


def get_tooling_dirs() -> set[Path]:
    """Get common tooling directories within the project root."""

    def _is_hidden_dir(path: Path) -> bool:
        return bool(str(path).startswith(".") and "." not in str(path)[1:])

    global _tooling_dirs
    if _tooling_dirs is None:
        tooling_paths = {
            path for tool in COMMON_TOOLING_PATHS for path in tool[1] if _is_hidden_dir(path)
        } | {path for tool in COMMON_LLM_TOOLING_PATHS for path in tool[1] if _is_hidden_dir(path)}
        _tooling_dirs = tooling_paths
    return _tooling_dirs


def backup_file_path(*, project_name: str | None = None, project_path: Path | None = None) -> Path:
    """Get the default backup file path for the vector store."""
    from codeweaver.core.utils.general import generate_collection_name

    return (
        get_user_config_dir()
        / ".vectors"
        / "backup"
        / f"{generate_collection_name(is_backup=True, project_name=project_name, project_path=project_path)}.json"
    )


__all__ = (
    "COMMON_LLM_TOOLING_PATHS",
    "COMMON_TOOLING_PATHS",
    "backup_file_path",
    "get_git_branch",
    "get_git_revision",
    "get_project_path",
    "get_tooling_dirs",
    "get_user_config_dir",
    "has_git",
    "in_codeweaver_clone",
    "is_git_dir",
    "normalize_ext",
    "set_relative_path",
    "try_git_rev_parse",
)
