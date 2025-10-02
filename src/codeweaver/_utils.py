# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Helper functions for CodeWeaver utilities.
"""

import contextlib
import inspect
import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata

from collections.abc import Callable, Hashable, Iterable
from functools import cache
from importlib import metadata, util
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypedDict, cast

from pydantic import UUID7, BaseModel, TypeAdapter
from typing_extensions import TypeIs

from codeweaver._common import LiteralStringT, Sentinel


if TYPE_CHECKING:
    from codeweaver._common import AbstractNodeName


logger = logging.getLogger(__name__)


class Missing(Sentinel):
    pass


MISSING: Missing = Missing("MISSING", "Sentinel<MISSING>", __name__)

if sys.version_info < (3, 14):
    from uuid_extensions import uuid7 as uuid7_gen
else:
    from uuid import uuid7 as uuid7_gen


def uuid7() -> UUID7:
    """Generate a new UUID7."""
    return cast(
        UUID7, uuid7_gen()
    )  # it's always UUID7 and not str | int | bytes because we don't take kwargs


def dict_set_to_tuple(
    d: dict[str, set[str]]
    | dict[LiteralStringT | AbstractNodeName, set[LiteralStringT | AbstractNodeName]],
) -> dict[str, tuple[str, ...]] | dict[Hashable, tuple[LiteralStringT | AbstractNodeName, ...]]:
    """Convert all sets in a dictionary to tuples."""
    return dict(
        sorted({k: tuple(sorted(v)) for k, v in d.items()}.items()),  # type: ignore
        key=lambda item: str(item[0]),  # type: ignore
    )


@cache
def lazy_importer(module_name: str) -> ModuleType:
    """Return a lazy importer for the given module."""
    spec = util.find_spec(module_name)
    if spec is None or not spec.loader:
        raise ImportError(f"Module {module_name} not found")
    loader = util.LazyLoader(spec.loader)
    spec.loader = loader
    module = util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


def is_pydantic_basemodel(model: Any) -> TypeIs[type[BaseModel] | BaseModel]:
    """Check if a model is a Pydantic BaseModel."""
    return isinstance(model, type) and (
        issubclass(model, BaseModel) or isinstance(model, BaseModel)
    )


def is_class(obj: Any) -> TypeIs[type[Any]]:
    """Check if an object is a class."""
    return inspect.isclass(obj)


def is_typeadapter(adapter: Any) -> TypeIs[TypeAdapter[Any] | type[TypeAdapter[Any]]]:
    """Check if an object is a Pydantic TypeAdapter."""
    return hasattr(adapter, "pydantic_complete") and hasattr(adapter, "validate_python")


def estimate_tokens(text: str | bytes, encoder: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text."""
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


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


def has_package(package_name: str) -> bool:
    """Check if a package is installed."""
    try:
        if util.find_spec(package_name):
            return True
    except metadata.PackageNotFoundError:
        return False
    return False


# Even Python's latest and greatest typing (as of 3.12+), Python can't properly express this function.
# You can't combine `TypeVarTuple` with `ParamSpec`, or use `Concatenate` to
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
        return func(*(fargs + args), **dict(fkwargs | kwargs))  # pyright: ignore[reportCallIssue]

    return partial_right


def ensure_iterable[T](value: Iterable[T] | T) -> Iterable[T]:
    """Ensure the value is iterable.

    Note: If you pass `ensure_iterable` a `Mapping` (like a `dict`), it will yield the keys of the mapping, not its items/values.
    """
    if isinstance(value, Iterable) and not isinstance(value, (bytes | bytearray | str)):
        yield from cast(Iterable[T], value)
    else:
        yield cast(T, value)


# ===========================================================================
# *                            Git/Path Utilities
# ===========================================================================


def try_git_rev_parse() -> Path | None:
    """Attempt to use git to get the root directory of the current git repository."""
    if not has_git():
        return None
    git = shutil.which("git")
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            ["rev-parse", "--show-superproject-working-tree", "--show-toplevel", "|", "head", "-1"],  # noqa: S607
            executable=git,
            capture_output=True,
            text=True,
        )
        return Path(output.stdout.strip())
    return None


def is_git_dir(directory: Path | None = None) -> bool:
    """Is the given directory version-controlled with git?"""
    directory = directory or Path.cwd()
    if (git_dir := (directory / ".git")) and git_dir.exists():
        return git_dir.is_dir()
    return False


def _walk_down_to_git_root(path: Path | None = None) -> Path:
    """Walk up the directory tree until a .git directory is found."""
    path = path or Path.cwd()
    if path.is_file():
        path = path.parent
    while path != path.parent:
        if is_git_dir(path):
            return path
        path = path.parent
    raise FileNotFoundError("No .git directory found in the path hierarchy.")


def _root_path_checks_out(root_path: Path) -> bool:
    """Check if the root path is valid."""
    return root_path.exists() and root_path.is_dir() and is_git_dir(root_path)


def get_project_root(root_path: Path | None = None) -> Path:
    """Get the root directory of the project."""
    return (
        root_path
        if isinstance(root_path, Path) and _root_path_checks_out(root_path)
        else _walk_down_to_git_root(root_path)
    )  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]


def set_relative_path(path: Path | str | None) -> Path | None:
    """Validates a path and makes it relative to the project root if the path is absolute."""
    if path is None:
        return None
    path_obj = Path(path)
    if not path_obj.is_absolute():
        return path_obj

    base_path = get_project_root()
    return path_obj.relative_to(base_path)


def has_git() -> bool:
    """Check if git is installed and available."""
    git = shutil.which("git")
    if not git:
        return False
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            ["--version"],  # noqa: S607
            executable=git,
            stderr=subprocess.STDOUT,
            capture_output=True,
        )
        return output.returncode == 0
    return False


def _get_git_dir(directory: Path) -> Path | Missing:
    """Get the .git directory of a git repository."""
    if not is_git_dir(directory):
        with contextlib.suppress(FileNotFoundError):
            directory = get_project_root() or Path.cwd()
        if not directory or not is_git_dir(directory):
            return MISSING
    return directory


def get_git_revision(directory: Path) -> str | Missing:
    """Get the SHA-1 of the HEAD of a git repository.

    This is a precursor for future functionality. We'd like to be able to associate indexes and other artifacts with a specific git commit. Because there's nothing worse than an Agent working from a totally different context than the one you expect.
    """
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                ["rev-parse", "--short", "HEAD"],  # noqa: S607
                executable=git,
                cwd=directory,
                capture_output=True,
                text=True,
            )
            return output.stdout.strip()
    return MISSING


def _get_branch_from_origin(directory: Path) -> str | Missing:
    """Get the branch name from the origin remote."""
    git = shutil.which("git")
    if not git:
        return MISSING
    with contextlib.suppress(subprocess.CalledProcessError):
        output = subprocess.run(
            ["rev-parse", "--abbrev-ref", "origin/HEAD"],  # noqa: S607
            executable=git,
            cwd=directory,
            capture_output=True,
            text=True,
        )
        branch = output.stdout.strip().removeprefix("origin/")
        if branch and "/" in branch:
            return branch.split("/", 1)[1]
        if branch:
            return branch
    return MISSING


def get_git_branch(directory: Path) -> str | Missing:
    """Get the current branch name of a git repository."""
    git_dir = _get_git_dir(directory)
    if git_dir is MISSING:
        return MISSING
    directory = cast(Path, git_dir)
    if has_git():
        git = shutil.which("git")
        with contextlib.suppress(subprocess.CalledProcessError):
            output = subprocess.run(
                ["rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
                executable=git,
                cwd=directory,
                capture_output=True,
                text=True,
            )
            if branch := output.stdout.strip():
                return branch if branch != "HEAD" else _get_branch_from_origin(directory)
            if branch is MISSING:
                return "detached"
    return MISSING


def in_codeweaver_clone(path: Path) -> bool:
    """Check if the current repo is CodeWeaver."""
    return (
        "codeweaver" in str(path).lower()
        or "code-weaver" in str(path).lower()
        or bool((rev_dir := try_git_rev_parse()) and "codeweaver" in rev_dir.name.lower())
    )  # pyright: ignore[reportOptionalMemberAccess, reportUnknownMemberType]


@cache
def normalize_ext(ext: str) -> str:
    """Normalize a file extension to a standard format. Cached because of hot/repetitive use."""
    return ext.lower().strip() if ext.startswith(".") else f".{ext.lower().strip()}"


# src/codeweaver/_utils.py
def is_debug() -> bool:
    """Check if the application is running in debug mode."""
    env = os.getenv("CODEWEAVER_DEBUG")

    explicit_true = (env in ("1", "true", "True", "TRUE")) if env is not None else False
    explicit_false = os.getenv("CODEWEAVER_DEBUG", "1") in ("false", "0", "", "False", "FALSE")

    has_debugger = (
        hasattr(sys, "gettrace") and callable(sys.gettrace) and (sys.gettrace() is not None)
    )
    repo_heuristic = in_codeweaver_clone(Path.cwd()) and not explicit_false

    return explicit_true or has_debugger or repo_heuristic


# ===========================================================================
# *               Text Normalization/Safety Utilities
# ===========================================================================
# by default, we do basic NFKC normalization and strip known invisible/control chars
# this is to avoid issues with fullwidth chars, zero-width spaces, etc.
# We plan to add more advanced santization options in the future, which users can opt into.
# TODO: Add Rebuff.ai integration, and/or other advanced sanitization options. Probably as middleware.

NORMALIZE_FORM = "NFKC"

CONTROL_CHARS = [chr(i) for i in range(0x20) if i not in (9, 10, 13)]
INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", *CONTROL_CHARS)

INVISIBLE_PATTERN = re.compile("|".join(re.escape(c) for c in INVISIBLE_CHARS))

POSSIBLE_PROMPT_INJECTS = (
    r"[<\(\|=:]\s*system\s*[>\)\|=:]",
    r"[<\(\|=:]\s*instruction\s*[>\)\|=:]",
    r"\b(?:ignore|disregard|forget|cancel|override|void)\b(?:\s+(?:previous|above|all|prior|earlier|former|before|other|last|everything|this)){0,2}\s*(?:instruct(?:ions?)?|direction(?:s?)?|directive(?:s?)?|command(?:s?)?|request(?:s?)?|order(?:s?)?|message(?:s?)?|prompt(?:s?)?)\b",
)

INJECT_PATTERN = re.compile("|".join(POSSIBLE_PROMPT_INJECTS), re.IGNORECASE)


def sanitize_unicode(
    text: str | bytes | bytearray,
    normalize_form: Literal["NFC", "NFKC", "NFD", "NFKD"] = NORMALIZE_FORM,
) -> str:
    """Sanitize unicode text by normalizing and removing invisible/control characters.

    TODO: Need to add a mechanism to override or customize the injection patterns.
    """
    if isinstance(text, bytes | bytearray):
        text = text.decode("utf-8", errors="ignore")
    if not text.strip():
        return ""

    text = unicodedata.normalize(normalize_form, text)
    filtered = INVISIBLE_PATTERN.sub("", text)

    matches = list(INJECT_PATTERN.finditer(filtered))
    for match in reversed(matches):
        start, end = match.span()
        logger.warning("Possible prompt injection detected and neutralized: %s", match.group(0))
        replacement = "[[ POSSIBLE PROMPT INJECTION REMOVED ]]"
        filtered = filtered[:start] + replacement + filtered[end:]

    return filtered.strip()


# ===========================================================================
# *                    Fastembed GPU/CPU Decision Logic                     *
# ===========================================================================
"""This section conducts a series of checks to determine if Fastembed-GPU can be used.

It is only called if the user requests a Fastembed provider.

There is also a separate set of optimizations that can be used with Fastembed and SentenceTransformers. These aren't yet fully implemented.
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


# ===========================================================================
#  todo                             TODO
# These optimizations aren't yet tied into the provider executions
# We need to:
#    - integrate and combine them with user settings/choices
#    - ensure they are integrated with `Fastembed` and `SentenceTransformers` (Fastembed will always use onnx, however)
#    - account for any potential conflicts or limitations in the chosen execution environment
# ===========================================================================

type SimdExtensions = Literal["arm64", "avx2", "avx512", "avx512_vnni"]


class AvailableOptimizations(TypedDict):
    onnx: bool
    onnx_gpu: bool
    open_vino: bool
    intel_cpu: bool
    simd_available: bool
    simd_exts: tuple[SimdExtensions, ...]


class OptimizationDecisions(TypedDict, total=False):
    backend: Required[Literal["onnx", "onnx_gpu", "open_vino", "torch"]]
    dtype: Required[Literal["float16", "bfloat16", "qint8"]]
    onnx_optset: NotRequired[Literal[3, 4] | None]
    simd_ext: NotRequired[Literal["arm64", "avx2", "avx512", "avx512_vnni"] | None]
    use_small_chunks_for_dense: NotRequired[bool | None]
    chunk_func: NotRequired[Callable[[int], int]]
    """A callable that takes the model's max_seq_length and returns the max chunk size to use."""
    use_small_batch_for_sparse: NotRequired[bool | None]


def _set_dense_optimization(opts: AvailableOptimizations) -> OptimizationDecisions:
    """Set optimization decisions for dense models."""
    match opts:
        case {"onnx_gpu": True, **_other}:
            return OptimizationDecisions(
                backend="onnx_gpu",
                dtype="bfloat16",
                onnx_optset=4,
                use_small_chunks_for_dense=True,
                chunk_func=lambda max_seq_length: min(512, max_seq_length),
            )
        case {"intel_cpu": True, "simd_available": True, "onnx": True, **_other} if (
            len(opts["simd_exts"]) > 0
        ):
            return OptimizationDecisions(
                backend="onnx",
                dtype="float16",
                onnx_optset=3,
                simd_ext=opts["simd_exts"][0],
                use_small_chunks_for_dense=False,
            )
        case {"intel_cpu": True, "open_vino": True, **_other}:
            return OptimizationDecisions(
                backend="open_vino", dtype="qint8", use_small_chunks_for_dense=False
            )
        case {"onnx": True, **_other}:
            return OptimizationDecisions(
                backend="onnx", dtype="float16", onnx_optset=3, use_small_chunks_for_dense=False
            )
        case {"open_vino": True, **_other}:
            return OptimizationDecisions(
                backend="open_vino", dtype="qint8", use_small_chunks_for_dense=False
            )
        case _:
            return OptimizationDecisions(
                backend="torch", dtype="float16", use_small_chunks_for_dense=False
            )


def _get_general_optimizations_available() -> AvailableOptimizations:
    """Assess the current environment for available optimizations."""
    optimizations = AvailableOptimizations(
        onnx=False,
        onnx_gpu=False,
        open_vino=False,
        intel_cpu=False,
        simd_available=False,
        simd_exts=(),
    )
    with contextlib.suppress(ImportError):
        optimizations = AvailableOptimizations(**optimizations, **(_set_cpu_optimizations()))
    return {
        **optimizations,
        "onnx_gpu": _onnx_cuda_available(),
        "onnx": has_package("onnxruntime"),
        "open_vino": has_package("optimum-intel"),
    }


def _set_cpu_optimizations() -> dict[
    Literal["intel_cpu", "simd_available", "simd_exts"], bool | tuple[str, ...]
]:
    cpuinfo = lazy_importer("cpuinfo")
    info = cpuinfo.get_cpu_info()
    simd_exts = tuple(
        flag for flag in ("avx512_vnni", "avx512", "avx2", "arm64") if flag in info.get("flags", [])
    )
    return {
        "intel_cpu": "intel" in info.get("vendor_id_raw", "").lower()
        or "intel" in info.get("brand_raw", "").lower(),
        "simd_available": len(simd_exts) > 0,
        "simd_exts": simd_exts,
    }


def get_optimizations(model_kind: Literal["dense", "sparse", "both"]) -> OptimizationDecisions:
    """Determine the optimization strategy based on input parameters."""
    opts = _get_general_optimizations_available()
    dense_opts = _set_dense_optimization(opts)
    sparse_opts = dense_opts
    for key in ("use_small_chunks_for_dense", "chunk_func"):
        _ = sparse_opts.pop(key, None)
    sparse_opts = OptimizationDecisions(
        **(sparse_opts | {"use_small_batch_for_sparse": sparse_opts["backend"] == "onnx_gpu"})  # pyright: ignore[reportArgumentType]
    )
    return (
        dense_opts
        if model_kind == "dense"
        else sparse_opts
        if model_kind == "sparse"
        else OptimizationDecisions(**(dense_opts | sparse_opts))
    )


__all__ = (
    "MISSING",
    "AvailableOptimizations",
    "Missing",
    "OptimizationDecisions",
    "SimdExtensions",
    "decide_fastembed_runtime",
    "ensure_iterable",
    "estimate_tokens",
    "get_git_revision",
    "get_optimizations",
    "get_possible_env_vars",
    "get_project_root",
    "get_project_root",
    "has_git",
    "has_package",
    "in_codeweaver_clone",
    "is_class",
    "is_debug",
    "is_git_dir",
    "is_pydantic_basemodel",
    "is_typeadapter",
    "lazy_importer",
    "normalize_ext",
    "rpartial",
    "set_relative_path",
    "uuid7",
)
