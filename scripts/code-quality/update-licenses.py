#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = ["rignore", "cyclopts", "pydantic-core", "reuse"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: avoid-global-variables
# ruff: noqa: S603
"""Update licenses for files in the repository."""

import shutil
import subprocess
import sys

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import cache, partial
from pathlib import Path
from typing import Annotated, NamedTuple

import rignore

from cyclopts import App, Group, Parameter, validators
from pydantic_core._pydantic_core import from_json


BASE_PATH = Path(__file__).parent.parent.parent
__version__ = "0.1.4"
CONTRIBUTORS_GROUP = Group(
    "Contributors",
    default_parameter=Parameter(negative=()),
    help="Manage contributors for the license update.",
)
CONTRIBUTORS = Parameter(
    consume_multiple=True,
    help="Name and email of the contributor(s) to add. May be provided multiple times, or as a json list.",
    negative=(),
    json_list=True,
)
INTERACTIVE = Parameter(
    negative=(), help="Run the script in interactive mode, prompting for contributors."
)
app = App(
    name="Knitli License Updater",
    version=__version__,
    help="Update licenses for files in the repository using Reuse. Respects .gitignore.",
    help_format="rich",
    default_parameter=Parameter(negative=()),
    help_on_error=True,
)


def run_command(cmd: list[str], paths: list[Path]) -> None:
    """Run a command with the given paths."""
    if not paths:
        return
    cmds = [[*cmd, str(path)] for path in paths]
    with ThreadPoolExecutor() as executor:
        _ = executor.map(subprocess.run, cmds)


def years() -> str:
    """
    Get the range of years for the copyright notice.
    """
    if (year := datetime.now(UTC).year) and year != 2025:
        return f"2025-{year!s}"
    return "2025"


CODE_LICENSE = "MIT OR Apache-2.0"
NON_CODE_LICENSE = "MIT OR Apache-2.0"

BASE_CMD = [
    "reuse",
    "annotate",
    "--year",
    years(),
    "--copyright",
    "Knitli Inc. <knitli@knit.li>",
    "--merge-copyrights",
    "--fallback-dot-license",
    "--skip-existing",
]
REUSE_PATH = shutil.which("reuse")
if not REUSE_PATH:
    print("Reuse is not installed or not found in PATH. Please install it to use this script.")
    sys.exit(1)
CHECK_CMD = [REUSE_PATH, "lint", "-j"]
"""Outputs a JSON report of non-compliant files."""
NON_CODE_EXTS = {
    "login",
    "astro",
    "bash",
    "bash_logout",
    "bashrc",
    "browserlistrc",
    "conf",
    "config",
    "csh",
    "css",
    "cts",
    "fish",
    "gitattributes",
    "gitconfig",
    "gitmodules",
    "html",
    "htmx",
    "ini",
    "j2",
    "jinja",
    "jinja2",
    "json",
    "json5",
    "jsonc",
    "jsonl",
    "ksh",
    "md",
    "mdown",
    "mdtext",
    "mdtxt",
    "mdwn",
    "mdx",
    "mk",
    "mkd",
    "mts",
    "nix",
    "nu",
    "pkl",
    "profile",
    "quokka",
    "rs",
    "sass",
    "scss",
    "sh",
    "shellcheckrc",
    "sql",
    "sqlite",
    "stylelintrc",
    "tcsh",
    "toml",
    "txt",
    "yaml",
    "yml",
    "zlogin",
    "zlogout",
    "zprofile",
    "zsh",
    "zshenv",
    "zshrc",
}
"""Extensions (without leading dots) considered non-code files for license purposes. Some of these *are* code, but they're helpers/support files and we treat them as non-code for license purposes (more lenient license in most knitli libraries)."""
DEFAULT_CONTRIBUTORS = ["Adam Poulemanos <adam@knit.li>"]


class PathsForProcessing(NamedTuple):
    """Paths for processing."""

    code_paths: list[Path]
    non_code_paths: list[Path]

    @classmethod
    def from_paths(cls, paths: tuple[list[Path], list[Path]]) -> "PathsForProcessing":
        """Create an instance from a tuple of paths."""
        if len(paths) != 2:
            raise ValueError("Expected a tuple of two lists: (code_paths, non_code_paths)")
        return cls(code_paths=paths[0], non_code_paths=paths[1])

    def process_with_cmd(self, cmd: list[str]) -> None:
        """Run a command with the paths."""
        if not self.code_paths and (not self.non_code_paths):
            return
        cmds = []
        if self.code_paths:
            code_cmd = [*cmd, "-l", CODE_LICENSE]
            cmds.append((code_cmd, self.code_paths))
        if self.non_code_paths:
            non_code_cmd = [*cmd, "-l", NON_CODE_LICENSE]
            cmds.append((non_code_cmd, self.non_code_paths))
        for cmd, paths in cmds:
            run_command(cmd, paths)


def get_staged_files() -> list[Path]:
    """Get the list of staged files in the git repository."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            print("Git is not installed or not found in PATH.")
            sys.exit(1)
        result = subprocess.run(
            [git_path, "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout.strip())
        staged_files = result.stdout.strip().splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error getting staged files: {e}")
        return []
    else:
        return [BASE_PATH / file for file in staged_files]


@cache
def filter_path(paths: tuple[Path] | None = None, path: Path | None = None) -> bool:
    """Check if a path is in the provided list of paths."""
    if not path:
        return False
    if paths is None:
        return path.is_file() and (not path.is_symlink())
    return path in paths and path.is_file() and (not path.is_symlink())


def get_files_with_missing() -> list[Path] | None:
    """Get files with missing licenses."""
    try:
        result = subprocess.run(
            CHECK_CMD, capture_output=True, text=True
        )  # reuse returns a non-zero exit code if there are non-compliant files, so we don't use check=True
        output = from_json.loads(result.stdout.strip("%\n "))
        missing_files: list[str] = []
        if (non_compliant_report := output.get("non_compliant", {})) and (
            missing_files := non_compliant_report.get("missing_copyright_info", [])
            + non_compliant_report.get("missing_licensing_info", [])
        ):
            print(f"Found {len(missing_files)} files with missing licenses.")
    except subprocess.CalledProcessError as e:
        print(f"Error checking files: {e}")
        return None
    else:
        return sorted({BASE_PATH / file for file in missing_files})


def get_empty_lists() -> tuple[list, list]:
    """Get empty lists for code paths, and non-code paths."""
    return ([], [])


def sort_paths(paths: list[Path] | None = None, base_dir: Path = BASE_PATH) -> PathsForProcessing:
    """Sort paths by their string representation."""
    base_dir = base_dir or Path.cwd()
    code_paths, non_code_paths = get_empty_lists()
    entry_filter = partial(filter_path, tuple(paths) if paths else None)
    for p in rignore.walk(
        base_dir,
        ignore_hidden=False,
        read_git_ignore=True,
        read_ignore_files=True,
        same_file_system=True,
    ):
        path = Path(p)
        if not entry_filter(path):
            continue
        if path.suffix in NON_CODE_EXTS:
            non_code_paths.append(path)
        else:
            code_paths.append(path)
    return PathsForProcessing.from_paths((code_paths, non_code_paths))


def process_contributors(contributors: list[str]) -> list[str]:
    """Process contributors to ensure they are in the correct format."""
    processed = (item for contributor in contributors for item in ["--contributor", contributor])
    return list(processed)


@app.command(help="Use git user information to add license and contributors as a pre-commit hook.")
def pre_commit() -> bool:
    """Use git user information to add license and contributors as a pre-commit hook.

    The equivalent bash command is:
    ```bash
    git diff --name-only --cached | xargs -I {} reuse annotate -c "$(git config --get user.name) <$(git config --get user.email)>" "{}"
    ```
    """
    if not (git_path := shutil.which("git")):
        print("Git is not installed or not found in PATH.")
        return False
    try:
        if not (staged_files := get_staged_files()):
            print("No staged files found.")
            return True
        user_name_result = subprocess.run(
            [git_path, "config", "--get", "user.name"], capture_output=True, text=True, check=True
        )
        user_email_result = subprocess.run(
            [git_path, "config", "--get", "user.email"], capture_output=True, text=True, check=True
        )
        contributor = f"{user_name_result.stdout.strip()} <{user_email_result.stdout.strip()}>"
        cmds = [
            [REUSE_PATH, "annotate", "--contributor", contributor, str(BASE_PATH / file)]
            for file in staged_files
        ]
        with ThreadPoolExecutor() as executor:
            _ = executor.map(subprocess.run, cmds)
    except subprocess.CalledProcessError as e:
        print(f"Error processing pre-commit hook: {e}")
        return False
    return True


def get_contributor() -> str:
    """Get a contributor from the user."""
    # first check if we're in an interactive shell
    if not sys.stdin.isatty():
        pre_commit()
    # if we are, prompt for the contributor
    if contributor := input(
        "What's your name and email? (e.g. 'Adam Poulemanos <adam@knit.li>' (the default)): "
    ).strip():
        if all(char in contributor for char in ("<", ">", "@")):
            return contributor
        if "@" in contributor and "@" in contributor.split(" ")[-1]:
            parts = contributor.split(" ")
            return f"{''.join(parts[:-1])} <{parts[-1]}>"  # name email
        # assume they just provided a name; which is fine.
        return contributor
    raise ValueError(
        "No contributor provided. Please provide a name and email in the format 'Name <email>'."
    )


@app.command(
    help="Update all licenses in the repository. Will check every file in the repository and add license information if it's missing."
)
def update_all(
    *,
    contributors: Annotated[list[str], CONTRIBUTORS] = DEFAULT_CONTRIBUTORS,
    interactive: Annotated[bool, INTERACTIVE] = False,
) -> None:
    """Update all licenses in the repository."""
    if interactive:
        try:
            contributor = get_contributor()
            if contributor not in contributors:
                contributors.append(contributor)
        except ValueError as e:
            print(e)
            sys.exit(1)
    path_obj = sort_paths()
    BASE_CMD.extend(process_contributors(contributors))
    try:
        path_obj.process_with_cmd(BASE_CMD)
    except Exception as e:
        print(f"Error updating licenses: {e}")


@app.command(
    help="Add licenses for only those files missing license information in the repository. Will check every file in the repository and add license information if it's missing."
)
def missing(
    *,
    contributors: Annotated[list[str], CONTRIBUTORS] = DEFAULT_CONTRIBUTORS,
    interactive: Annotated[bool, INTERACTIVE] = False,
) -> None:
    """Add licenses for only those files missing license information in the repository."""
    missing_files = get_files_with_missing()
    if not missing_files:
        print("No files with missing licenses found.")
        return
    if interactive:
        try:
            contributor = get_contributor()
            if contributor not in contributors:
                contributors.append(contributor)
        except ValueError as e:
            print(e)
            sys.exit(1)
    path_obj = sort_paths(missing_files)
    BASE_CMD.extend(process_contributors(contributors))
    try:
        path_obj.process_with_cmd(BASE_CMD)
    except Exception as e:
        print(f"Error updating licenses: {e}")


@app.command(
    help="Update licenses for staged files in the repository. Will only check files that are staged for commit."
)
def staged(
    *,
    contributors: Annotated[list[str], CONTRIBUTORS] = DEFAULT_CONTRIBUTORS,
    interactive: Annotated[bool, INTERACTIVE] = False,
) -> None:
    """Update licenses for staged files in the repository."""
    if interactive:
        try:
            contributor = get_contributor()
            if contributor not in contributors:
                contributors.append(contributor)
        except ValueError as e:
            print(e)
            sys.exit(1)
    staged_files = get_staged_files()
    if not staged_files:
        print("No staged files found.")
        sys.exit(0)
    path_obj = sort_paths(staged_files)
    BASE_CMD.extend(process_contributors(contributors))
    try:
        path_obj.process_with_cmd(BASE_CMD)
    except Exception as e:
        print(f"Error updating licenses: {e}")


@app.command(
    help="Add licenses for specific files in the repository. Will only check the files provided. May be provided as a space separated list, or as a json list. If a file already has a license, it will be skipped."
)
def add(
    files: Annotated[
        list[Path],
        Parameter(
            validator=validators.Path(exists=True),
            required=True,
            consume_multiple=True,
            json_list=True,
        ),
    ],
    *,
    contributors: Annotated[list[str], CONTRIBUTORS] = DEFAULT_CONTRIBUTORS,
    interactive: Annotated[bool, INTERACTIVE] = False,
) -> None:
    """Update licenses for specific files in the repository."""
    if not files:
        print("No files provided.")
        sys.exit(0)
    if interactive:
        try:
            contributor = get_contributor()
            if contributor not in contributors:
                contributors.append(contributor)
        except ValueError as e:
            print(e)
            sys.exit(1)
    path_obj = sort_paths(files)
    BASE_CMD.extend(process_contributors(contributors))
    try:
        path_obj.process_with_cmd(BASE_CMD)
    except Exception as e:
        print(f"Error updating licenses: {e}")


def main() -> None:
    """Main function to update licenses."""
    app()


if __name__ == "__main__":
    main()
