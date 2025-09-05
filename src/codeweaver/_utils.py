# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Helper functions for CodeWeaver utilities.
"""

import contextlib
import logging
import os
import shutil
import subprocess

from collections.abc import Callable
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Literal

from codeweaver._common import Sentinel


logger = logging.getLogger(__name__)


class Missing(Sentinel):
    pass


MISSING: Missing = Missing("MISSING", "Sentinel<MISSING>", __name__)


# Even Python's latest and greatest typing (as of 3.12+) can't properly express this.
# You can't combine TypeVarTuple with ParamSpec, or use concatenate to
# express combining some args and some kwargs, particularly from the right.
def rpartial[**P, R](func: Callable[P, R], *args: object, **kwargs: object) -> Callable[P, R]:
    """Return a new function that behaves like func called with the given arguments.

    `rpartial` is like `functools.partial`, but it appends the given arguments to the right.
    It's useful for functions that take a variable number of arguments, especially when you want to fix keywords and modifier-type arguments, which tend to come at the end of the argument list.
    You can supply any number of contiguous positional and keyword arguments from the right.

    Examples:
        ```python
        def example_function(a: int, b: int, c: int) -> int:
            return a + b + c


        # Create a new function with the last argument fixed
        # this is equivalent to: lambda a, b: example_function(a, b, 3)
        new_function = rpartial(example_function, 3)

        # Call the new function with the remaining arguments
        result = new_function(1, 2)
        print(result)  # Output: 6
        ```

        ```python
        # with keyword arguments

        # we'll fix a positional argument and a keyword argument
        def more_complex_example(x: int, y: int, z: int = 0, flag: bool = False) -> int:
            if flag:
                return x + y + z
            return x * y * z


        new_function = rpartial(
            more_complex_example, z=5, flag=True
        )  # could also do `rpartial(more_complex_example, 5, flag=True)` if z was positional-only
        result = new_function(2, 3)  # returns 10 (2 + 3 + 5)
        ```
    """

    def partial_right(*fargs: P.args, **fkwargs: P.kwargs) -> R:
        """Return a new partial object which when called will behave like func called with the
        given arguments.
        """
        return func(*(fargs + args), **{**fkwargs, **kwargs})  # pyright: ignore[reportCallIssue]

    return partial_right


def is_git_repo(directory: Path | None = None) -> bool:
    """Is the given directory version-controlled with git?"""
    directory = directory or Path.cwd()
    if (git_dir := (directory / ".git")) and git_dir.exists():
        return git_dir.is_dir()
    return False


def walk_down_to_git_root(path: Path | None = None) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    path = path or Path.cwd()
    if path.is_file():
        path = path.parent
    while path != path.parent:
        if is_git_repo(path):
            return path
        path = path.parent
    raise FileNotFoundError("No .git directory found in the path hierarchy.")


def get_project_root() -> Path:
    """Get the root directory of the project."""
    from codeweaver.main import get_app_settings

    settings = get_app_settings()
    return settings.project_root or walk_down_to_git_root()


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    with contextlib.suppress(subprocess.CalledProcessError):
        subprocess.run(["--version"], executable=git, stderr=subprocess.STDOUT)  # pyright: ignore[reportUnusedCallResult]  # noqa: S607
        return True
    return False


def get_git_revision(directory: Path) -> str | Missing:  # pyright: ignore[reportInvalidTypeForm, reportUnknownParameterType]
    """Get the SHA-1 of the HEAD of a git repository."""
    if not is_git_repo(directory):
        with contextlib.suppress(FileNotFoundError):
            directory = walk_down_to_git_root(directory)
        if not directory or not is_git_repo(directory):
            return MISSING
    if has_git():
        git = shutil.which("git")
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(["rev-parse", "--short", "HEAD"], executable=git, cwd=directory)  # noqa: S607
            return output.stdout.decode("utf-8").strip()
    return MISSING


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return "codeweaver" in str(path).lower() or "code-weaver" in str(path).lower()


def estimate_tokens(text: str | bytes, encoder: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text."""
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


@cache
def normalize_ext(ext: str) -> str:
    """Normalize a file extension to a standard format."""
    return ext.lower().strip() if ext.startswith(".") else f".{ext.lower().strip()}"


def _check_env_var(var_name: str) -> str | None:
    """Check if an environment variable is set and return its value, or None if not set."""
    return os.getenv(var_name)


def get_possible_env_vars() -> tuple[tuple[str, str], ...] | None:
    """Get a tuple of any resolved environment variables for all providers and provider environment variables. If none are set, returns None."""
    from codeweaver.provider import Provider

    env_vars = sorted({item[1][0] for item in Provider.all_envs()})
    found_vars = tuple(
        (var, value) for var in env_vars if (value := _check_env_var(var)) is not None
    )
    return found_vars or None


# ===========================================================================
# *                    Fastembed GPU/CPU Decision Logic                     *
# ===========================================================================
"""This section conducts a series of checks to determine if Fastembed-GPU can be used.

It is only called if the user requests a Fastembed provider.
"""


def _which_fastembed_dist() -> str | None:
    """Check if fastembed or fastembed-gpu is installed, and return which one."""
    for dist_name in ("fastembed-gpu", "fastembed"):
        try:
            _ = metadata.version(dist_name)
        except metadata.PackageNotFoundError:
            continue
        else:
            return dist_name
    return None


def _nvidia_smi_device_ids() -> list[int]:
    """Attempts to detect available NVIDIA GPU device IDs using nvidia-smi."""
    if not (nvidia_smi := shutil.which("nvidia-smi")):
        return []
    with contextlib.suppress(Exception):
        out = subprocess.check_output(  # noqa: S603
            [nvidia_smi, "--query-gpu=index", "--format=csv,noheader,nounits"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=2.0,
        )
        return [int(line.strip()) for line in out.splitlines() if line.strip().isdigit()]
    return []


def _onnx_cuda_available() -> bool:
    try:
        gpu_runtime = metadata.version("onnxruntime-gpu")
    except Exception:
        # If ORT isn't importable yet, fall back to a light GPU presence check
        return False
    else:
        return bool(gpu_runtime)


def _cuda_usable() -> bool:
    return _onnx_cuda_available() or bool(_nvidia_smi_device_ids())


def _decide_fastembed_runtime(
    *, explicit_cuda: bool | None = None, explicit_device_ids: list[int] | None = None
) -> tuple[bool, list[int] | None, str]:
    """Decide the runtime for fastembed based on environment and user input."""
    if not (dist := _which_fastembed_dist()) or dist == "fastembed":
        return False, None, "fastembed not found or CPU-only fastembed installed; using CPU."
    device_ids = (
        explicit_device_ids if explicit_device_ids is not None else _nvidia_smi_device_ids()
    )
    cuda_usable = _cuda_usable()
    if _onnx_cuda_available():
        try:
            import platform

            import onnxruntime as ort

            logger.info("ONNX Runtime GPU package detected. Attempting to preload DLLs...")
            ort.preload_dlls(cuda=True, cudnn=True, msvc=platform.system() == "Windows")  # pyright: ignore[reportUnknownMemberType]
        except Exception:
            logger.exception("ONNX Runtime CUDA not usable despite being installed.")
            cuda_usable = False

    # Honor explicit user choice but guard against impossible states
    if explicit_cuda is not None:
        if explicit_cuda and not cuda_usable:
            return False, None, "Requested CUDA but ONNX CUDA not usable; forcing CPU."
        return explicit_cuda, (device_ids or None), "Explicit runtime selection respected."

    if cuda_usable:
        return True, (device_ids or None), "Using GPU: fastembed-gpu present and ONNX CUDA usable."
    return False, None, "fastembed-gpu installed but ONNX CUDA not usable; falling back to CPU."


def decide_fastembed_runtime(
    *, explicit_cuda: bool | None = None, explicit_device_ids: list[int] | None = None
) -> Literal["cpu", "gpu"] | tuple[Literal["gpu"], list[int]]:
    """Decide the runtime for fastembed based on environment and user input."""
    decision = _decide_fastembed_runtime(
        explicit_cuda=explicit_cuda, explicit_device_ids=explicit_device_ids
    )
    match decision:
        case True, device_ids, _ if isinstance(device_ids, list) and len(device_ids) > 0:
            return "gpu", device_ids
        case True, _, _:
            if found_device_ids := _nvidia_smi_device_ids():
                return "gpu", found_device_ids
            from warnings import warn

            warn(
                "It looks like you have fastembed-gpu installed and CUDA is usable, but no GPUs were detected. We'll give this a shot, but it may fail. If it does, please provide your device_ids in your CodeWeaver settings.",
                stacklevel=2,
            )
            return "gpu"
        case False, _, _ if explicit_device_ids or explicit_cuda:
            from warnings import warn

            warn(
                f"It looks like you requested GPU usage for Fastembed, but cuda is not available. Make sure to provide your device_ids in your CodeWeaver settings if you have GPUs available, installed the `codeweaver-mcp[provider-fastembed-gpu]` extra, and followed Fastembed's [gpu setup instructions](https://qdrant.github.io/fastembed/examples/FastEmbed_GPU/). Our checks returned this message: {decision[2]}",
                stacklevel=2,
            )
            return "cpu"
        case _:
            return "cpu"
