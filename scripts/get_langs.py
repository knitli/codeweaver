#!/usr/bin/env -S uv run

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# ///script
# requires-python = ">=3.11"
# dependencies = ["httpx", "cyclopts", "pydantic", "rich"]
# ///
# sourcery skip: avoid-global-variables, lambdas-should-be-short, no-complex-if-expressions

"""Fetches tree-sitter grammars from their repos."""

from __future__ import annotations

import asyncio
import os
import sys

from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal, LiteralString, TypeGuard, cast

import httpx

from cyclopts import App, Parameter
from cyclopts.config import Env
from pydantic import BaseModel, ConfigDict, Field, PastDatetime
from rich.console import Console


SAVE_DIR = Path.cwd() / "grammars"


class GrammarRetrievalError(Exception):
    """Raised when grammar retrieval fails."""


__version__ = "0.1.0"

console = Console(markup=True, emoji=True)

AppCtor = cast(Any, App)
Param = cast(Any, Parameter)
app = AppCtor(
    name="GramFetch",
    help="Fetches tree-sitter grammars from their repos and saves them locally. 🌳 🙊",
    console=console,
    default_parameter=Param(
        negative=()
    ),  # disable the negative version of the parameter (e.g. --no-verbose) by default
    version=__version__,
    config=Env(prefix="GF_"),
    help_format="rich",
)

GH_USERNAME = os.environ.get("GH_USERNAME", None)
GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", None))

MULTIPLIER = (
    1 if GH_TOKEN else 3
)  # increase wait time if no token is provided to avoid hitting rate limits

SAVE_DIR = Path(__file__).parent.parent / "grammars"


@cache
def get_request_headers() -> dict[str, str]:
    """Returns a GitHub client using the token from environment variables."""
    default_headers = {
        "Accept": "application/vnd.github+json",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "Codeweaver-MCP",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if not GH_TOKEN:
        # If no token, we can use the public API but may hit rate limits.
        console.print(
            "[orange]No GitHub token provided,[/orange] [yellow]using public API with limited access.[/yellow]"
        )
        console.print(
            "Set [cyan]GH_USERNAME[/cyan] and [cyan]GH_TOKEN[/cyan] or [cyan]GITHUB_TOKEN[/cyan] environment variable for full access."
        )
        console.print("You can also pass them as command line arguments.")
        console.print("Usage: uv run scripts/fetch_grammars.py <GH_USERNAME> [GH_TOKEN]")
        return default_headers
    return {**default_headers, "Authorization": f"Bearer {GH_TOKEN}"}


@dataclass(frozen=True, kw_only=True, order=True)
class TreeSitterGrammarResult:
    """Represents a Tree-sitter grammar file in a Github repo."""

    git_path: str
    type_: Literal["blob", "tree", "commit"]
    language: AstGrepSupportedLanguage
    repo: TreeSitterRepo
    url: str
    sha: str
    date: PastDatetime
    last_fetched: PastDatetime | None

    def save_path(self, save_dir: Path = SAVE_DIR) -> Path:
        """The filename for saving the grammar locally."""
        extension = self.git_path.split(".")[-1]
        if "node-types" in self.git_path:
            return save_dir / f"{self.language.value}-node-types.{extension}"
        return save_dir / f"{self.language.value}-grammar.{extension}"

    async def fetch_node_types(self) -> str | None:
        """Fetches the node types file for the grammar, if it exists."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, headers=get_request_headers())
                _ = response.raise_for_status()
                response_data = response.json()
                return response_data.get("content", "")
        except httpx.HTTPError as e:
            console.print(f"[red]Failed to fetch node types for {self.language.value}:[/red] {e}")
            return None

    async def get_grammar_file(self) -> str:
        """Returns the grammar file content."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, headers=get_request_headers())
                _ = response.raise_for_status()
                response_data = response.json()
                content = response_data.get("content", "")

                # Decode base64 content if it exists
                if content:
                    import base64

                    try:
                        decoded_content = base64.b64decode(content).decode("utf-8")
                        console.print(
                            f"[cyan]DEBUG:[/cyan] Decoded {len(content)} chars to {len(decoded_content)} chars for {self.language.value}"
                        )
                    except Exception as decode_error:
                        console.print(
                            f"[yellow]Warning:[/yellow] Failed to decode base64 content for {self.language.value}: {decode_error}"
                        )
                        return content
                    else:
                        return decoded_content
                return content
        except httpx.HTTPStatusError as e:
            raise GrammarRetrievalError(
                f"Failed to retrieve grammar file from {self.url}: {e}"
            ) from e

    async def save(self, content: str | bytes | None = None, save_dir: Path = SAVE_DIR) -> None:
        """Saves the grammar file to the specified directory."""
        save_path = self.save_path(save_dir)
        if not save_path.parent.exists():
            save_path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            content = await self.get_grammar_file()
        if not content:
            raise GrammarRetrievalError(f"No content retrieved for {self.language} grammar.")
        if save_path.exists():
            save_path.unlink()
        if isinstance(content, str):
            content = content.encode("utf-8")
        _ = save_path.write_bytes(content)
        console.print(f"Saved grammar for {self.language} to {save_path}")


@dataclass(kw_only=True, order=True)
class TreeSitterRepo:
    """Represents a Tree-sitter repository."""

    language: AstGrepSupportedLanguage
    repo: str
    branch: str

    _sha: str | None = None
    _tree: dict[str, Any] | None = None
    _grammar: TreeSitterGrammarResult | None = None
    _commit_date: datetime | None = None
    _branch_obj: dict[str, Any] | None = None
    _node_types: bool = False
    _only_node_types: bool = False

    @property
    def base_url(self) -> str:
        """Returns the web URL of the repository."""
        return f"https://github.com/{self.repo}"

    @property
    def clone_url(self) -> str:
        """Returns the URL of the repository."""
        return f"{self.base_url}.git"

    @property
    def branch_url(self) -> str:
        """Returns the URL of the repository branch."""
        return f"{self.base_url}/tree/{self.branch}"

    async def commit_date(self) -> datetime:
        """Returns the date of the latest commit hash."""
        if not self._commit_date:
            branch_info = await self.branch_obj()
            serialized_date = branch_info["commit"]["commit"]["author"]["date"]
            try:
                # Normalize 'Z' suffix to a valid offset for fromisoformat
                date_norm = serialized_date.replace("Z", "+00:00")
                self._commit_date = datetime.fromisoformat(date_norm)
            except Exception:
                try:
                    from email.utils import parsedate_to_datetime

                    self._commit_date = parsedate_to_datetime(serialized_date)
                except Exception:
                    console.print(
                        f"[yellow]Warning:[/yellow] Unable to parse commit date '{serialized_date}', defaulting to now"
                    )
                    self._commit_date = datetime.now(UTC)
            console.print(f"raw commit date: {serialized_date}")
            console.print(
                f"Fetched commit date for {self.language} from {self.repo} branch {self.branch}: {self._commit_date}"
            )
        return cast(datetime, self._commit_date)

    @property
    def api_url(self) -> str:
        """Returns the API URL of the repository."""
        return f"https://api.github.com/repos/{self.repo}"

    async def branch_obj(self) -> dict[str, Any]:
        """Fetches the latest branch name for the repository."""
        if not self._branch_obj:
            url = f"{self.api_url}/branches/{self.branch}"
            headers = get_request_headers()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers)
                    _ = response.raise_for_status()
                    console.print(
                        f"Fetched branch info for {self.language} from {self.repo} branch {self.branch}."
                    )
                    self._branch_obj = response.json()
            except httpx.HTTPStatusError as e:
                raise GrammarRetrievalError(
                    f"Failed to retrieve branch info for {self.repo} branch {self.branch}: {e}"
                ) from e
        return self._branch_obj or {}

    async def sha(self) -> str:
        """Fetches the latest commit SHA for the repository branch."""
        if not self._sha:
            branch_info = await self.branch_obj()
            self._sha = branch_info["commit"]["sha"]
        return self._sha or ""

    async def tree(self) -> dict[str, Any]:
        """Fetches the tree structure of the repository branch."""
        if not self._tree:
            sha = await self.sha()
            console.print(
                f"Fetching tree for {self.language} from {self.repo} branch {self.branch} at commit {sha}..."
            )
            url = f"{self.api_url}/git/trees/{sha}?recursive=1"
            headers = get_request_headers()
            try:
                # Use httpx to fetch the tree structure
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers)
                    _ = response.raise_for_status()
                    console.print(
                        f"Fetched tree for {self.language} from {self.repo} branch {self.branch}."
                    )
                    self._tree = response.json()
            except httpx.HTTPStatusError as e:
                raise GrammarRetrievalError(
                    f"Failed to retrieve tree for {self.repo} branch {self.branch}: {e}"
                ) from e
        return self._tree or {}

    async def grammar(self) -> TreeSitterGrammarResult:
        """Finds the Tree-sitter grammar file in the repository."""
        if not self._grammar:
            console.print(
                f"Fetching grammar for {self.language} from {self.repo} branch {self.branch}..."
            )
            tree = await self.tree()
            if "tree" not in tree:
                raise FileNotFoundError(f"No tree found in {self.repo} branch {self.branch}.")
            grammar_types = ("grammar.js", "grammar.json", "grammar.ts")
            if self._only_node_types:
                grammar_types = ("node-types.json",)
            elif self._node_types:
                grammar_types = ("grammar.js", "grammar.json", "grammar.ts", "node-types.json")
            console.print(
                f"[cyan]DEBUG:[/cyan] Looking for grammar files in tree with {len(tree.get('tree', []))} items"
            )
            if found_item := next(
                (
                    item
                    for item in tree["tree"]
                    if any(item["path"].endswith(t) for t in grammar_types)
                ),
                None,
            ):
                console.print(f"[cyan]DEBUG:[/cyan] Found grammar file: {found_item['path']}")
                # DEBUG: Add commit date for the grammar result
                commit_date = await self.commit_date()
                console.print(
                    f"[cyan]DEBUG:[/cyan] Creating grammar result with commit date: {commit_date}"
                )
                self._grammar = TreeSitterGrammarResult(
                    git_path=found_item["path"],
                    type_=found_item["type"],
                    language=self.language,
                    repo=self,
                    url=f"{self.api_url}/contents/{found_item['path']}?ref={self.branch}",
                    sha=found_item["sha"],
                    date=commit_date,
                    last_fetched=datetime.now(UTC),
                )
        if not self._grammar:
            raise FileNotFoundError(f"No grammar file found in {self.repo} branch {self.branch}.")
        return self._grammar

    @staticmethod
    def from_tuple(
        repo_tuple: TreeSitterRepo | tuple[AstGrepSupportedLanguage, str, str],
        *,
        node_types: bool = False,
        only_node_types: bool = False,
    ) -> TreeSitterRepo:
        """Creates a TreeSitterRepo from a tuple or returns the input if already a TreeSitterRepo."""
        if isinstance(repo_tuple, TreeSitterRepo):
            if not (node_types or only_node_types):
                return repo_tuple
            return TreeSitterRepo(
                language=repo_tuple.language,
                repo=repo_tuple.repo,
                branch=repo_tuple.branch,
                _node_types=node_types,
                _only_node_types=only_node_types,
            )
        if (
            isinstance(repo_tuple, tuple)
            and len(repo_tuple) == 3
            and isinstance(repo_tuple[0], AstGrepSupportedLanguage)
            and isinstance(repo_tuple[1], str)
            and isinstance(repo_tuple[2], str)
        ):
            return TreeSitterRepo(
                language=repo_tuple[0],
                repo=repo_tuple[1],
                branch=repo_tuple[2],
                _node_types=node_types,
                _only_node_types=only_node_types,
            )
        raise ValueError("Invalid repository tuple format.")


class AstGrepSupportedLanguage(Enum):
    """Supported languages for AST Grep."""

    BASH = "bash"
    C_LANG = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    CSS = "css"
    ELIXIR = "elixir"
    GO = "go"
    HASKELL = "haskell"
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSON = "json"
    KOTLIN = "kotlin"
    LUA = "lua"
    NIX = "nix"
    PHP = "php"
    PHP_SPARSE = "php_sparse"
    """PHP has two grammars: standard and what we're calling "sparse".

    The standard grammar supports PHP with other languages embedded (e.g. HTML) where the opening tag is `<?php` but allows for text before/after php tags. What we call `php_sparse` (`php_only` in the grammar's repo) *only* supports pure PHP code (doesn't even require the php tag)."""
    PYTHON = "python"
    RUBY = "ruby"
    RUST = "rust"
    SCALA = "scala"
    SOLIDITY = "solidity"
    SWIFT = "swift"
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    YAML = "yaml"

    # Special case for all languages
    _ALL = "all"

    @property
    def resolved_languages(self) -> tuple[AstGrepSupportedLanguage, ...]:
        """Returns the resolved language name."""
        return tuple(type(self).members())

    @property
    def repo_tuple(self) -> TreeSitterRepo | tuple[TreeSitterRepo, ...]:
        """Returns the repository tuple for the language."""
        tree_sitter_name = (
            f"tree-sitter-{self.value}"
            if self != AstGrepSupportedLanguage.CSHARP
            else "tree-sitter-c-sharp"
        )
        match self:
            case AstGrepSupportedLanguage._ALL:
                return tuple(
                    repo
                    for lang in AstGrepSupportedLanguage.members()
                    for repo in (
                        (lang.repo_tuple,)
                        if isinstance(lang.repo_tuple, TreeSitterRepo)
                        else lang.repo_tuple
                    )
                )
            case (
                AstGrepSupportedLanguage.BASH
                | AstGrepSupportedLanguage.C_LANG
                | AstGrepSupportedLanguage.CPP
                | AstGrepSupportedLanguage.CSHARP
                | AstGrepSupportedLanguage.CSS
                | AstGrepSupportedLanguage.GO
                | AstGrepSupportedLanguage.HASKELL
                | AstGrepSupportedLanguage.HTML
                | AstGrepSupportedLanguage.JAVA
                | AstGrepSupportedLanguage.JAVASCRIPT
                | AstGrepSupportedLanguage.JSON
                | AstGrepSupportedLanguage.PHP
                | AstGrepSupportedLanguage.PYTHON
                | AstGrepSupportedLanguage.RUBY
                | AstGrepSupportedLanguage.RUST
                | AstGrepSupportedLanguage.SCALA
                | AstGrepSupportedLanguage.TYPESCRIPT
            ):
                return TreeSitterRepo(
                    language=self, repo=f"tree-sitter/{tree_sitter_name}", branch="master"
                )
            case AstGrepSupportedLanguage.PHP_SPARSE:
                return TreeSitterRepo(
                    language=self, repo="tree-sitter/tree-sitter-php", branch="master"
                )
            case AstGrepSupportedLanguage.TSX:
                return TreeSitterRepo(
                    language=self, repo="tree-sitter/tree-sitter-typescript", branch="master"
                )
            case AstGrepSupportedLanguage.ELIXIR:
                return TreeSitterRepo(
                    language=self, repo=f"elixir-lang/{tree_sitter_name}", branch="main"
                )
            case (
                AstGrepSupportedLanguage.KOTLIN
                | AstGrepSupportedLanguage.LUA
                | AstGrepSupportedLanguage.YAML
            ):
                return TreeSitterRepo(
                    language=self,
                    repo=f"tree-sitter-grammars/{tree_sitter_name}",
                    branch="main" if self == AstGrepSupportedLanguage.LUA else "master",
                )
            case AstGrepSupportedLanguage.NIX:
                return TreeSitterRepo(
                    language=self, repo=f"nix-community/{tree_sitter_name}", branch="master"
                )
            case AstGrepSupportedLanguage.SOLIDITY:
                return TreeSitterRepo(
                    language=self, repo=f"JoranHonig/{tree_sitter_name}", branch="master"
                )
            case AstGrepSupportedLanguage.SWIFT:
                return TreeSitterRepo(
                    language=self, repo=f"alex-pinkus/{tree_sitter_name}", branch="main"
                )
            case _:
                raise ValueError(f"{self.value} is not a valid AstGrepSupportedLanguage.")

    @property
    def keep_dirs(self) -> LiteralString:
        """Directories to keep when saving the grammar."""
        if self == AstGrepSupportedLanguage.PHP_SPARSE:
            return "php_only/src"
        if self in (
            AstGrepSupportedLanguage.TYPESCRIPT,
            AstGrepSupportedLanguage.TSX,
            AstGrepSupportedLanguage.PHP,
        ):
            return f"{self!s}/src"  # type: ignore
        return "src"

    def __str__(self) -> str:
        """Returns the string representation of the language."""
        if self == AstGrepSupportedLanguage._ALL:
            import json

            langs = [str(lang) for lang in self.resolved_languages]
            return json.dumps(langs)
        return self.value

    @classmethod
    def from_str(cls, value: str) -> AstGrepSupportedLanguage:  # noqa: C901
        """Returns the enum member from a string."""
        try:
            normalized_value = value.strip().replace("-", "_").lower()
            match normalized_value:
                case "all":
                    return cls._ALL
                # handle common aliases
                case "php_only" | "php_sparse" | "just_php":
                    return cls.PHP_SPARSE
                case "c_sharp" | "c#":
                    return cls.CSHARP
                case "yml":
                    return cls.YAML
                case "c++":
                    return cls.CPP
                case "c_lang":
                    return cls.C_LANG
                case "ts":
                    return cls.TYPESCRIPT
                case "js":
                    return cls.JAVASCRIPT
                case "htm":
                    return cls.HTML
                # everything else
                case _:
                    return cls.__members__[normalized_value.upper()]
        except KeyError as e:
            # __members__ raises KeyError on missing item
            raise ValueError(f"{value} is not a valid AstGrepSupportedLanguage.") from e

    @classmethod
    def languages(cls) -> Generator[str, None, None]:
        """Returns names of all supported languages (excluding _ALL)."""
        # Use members() so _ALL is excluded
        yield from (m.name for m in cls.members())

    @classmethod
    def members(cls) -> Generator[AstGrepSupportedLanguage, None, None]:
        """Returns enum members excluding _ALL."""
        yield from (member for member in cls.__members__.values() if member is not cls._ALL)

    @classmethod
    def repos(cls, **kwargs: Any) -> Generator[TreeSitterRepo, None, None]:
        """Yields TreeSitterRepo items only (never tuples)."""
        for lang in cls.members():
            rt = lang.repo_tuple
            yield TreeSitterRepo.from_tuple(rt, **kwargs)


def is_grammar_result(result: Any) -> TypeGuard[TreeSitterGrammarResult]:
    """Checks if the result is not an exception."""
    return isinstance(result, TreeSitterGrammarResult)


async def _fetch_grammars(
    repos: tuple[TreeSitterRepo, ...], _tries: int = 0
) -> tuple[TreeSitterGrammarResult, ...]:
    """Fetches the grammars from the repositories asynchronously."""
    tasks = []
    async with asyncio.TaskGroup() as tg:
        console.print(f"[cyan]DEBUG:[/cyan] Fetching grammars for {len(repos)} repositories...")
        for repo in repos:
            console.print(f"[cyan]DEBUG:[/cyan] Adding task for {repo.language.value} grammar...")
            tasks.append(tg.create_task(repo.grammar()))
    return tuple(task.result() for task in tasks)


def _evaluate_results(
    results: Iterable[TreeSitterGrammarResult | Exception | None],
) -> tuple[tuple[TreeSitterGrammarResult, ...], tuple[int, ...]]:
    """Evaluates the results of the grammar fetch."""
    successful_results = []
    failed = []
    console.print("[cyan]DEBUG:[/cyan] Evaluating results...")
    console.print(f"[cyan]DEBUG:[/cyan] Results type: {type(results)}")
    for i, result in enumerate(results):
        if is_grammar_result(result):
            successful_results.append(result)
        else:
            failed.append(i)
    return tuple(successful_results), tuple(failed)


async def _gather(repos: tuple[TreeSitterRepo, ...]) -> tuple[TreeSitterGrammarResult, ...]:
    """Fetches the list of Tree-sitter grammars from the GitHub API."""
    successful_results: list[TreeSitterGrammarResult] = []
    failed_repos = list(repos)

    for tries in range(4):  # 0,1,2,3 (max 3 retries)
        if not failed_repos:
            break

        results = await _fetch_grammars(tuple(failed_repos), tries)
        new_successful_results, failed_indexes = _evaluate_results(results)
        # Add new successes
        successful_results.extend(new_successful_results)
        # Prepare next round of failures
        failed_repos = [failed_repos[i] for i in failed_indexes]
        if not failed_repos:
            console.print("[bold green]Successfully retrieved all grammars[/bold green] 🎉")
            break
        if tries < 3:
            await asyncio.sleep((tries + 1) * 2 * MULTIPLIER)
    return tuple(successful_results)


async def gather_grammars(repos: tuple[TreeSitterRepo, ...]) -> Grammars | None:
    """Fetches the list of Tree-sitter grammars from the GitHub API."""
    if not repos:
        console.print("No repositories provided. Please provide a list of supported languages.")
        return None
    console.print(f"Fetching grammars for {len(repos)} repositories...")
    grammars = None
    try:
        # Start the gathering process
        grammars = await _gather(repos)

    except httpx.HTTPStatusError:
        console.print_exception()
    else:
        console.print("[bold green]Successfully fetched grammars![/bold green] 🎉")
    if grammars:
        try:
            grammar_obj = Grammars.from_grammars(grammars)
        except Exception:
            console.print_exception()
            return None
        else:
            console.print(
                f"[green]Successfully created Grammars object with {len(grammar_obj.grammars)} grammars![/green]"
            )
            return grammar_obj
    return None


class Grammars(BaseModel):
    """Model for json record of grammars."""

    model_config = ConfigDict(
        extra="forbid",  # forbid extra fields
        frozen=True,  # make the model immutable
        str_strip_whitespace=True,  # strip whitespace from strings
        validate_assignment=True,  # validate assignment of fields
        cache_strings="all",  # cache the model for performance
        # spellchecker:off
        ser_json_inf_nan="strings",  # serialize inf/nan as strings
        # spellchecker:on
    )
    languages: Annotated[
        tuple[AstGrepSupportedLanguage, ...],
        (Field(description="List of supported languages for AST Grep.", frozen=True, repr=False)),
    ]
    grammars: Annotated[
        tuple[TreeSitterGrammarResult, ...],
        Field(default_factory=tuple, description="List of Tree-sitter grammar results."),
    ]

    def all_repos(self) -> tuple[TreeSitterRepo, ...]:
        """Returns a tuple of all repositories for the supported languages."""
        return tuple(grammar.repo for grammar in self.grammars)

    @classmethod
    def from_grammars(cls, grammars: tuple[TreeSitterGrammarResult, ...]) -> Grammars:
        """Creates a Grammars instance from a tuple of TreeSitterGrammarResult."""
        return cls.model_validate({
            "languages": tuple({g.language for g in grammars}),
            "grammars": grammars,
        })

    @classmethod
    def from_merge(cls, *grammars: Grammars) -> Grammars:
        """Merges multiple Grammars instances into one."""
        if not grammars:
            return cls(languages=(), grammars=())
        merged_languages = set()
        merged_grammars = []
        for grammar in grammars:
            merged_languages.update(grammar.languages)
            merged_grammars.extend(grammar.grammars)
        return cls.model_validate({
            "languages": tuple(merged_languages),
            "grammars": tuple(merged_grammars),
        })

    def serialize(self, save_dir: Path = SAVE_DIR) -> None:
        """Saves the grammars to a JSON file."""
        if not save_dir.exists():
            save_dir.mkdir(parents=True, exist_ok=True)
        record_path = save_dir / ".fetch_record.json"
        new_record = self
        if record_path.exists():
            if old_record := new_grammar_from_json(record_path):
                console.print(
                    f"[yellow]Found existing grammar fetch record at {record_path}, merging with new data...[/yellow]"
                )
                new_record = type(self).from_merge(old_record, self)
            self = new_record
            record_path.unlink()
        _ = record_path.write_text(
            self.model_dump_json(indent=2, warnings="warn"), encoding="utf-8"
        )
        console.print(f"Saved grammar fetch record to {record_path}")


def new_grammar_from_json(file_path: Path) -> Grammars | None:
    """Creates a Grammars object from a JSON file."""
    if not file_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        return None
    try:
        data = file_path.read_text(encoding="utf-8")
        model = Grammars.model_validate_json(data)
    except Exception as e:
        console.print(f"[red]Error reading JSON file:[/red] {e}")
        return None
    else:
        console.print(f"[green]Successfully created Grammars object from {file_path}![/green]")
        return model


@app.command(name="list", help="List all supported languages and their repositories.")
def list_grammars() -> None:
    """List all supported languages and their repositories."""
    console.print("Supported languages and their repositories:")
    repos: list[TreeSitterRepo] = []
    for lang in AstGrepSupportedLanguage.members():
        rt = lang.repo_tuple
        if isinstance(rt, TreeSitterRepo):
            repos.append(rt)
        else:
            # rt is tuple[TreeSitterRepo, ...]
            repos.extend(rt)
    for repo in repos:
        console.print(
            f"[bold]{repo.language.value}[/bold]: [link={repo.base_url}]{repo.repo}[/link] (branch: {repo.branch})"
        )
    console.print("\nUse `gramfetch fetch` to fetch grammars for these languages.")


def _raise_fetch_error(message: str, error: Exception | None = None) -> None:
    """Raises a GrammarRetrievalError with the given message."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    if error:
        # print_exception takes no positional args; print the provided exception explicitly
        console.print(f"[red]{error.__class__.__name__}:[/red] {error}")
    raise GrammarRetrievalError(message) from error


def normalize_grammars() -> None:
    """Normalizes the grammar files to JSON format using the tree-sitter CLI."""
    console.print("[cyan]DEBUG:[/cyan] Normalizing grammars to JSON format...")
    try:
        import shutil
        import subprocess

        if not (ts_cli := shutil.which("tree-sitter")):
            console.print(
                "[red]tree-sitter CLI not found. Please install it to normalize grammars.[/red]"
            )
            return
        _ = subprocess.run([ts_cli, "generate", "-b", str(SAVE_DIR)])  # noqa: S603
    except FileNotFoundError:
        console.print(
            "[red]tree-sitter CLI not found. Please install it to normalize grammars.[/red]"
        )


@app.command(name="fetch", help="Fetch grammars from GitHub.")
async def fetch_grammars(  # noqa: C901
    *,
    gh_username: Annotated[
        str | None,
        Param(name=["-u", "--username"], help="GitHub username to use for fetching grammars."),
    ] = None,
    gh_token: Annotated[
        str | None, Param(name=["-t", "--token"], help="GitHub token to use for fetching grammars.")
    ] = None,
    languages: Annotated[
        tuple[AstGrepSupportedLanguage, ...],
        Param(
            name=["-l", "--languages"],
            alias="langs",
            help="List of languages you want to fetch grammars for. Defaults to all supported languages.",
        ),
    ] = (AstGrepSupportedLanguage._ALL,),
    save_dir: Annotated[
        Path | None,
        Param(name=["-d", "--dir"], alias="dir", help="Directory to save the grammars to."),
    ] = SAVE_DIR,
    only_update: Annotated[
        bool,
        Param(
            name=["-u", "--update"],
            alias="update",
            help="Only download grammars that have been updated since the last fetch.",
            show_env_var=False,
        ),
    ] = False,
    normalize: Annotated[
        bool,
        Param(
            name=["-n", "--normalize"],
            help="Normalize the grammar files to json. Requires the tree-sitter CLI to be installed.",
        ),
    ] = True,
    node_types: Annotated[
        bool,
        Param(
            name=["--node-types"],
            help="Also fetch the node types file for each grammar, if it exists.",
        ),
    ] = False,
    only_node_types: Annotated[
        bool,
        Param(
            name=["--only-node-types"],
            help="Only fetch the node types file for each grammar, if it exists.",
        ),
    ] = False,
) -> None:  # sourcery skip: low-code-quality, no-long-functions
    """Fetch and save grammars from GitHub. Use `--languages` to specify languages, otherwise it will fetch all grammars."""
    console.print("Starting grammar fetch...🌳")

    # DEBUG: Log the received parameters
    console.print(f"[cyan]DEBUG:[/cyan] languages parameter type: {type(languages)}")
    console.print(f"[cyan]DEBUG:[/cyan] languages parameter value: {languages}")

    global GH_USERNAME, GH_TOKEN, MULTIPLIER, SAVE_DIR
    gh_username = gh_username or GH_USERNAME
    gh_token = gh_token or GH_TOKEN
    save_dir = save_dir or SAVE_DIR
    MULTIPLIER = (
        1 if gh_token else 3
    )  # increase wait time if no token is provided to avoid hitting rate limits
    # adjust globals based on provided arguments
    GH_USERNAME, GH_TOKEN, SAVE_DIR = gh_username, gh_token, save_dir
    all_ = len(languages) == 1 and languages[0] == AstGrepSupportedLanguage._ALL
    languages = languages[0].resolved_languages if all_ else languages

    if all_:
        repos_iter: Iterable[TreeSitterRepo] = AstGrepSupportedLanguage.repos(
            node_types=node_types, only_node_types=only_node_types
        )
    else:
        # Flatten repo tuples for the selected languages into a flat stream of TreeSitterRepo
        repos_iter: Iterable[TreeSitterRepo] = (
            TreeSitterRepo.from_tuple(rt, node_types=node_types, only_node_types=only_node_types)
            for lang in languages
            for rt in (
                lang.repo_tuple if isinstance(lang.repo_tuple, tuple) else (lang.repo_tuple,)
            )
        )
    if only_update:
        raise NotImplementedError(
            "This feature is disabled for now until we can debug it properly. Unless you want to debug it, then PRs are welcome! 😉"
        )
        # repos = await _handle_update_only(tuple(repos), save_dir)
    repos: tuple[TreeSitterRepo, ...] = tuple(repos_iter)  # ensure flat tuple for type checking
    console.print(f"Fetching [green]{len(repos)}[/green] grammars from GitHub...")
    grammars = None
    try:
        # gather grammars asynchronously
        grammars = await gather_grammars(repos)
        if not grammars:
            _raise_fetch_error(
                "No grammars were fetched. Please check the repositories and try again."
            )
        async with asyncio.TaskGroup() as tg:
            if not grammars:
                _raise_fetch_error("No grammars to save.")
            console.print(
                f"[cyan]DEBUG:[/cyan] Saving {len(cast(Grammars, grammars).grammars)} grammars to disk..."
            )
            if not grammars:
                _raise_fetch_error("No grammars to save.")
            for grammar in cast(Grammars, grammars).grammars:
                _ = tg.create_task(grammar.save(save_dir=save_dir))
        if normalize:
            normalize_grammars()
        try:
            grammars.serialize(save_dir=save_dir)  # pyright: ignore[reportOptionalMemberAccess]
        except Exception as e:
            console.print(f"[red]Failed to serialize grammars:[/red] {e}")
        if grammars:
            console.print(
                f"[green]Successfully fetched and saved {len(grammars.grammars)} grammars![/green]"
            )
    except GrammarRetrievalError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    console.print("Fetching grammars from GitHub...")
    try:
        # DEBUG: List all commands registered
        console.print(f"[cyan]DEBUG:[/cyan] Registered commands: {app.meta}")
        console.print("[cyan]DEBUG:[/cyan] About to call app()")
        app()
    except Exception as e:
        console.print(f"[red]DEBUG Error details:[/red] {e}")
        console.print_exception(word_wrap=True)
        sys.exit(1)
