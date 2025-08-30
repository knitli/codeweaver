#!/usr/bin/env -S uv run -s
# /// script
# requires-python = ">=3.12"
# dependencies = ["mteb", "black", "cyclopts", "pydantic>=2.11.0"]
# ///
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""A helper script for converting MTEB model metadata to CodeWeaver capabilities."""

from __future__ import annotations

import re

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict

import black

from cyclopts import App, Parameter
from mteb import AbsTask, ModelMeta, get_model_meta, get_model_metas
from pydantic import AnyUrl, PastDatetime

from codeweaver.embedding.capabilities.base import PartialCapabilities


VERSION_PATTERNS = (  # some special cases first
    re.compile(r"^Qwen/Qwen(?P<version>[3-9][.-]?\d{0,2})", re.IGNORECASE),
    re.compile(r"^BAAI-bge-(?P<version>m[3-9][.-]?\d{0,2})", re.IGNORECASE),
    re.compile(r"v(?P<version>\d\.\d{1,2})", re.IGNORECASE),
    re.compile(r"v(?P<version>\d-\d{1,2})", re.IGNORECASE),
    re.compile(r"v(?P<version>\d)", re.IGNORECASE),
    re.compile(r"[_-](?P<version>\d\.\d{1,2})(?![a-ux-z])[_-]?", re.IGNORECASE),
    re.compile(r"[_-](?P<version>\d-\d{1,2})(?![a-ux-z])[_-]?", re.IGNORECASE),
    re.compile(r"(?P<version>\d[.-]\d{1,2})"),
    re.compile(r"[_-](?P<version>\d)$"),
    re.compile(r"[_-](?P<version>\d)[_-]"),
)
"""A set of patterns for finding versions in model names. Rather than try to capture with one, we keep it simple and try a few. They're in order of certainty."""

app = App(name="mteb-to-codeweaver")

Frameworks = Literal[
    "Sentence Transformers",
    "PyTorch",
    "GritLM",
    "LLM2Vec",
    "TensorFlow",
    "API",
    "Tevatron",
    "NumPy",
    "PyLate",
    "ColBERT",
    "ColPali",
]


def get_mteb_model_metadata(
    models: str | Iterable[str] = "all",
    *,
    languages: Iterable[str] | None = None,
    open_weights: bool | None = None,
    frameworks: Iterable[Frameworks] | None = None,
    n_parameters_range: tuple[int | None, int | None] = (None, None),
    use_instructions: bool | None = None,
    zero_shot_on: list[AbsTask] | None = None,
) -> ModelMeta | Iterable[ModelMeta]:
    """
    Fetch MTEB model metadata for given model names or all models if 'all' is specified.
    Optionally filter by languages, frameworks, number of parameters, and other criteria.
    """
    kwargs = {
        "languages": languages,
        "open_weights": open_weights,
        "frameworks": frameworks,
        "n_parameters_range": n_parameters_range,
        "use_instructions": use_instructions,
        "zero_shot_on": zero_shot_on,
    }
    if not kwargs.values():
        kwargs = None
    if models == "all":
        return get_model_metas(**(kwargs or {}))  # pyright: ignore[reportArgumentType]
    if isinstance(models, str) and not kwargs:
        return get_model_meta(models)
    return get_model_metas(models, **(kwargs or {}))


type DistanceMetrics = Literal["cosine", "max_sim", "dot"]


class LoaderDict(TypedDict, total=False):
    """A dictionary representation of MTEB's `Loader` type, which are actually function arguments."""

    model_name: NotRequired[str | None]
    revision: NotRequired[str | None]
    attn: NotRequired[str | None]
    model_name_or_path: NotRequired[str | None]
    instruction_template: NotRequired[dict[str, Any] | None]
    model_prompts: NotRequired[dict[str, str] | None]
    """A dictionary mapping from instruction name to prompt string."""
    trust_remote_code: NotRequired[bool]
    normalized: NotRequired[bool]
    mode: NotRequired[
        Literal["embedding"]
    ]  # probably more values, but not in my small set of models
    pooling_method: NotRequired[Literal["mean", "max"]]
    torch_dtype: NotRequired[Literal["float16", "bfloat16", "float32"]]
    max_seq_length: NotRequired[int]
    padding_side: NotRequired[Literal["left", "right"]]
    add_eos_token: NotRequired[bool]


class SimplifiedModelMeta(TypedDict, total=False):
    """Modeled after the MTEB `ModelMeta` type, but to handle it after conversion to a dictionary."""

    name: Required[str | None]
    revision: NotRequired[str | None]
    release_date: NotRequired[PastDatetime | None]
    languages: NotRequired[list[str] | None]
    loader: NotRequired[LoaderDict | None]
    n_parameters: NotRequired[int | None]
    memory_usage_mb: NotRequired[float | None]
    max_tokens: NotRequired[int | None]
    embed_dim: NotRequired[int | None]
    license: NotRequired[str | None]
    open_weights: NotRequired[bool | None]
    public_training_code: NotRequired[str | None]
    public_training_data: NotRequired[AnyUrl | bool | None]
    framework: Required[list[Frameworks]]
    reference: NotRequired[AnyUrl | None]
    similarity_fn_name: NotRequired[DistanceMetrics | None]
    use_instructions: NotRequired[bool | None]
    training_datasets: NotRequired[dict[str, list[str]] | None]
    adapted_from: NotRequired[str | None]
    superseded_by: NotRequired[str | None]
    is_cross_encoder: NotRequired[bool | None]
    modalities: list[Literal["text", "image"]]


def check_for_prompts(model: SimplifiedModelMeta) -> dict[str, str] | None:
    """
    Check if the model has custom prompts defined.
    """
    if (loader := model.get("loader")) and (model_prompts := loader.get("model_prompts")):
        return model_prompts
    return None


def key_in_prompts(loader: LoaderDict, key: Literal["query", "document"]) -> str | None:
    """
    Check if a specific key exists in the model_prompts of the loader. Returns the actual keyname.
    """
    if not (prompts := check_for_prompts({"loader": loader})):  # pyright: ignore[reportArgumentType]
        return None
    keys = (
        {"query", "retrieval.query", "similarity.query"}
        if key == "query"
        else {
            "document",
            "retrieval.document",
            "passage",
            "retrieval.passage",
            "similarity.document",
            "similarity.passage",
        }
    )
    return next((value for key, value in prompts.items() if key in keys and value), None)  # pyright: ignore[reportOperatorIssue]


def attempt_to_get_version(name: str) -> str | int | float | None:
    """
    Attempt to get the version of a model by its name.
    """
    for pattern in VERSION_PATTERNS:
        if match := pattern.search(name):
            version = match.group("version")
            version = version.replace("-", ".").replace("_", ".")
            try:
                return float(version) if "." in version else int(version)
            except (ValueError, TypeError):
                return version
    return None


def mteb_to_capabilities(model: SimplifiedModelMeta) -> PartialCapabilities:  # pyright: ignore[reportReturnType]
    """
    Convert a MTEB model metadata dictionary to a PartialCapabilities object.
    """
    loader = getattr(model, "loader", {})
    loader = loader if isinstance(loader, dict) else {}
    caps = {
        "name": model["name"],
        "default_dimension": model["embed_dim"],
        "context_window": model["max_tokens"],
        "preferred_metrics": (model.get("similarity_fn_name", "cosine"),),
        "supports_context_chunk_embedding": False,
        "tokenizer": "tokenizers",
        "tokenizer_model": model["name"],
        "default_dtype": "float32",
        "output_dtypes": ("float32",),
        "version": attempt_to_get_version(model["name"]),
        "supports_custom_prompts": model.get("use_instructions", False)
        or model.get("supports_custom_prompts", False),
        "custom_query_prompt": model.get(key_in_prompts(loader, "query") or "")  # pyright: ignore[reportArgumentType]
        if loader is not None
        else None,
        "custom_document_prompt": model.get(key_in_prompts(loader, "document") or "")  # pyright: ignore[reportArgumentType]
        if loader is not None
        else None,
        "other": {
            k: v
            for k, v in model.items()
            if k
            not in {
                "name",
                "embed_dim",
                "max_tokens",
                "similarity_fn_name",
                "use_instructions",
                "training_datasets",
                "languages",
            }  # we also leave out some of the more verbose fields
            and v is not None
        },
    }
    for field in ("context_window", "default_dimension"):
        if field in caps:
            caps[field] = int(caps[field])
    if (
        (other := caps.get("other"))
        and isinstance(other, dict)
        and (mem_usage := other.get("memory_usage_mb"))
    ):
        other["memory_usage_mb"] = int(mem_usage)
        other["memory_usage_gb"] = int(mem_usage) / 1024
    if (metric := caps.get("preferred_metrics")) and isinstance(metric, tuple):
        if metric[0] == "cosine":
            metric = ("cosine", "dot_product", "euclidean")
        caps["preferred_metrics"] = metric
    return caps


def from_mteb_to_simplified(obj: ModelMeta) -> SimplifiedModelMeta:
    """
    Convert a Pydantic MTEB model metadata object to a SimplifiedModelMeta dictionary.
    """
    # loader is a functools.partial, we're going to grab its kwargs
    mapped_obj = obj.model_copy(deep=True).to_dict()
    mapped_obj["loader"] = {}
    if (loader := obj.loader) and hasattr(loader, "keywords"):
        mapped_obj = mapped_obj | {"loader": loader.keywords or {}}
    else:
        mapped_obj["loader"] = {}
    return SimplifiedModelMeta(mapped_obj)


def build_get_function(maker: str, var_names: tuple[str, ...]) -> str:
    """Build a get function for a specific model maker."""
    func_line = f"def get_{sanitize_name(maker.lower())}_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:"
    docstring = f'    """Get the capabilities for {maker} embedding models."""'
    return_stmt = f"   return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in ({', '.join(var_names)}))"
    return f"{func_line}\n\n{docstring}\n\n{return_stmt}"


def generate_capabilities_file(models: list[SimplifiedModelMeta], model_maker: str) -> str:
    """Generate a capabilities module from MTEB models."""
    header = [
        f'"""Capabilities for {model_maker} embedding models."""',
        "# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.",
        "# SPDX-License-Identifier: MIT OR Apache-2.0",
        "# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>",
        "from __future__ import annotations",
        "",
        "from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities, PartialCapabilities",
        "",
        "",
    ]

    capabilities = []
    for model in models:
        caps = mteb_to_capabilities(model)
        var_name = sanitize_name(caps["name"]) + "_CAPABILITIES"

        # Format the dictionary nicely
        formatted_dict = format_python_dict(caps, indent_level=0)
        capabilities.append(f"{var_name}: PartialCapabilities = {formatted_dict}")

    # Combine everything
    code = "\n\n".join(["\n".join(header), "", *capabilities])
    cap_names = tuple(sanitize_name(caps["name"]) + "_CAPABILITIES" for caps in capabilities)
    func_def = build_get_function(model_maker, cap_names)
    # Format with black
    page = f"{code}\n\n\n{func_def}\n"
    return black.format_str(page, mode=black.FileMode())


def format_python_dict(d: dict[str, Any], indent_level: int = 0) -> str:
    """Format a dictionary as clean Python code."""
    if not d:
        return "{}"

    indent = "    " * (indent_level + 1)
    close_indent = "    " * indent_level

    items = []
    for key, value in d.items():
        formatted_value = format_python_value(value, indent_level + 1)
        items.append(f'{indent}"{key}": {formatted_value}')

    return "{\n" + ",\n".join(items) + f",\n{close_indent}" + "}"


def format_python_value(value: Any, indent_level: int = 0) -> str:
    """Format any Python value as code."""
    if isinstance(value, str):
        return repr(value)  # Handles escaping automatically
    if isinstance(value, dict):
        return format_python_dict(value, indent_level)
    if isinstance(value, list | tuple):
        if not value:
            return "[]" if isinstance(value, list) else "()"

        # Format as multiline if complex
        if any(isinstance(v, dict | list | tuple) for v in value):
            indent = "    " * (indent_level + 1)
            close_indent = "    " * indent_level
            items = [f"{indent}{format_python_value(v, indent_level + 1)}" for v in value]
            bracket = "[]" if isinstance(value, list) else "()"
            return f"{bracket[0]}\n" + ",\n".join(items) + f",\n{close_indent}{bracket[1]}"
        # Simple inline format
        items = [format_python_value(v, indent_level) for v in value]
        bracket = "[]" if isinstance(value, list) else "()"
        return f"{bracket[0]}{', '.join(items)}{bracket[1]}"
    return repr(value)


def sanitize_name(name: str) -> str:
    """Convert model name to valid Python identifier."""
    return name.replace("-", "_").replace(".", "_").replace("/", "_").upper()


@app.default
def get(
    names: Annotated[list[str], Parameter(help="List of model names.")],
) -> dict[str, PartialCapabilities]:
    """Get capabilities for a list of model names."""
    models = get_mteb_model_metadata(names)
    simplified = [from_mteb_to_simplified(m) for m in models]
    by_maker = {}
    for model in simplified:
        maker = model["name"].split("/")[0]
        if maker not in by_maker:
            by_maker[maker] = [model]
        else:
            by_maker[maker].append(model)
    for maker, models in by_maker.items():
        filename = (
            Path("src/codeweaver/embedding/capabilities") / f"{sanitize_name(maker.lower())}.py"
        )
        if not filename.exists():
            filename.touch()
        filename.write_text(generate_capabilities_file(models, maker))


if __name__ == "__main__":
    app.run()
