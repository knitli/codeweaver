# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Optimization decision logic for Fastembed and SentenceTransformers providers."""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess

from collections.abc import Callable
from importlib import metadata
from importlib.util import find_spec
from types import ModuleType
from typing import Literal, NotRequired, Required, TypedDict

from codeweaver.core import LazyImport, has_package, lazy_import


# ===========================================================================
# *               Fastembed GPU/CPU Decision Logic                     *
# ===========================================================================
"""This section conducts a series of checks to determine if Fastembed-GPU can be used.

It is only called if the user requests a Fastembed provider.

There is also a separate set of optimizations that can be used with Fastembed and SentenceTransformers. These aren't yet fully implemented.
"""

logger = logging.getLogger(__name__)


def _which_fastembed_dist() -> str | None:
    """Check if fastembed or fastembed-gpu is installed, and return which one."""
    return next(
        (dist for dist in ("fastembed-gpu", "fastembed") if find_spec(dist) is not None), None
    )


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
            ort.preload_dlls(cuda=True, cudnn=True, msvc=platform.system() == "Windows")
        except Exception:
            logger.warning("ONNX Runtime CUDA not usable despite being installed.", exc_info=True)
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
                f"It looks like you requested GPU usage for Fastembed, but cuda is not available. Make sure to provide your device_ids in your CodeWeaver settings if you have GPUs available, installed the `codeweaver[fastembed-gpu]` extra, and followed Fastembed's [gpu setup instructions](https://qdrant.github.io/fastembed/examples/FastEmbed_GPU/). Our checks returned this message: {decision[2]}",
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


class AvailableOptimizations(TypedDict, total=False):
    """Available optimizations in the current environment."""

    onnx: bool
    onnx_gpu: bool
    open_vino: bool
    intel_cpu: bool
    simd_available: bool
    simd_exts: tuple[SimdExtensions, ...]


class OptimizationDecisions(TypedDict, total=False):
    """Decided optimizations to use for model inference."""

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
    cpuinfo: LazyImport[ModuleType] = lazy_import("cpuinfo")
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
    sparse_opts = OptimizationDecisions(  # ty: ignore[missing-typed-dict-key]
        **(
            sparse_opts
            | {
                "use_small_batch_for_sparse": sparse_opts["backend"] == "onnx_gpu",
                "backend": sparse_opts["backend"],
                "dtype": sparse_opts["dtype"],
            }
        )
    )
    return (
        dense_opts
        if model_kind == "dense"
        else sparse_opts
        if model_kind == "sparse"
        else OptimizationDecisions(**(dense_opts | sparse_opts))  # ty: ignore[missing-typed-dict-key]
    )


__all__ = (
    "AvailableOptimizations",
    "OptimizationDecisions",
    "decide_fastembed_runtime",
    "get_optimizations",
)
