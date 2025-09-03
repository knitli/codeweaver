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

import functools
import json
import re
import sys

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, LiteralString, NotRequired, Required, TypedDict, cast

import black

from cyclopts import App, Parameter
from mteb import AbsTask, ModelMeta, get_model_meta, get_model_metas
from pydantic import AnyUrl, PastDatetime
from rich.console import Console


# make sure codeweaver is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from codeweaver._settings import Provider
from codeweaver.embedding.capabilities.base import PartialCapabilities


VERSION_PATTERNS = (  # some special cases first
    re.compile(r"^Qwen/Qwen(?P<version>[3-9][.-]?\d{0,2})", re.IGNORECASE),
    re.compile(r"^BAAI-bge-(?P<version>m[3-9][.-]?\d{0,2})", re.IGNORECASE),
    re.compile(r"intfloat/.+-(?P<version>e[5-9]}-)", re.IGNORECASE),
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

type ModelName = LiteralString
"""The Hugging Face name for a model, in the HF format of organization/name. For models in `HF_NAMES`, this is the *value*"""


console = Console(markup=True, soft_wrap=True)
app = App(name="mteb-to-codeweaver")

Frameworks = Literal[
    "API",
    "ColBERT",
    "ColPali",
    "GritLM",
    "LLM2Vec",
    "NumPy",
    "PyLate",
    "PyTorch",
    "Sentence Transformers",
    "TensorFlow",
    "Tevatron",
]

NormalizedModels = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "jinaai/jina-embeddings-v2-base-code",
    "thenlper/gte-base",
    "thenlper/gte-large",
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
    return get_model_metas(models, **(kwargs or {}))  # pyright: ignore[reportArgumentType]


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

    name: Required[str]
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

    def replacements(s: str) -> tuple[str, str, str, str, str, str]:
        return (
            s,
            s.lower(),
            s.replace("-", "").lower(),
            s.replace("-", ".").lower(),
            s.replace("-", ""),
            s.replace("-", "."),
        )

    if not (prompts := check_for_prompts({"loader": loader})):  # pyright: ignore[reportArgumentType]
        return None
    query_keys = {
        word
        for tup in {"Retrieval-Query", "Similarity-Query", "Query", "DocumentUnderstanding"}
        for word in replacements(tup)
    }
    doc_keys = {
        word
        for tup in {"Retrieval-Document", "Similarity-Document", "Document", "Passage"}
        for word in replacements(tup)
    }
    keys = query_keys if key.lower() == "query" or key in query_keys else doc_keys
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


type ModelMaker = Literal[
    "Alibaba-NLP",
    "BAAI",
    "ibm-granite",
    "intfloat",
    "jinaai",
    "mixedbread-ai",
    "nomic-ai",
    "Qwen",
    "WhereIsAI",
    "thenlper",
    "sentence-transformers",
    "Snowflake",
]
type HFModelProviders = Literal[
    Provider.FASTEMBED,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.FIREWORKS,
    Provider.GROQ,
    Provider.OLLAMA,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TOGETHER,
]

type SparseMap = dict[
    Literal[Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS],
    list[ModelName | dict[Literal["Qdrant/Spade_PP_en_v1"], Literal["prithivida/Spade_PP_en_v1"]]],
]

type AliasMap = dict[Provider, dict[ModelName, ModelName]]
"""A mapping of providers to the Hugging Face names, as keys, and the provider equivalent as values."""

type DataMap = dict[ModelName, SimplifiedModelMeta]

type ModelMap = dict[ModelMaker, dict[ModelName, tuple[HFModelProviders, ...]]]
"""A mapping of model makers to their models and the providers that support each model."""


def build_map(mapping: dict[str, dict[str, list[str]]]) -> ModelMap:
    """Build the model map from a raw dictionary."""
    parsed_map: ModelMap = cast(ModelMap, dict.fromkeys(mapping.keys()))
    for maker, values in mapping.items():
        for model, providers in values.items():
            if maker not in parsed_map or parsed_map[maker] is None:
                parsed_map[cast(ModelMaker, maker)] = {}
            parsed_map[maker][model] = tuple(Provider.from_string(p) for p in providers)  # pyright: ignore[reportArgumentType]
    return parsed_map


def load_map() -> tuple[DataMap, ModelMap, AliasMap, SparseMap]:
    """Load the model map from the JSON file."""
    try:
        path = Path(__file__).parent / "hf_models.json"
        data, mapping, alias_mapping, sparse_models = json.loads(path.read_text())
        sparse_models = {Provider.from_string(k): v for k, v in sparse_models.items()}  # pyright: ignore[reportArgumentType]
        parsed_alias_map = cast(
            AliasMap, {Provider.from_string(k): v for k, v in alias_mapping.items()}
        )  # pyright: ignore[reportArgumentType]
        parsed_map = build_map(mapping)
    except Exception:
        console.print_exception(show_locals=True)
        return {}, {}, {}, {}
    else:
        return data, parsed_map, parsed_alias_map, cast(SparseMap, sparse_models)


DATA, MODEL_MAP_DATA, ALIAS_MAP_DATA, SPARSE_MODELS = load_map()
FLATTENED_ALIASES: dict[ModelName, ModelName] = {
    k: v for val in ALIAS_MAP_DATA.values() for k, v in val.items()
}


def mteb_to_capabilities(model: SimplifiedModelMeta) -> PartialCapabilities:  # pyright: ignore[reportReturnType]
    """
    Convert an MTEB model metadata dictionary to a PartialCapabilities object.
    """
    loader = getattr(model, "loader", {})
    loader = loader if isinstance(loader, dict) else {}
    caps = {
        "name": model["name"],
        "default_dimension": model.get("embed_dim"),
        "context_window": model.get("max_tokens"),
        "preferred_metrics": (model.get("similarity_fn_name", "cosine"),),
        "supports_context_chunk_embedding": False,
        "tokenizer": "tokenizers",
        "tokenizer_model": model["name"],
        "default_dtype": "float",
        "output_dtypes": ("float",),
        "version": attempt_to_get_version(model["name"]),
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
        other["memory_usage_gb"] = round(int(mem_usage) / 1024, 2)
    if (metric := caps.get("preferred_metrics")) and isinstance(metric, tuple):
        if metric[0] == "cosine" and len(metric) == 1:
            metric = ("cosine", "dot", "euclidean")
        caps["preferred_metrics"] = metric
    if (
        (name := model.get("name"))
        and ("jina-embeddings" in name)
        and ("-v3" in name or "-v4" in name)
    ):
        caps["output_dimensions"] = (
            (1024, 512, 256, 128, 64, 32) if "-v3" in name else (2048, 1024, 512, 256, 128)
        )
    aliases = [v for val in ALIAS_MAP_DATA.values() for v in val.values()]
    if aliased := next((v for v in aliases if caps["name"] == v), None):
        caps["hf_name"] = next((k for k, v in FLATTENED_ALIASES.items() if v == aliased), None)
        caps["name"] = aliased
    elif caps["name"] in FLATTENED_ALIASES and not caps.get("hf_name"):
        caps["hf_name"] = next((k for k in FLATTENED_ALIASES if k == caps["name"]), None)
    if "Qwen3" in model["name"]:
        caps["other"] = caps.get("other", {}) | {
            "model": {
                "instruction": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query."
            }
        }  # pyright: ignore[reportOperatorIssue]

    return cast(PartialCapabilities, caps)


def from_mteb_to_simplified(obj: ModelMeta) -> SimplifiedModelMeta:
    """
    Convert a Pydantic MTEB model metadata object to a SimplifiedModelMeta dictionary.
    """
    # loader is a functools.partial, we're going to grab its kwargs
    mapped_obj = obj.model_copy(deep=True).to_dict()
    mapped_obj["loader"] = {}
    if (loader := obj.loader) and hasattr(loader, "keywords"):
        mapped_obj = mapped_obj | {
            "loader": cast(dict[str, Any], cast(functools.partial, loader).keywords) or {}
        }
    else:
        mapped_obj["loader"] = {}
    return SimplifiedModelMeta(mapped_obj)


def build_get_function(maker: str) -> str:
    """Build a get function for a specific model maker."""
    func_line = f"def get_{sanitize_name(maker).lower()}_embedding_capabilities() -> tuple[EmbeddingModelCapabilities, ...]:"
    docstring = f'    """Get the capabilities for {maker} embedding models."""'
    capabilities = "    capabilities: list[EmbeddingCapabilities] = []"
    provider_caps = '    for cap in ALL_CAPABILITIES:\n        capabilities.extend([EmbeddingCapabilities({**cap, "provider": provider}) for provider in CAP_MAP[cap["name"]]])'
    return_stmt = (
        "    return tuple(EmbeddingModelCapabilities.model_validate(cap) for cap in capabilities)"
    )
    return f"{func_line}\n\n{docstring}\n{capabilities}\n{provider_caps}\n{return_stmt}"


def to_camel(s: str) -> str:
    """Convert a snake_case string to CamelCase."""
    parts = s.split("_") if "_" in s else s.split("-")
    return "".join(word.capitalize() for word in parts)


def generate_capabilities_file(models: list[SimplifiedModelMeta], model_maker: ModelMaker) -> str:
    """Generate a capabilities module from MTEB models."""
    header = [
        "# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.",
        f'"""Capabilities for {model_maker} embedding models."""',
        "# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.",
        "# SPDX-License-Identifier: MIT OR Apache-2.0",
        "# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>",
        "from __future__ import annotations",
        "",
        "from typing import Literal",
        "",
        "from codeweaver._settings import Provider",
        "from codeweaver.embedding.capabilities.base import EmbeddingCapabilities, EmbeddingModelCapabilities, PartialCapabilities",
        "",
        "",
    ]
    cap_partials = [mteb_to_capabilities(model) for model in models]
    for cap_partial in cap_partials:
        if not isinstance(cap_partial["output_dtypes"], tuple):
            cap_partial["output_dtypes"] = (cap_partial["output_dtypes"],)  # pyright: ignore[reportArgumentType]
    capabilities = []
    cap_map = MODEL_MAP_DATA.get(model_maker, {})
    maker_title = to_camel(model_maker)
    cap_type = f"type {maker_title}Provider = Literal[{', '.join(sorted({f'{format_python_value(v)}' if isinstance(val, tuple) else format_python_value(val) for val in cap_map.values() for v in val}))}]"
    printed_map = f"CAP_MAP: dict[Literal[{', '.join(f'"{k!s}"' for k in cap_map)}], tuple[{maker_title}Provider, ...]] = {format_python_dict(cast(dict[str, Any], cap_map), indent_level=0)}\n\n"
    sanitized_names = [
        sanitize_name(
            cast(str, caps["name"])
            if caps["name"] not in FLATTENED_ALIASES
            else FLATTENED_ALIASES[caps["name"]]
        )
        for caps in cap_partials
    ]
    for i, caps in enumerate(cap_partials):
        var_name = f"{sanitized_names[i]}_CAPABILITIES"

        # Format the dictionary nicely
        formatted_dict = format_python_dict(caps, indent_level=0)  # pyright: ignore[reportArgumentType]
        capabilities.append(f"{var_name}: PartialCapabilities = {formatted_dict}")
    capabilities += f"\nALL_CAPABILITIES: tuple[PartialCapabilities, ...] = ({', '.join(f'{name}_CAPABILITIES' for name in sanitized_names)})\n".splitlines()
    # Combine everything
    code = "\n\n".join(["\n".join(header), "", cap_type, printed_map, *capabilities])
    func_def = build_get_function(model_maker)
    # Format with black
    page = f"{code}\n\n\n{func_def}\n"
    # black seems to think single tuples are just the value in parentheses, so we replace them after formatting
    return (
        black.format_str(
            page,
            mode=black.FileMode(
                target_versions={black.TargetVersion.PY312, black.TargetVersion.PY313}
            ),
        )
        .replace('("float")', '("float",)')
        .replace('("Provider.SENTENCE_TRANSFORMERS")', '("Provider.SENTENCE_TRANSFORMERS",)')
        .replace('("Provider.FASTEMBED")', '("Provider.FASTEMBED",)')
        .replace('("Provider.HUGGINGFACE_INFERENCE")', '("Provider.HUGGINGFACE_INFERENCE",)')
        .replace('("Provider.OLLAMA")', '("Provider.OLLAMA",)')
        .replace('("Provider.TOGETHER")', '("Provider.TOGETHER",)')
        .replace('("Provider.FIREWORKS")', '("Provider.FIREWORKS",)')
        .replace('("Provider.GROQ")', '("Provider.GROQ",)')
    )


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
    if isinstance(value, Provider):
        return f"Provider.{value.name}"
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
    if name.lower() in FLATTENED_ALIASES:
        name = FLATTENED_ALIASES[cast(LiteralString, name.lower())]
    return name.replace("-", "_").replace(".", "_").replace("/", "_").replace(":", "_").upper()


def write_capabilities_file(maker: ModelMaker, content: str) -> None:
    """Write the capabilities file for a specific model maker."""
    filename = Path("src/codeweaver/embedding/capabilities") / f"{sanitize_name(maker).lower()}.py"
    if not filename.exists():
        filename.touch()
    _ = filename.write_text(content)


def generate_with_simplified(simplified_data: Sequence[SimplifiedModelMeta]) -> None:
    """Generate code from simplified model metadata."""
    by_maker = dict.fromkeys(MODEL_MAP_DATA.keys())
    for model in simplified_data:
        model_id = (
            model["name"]
            if model["name"] not in FLATTENED_ALIASES
            else FLATTENED_ALIASES[model["name"]]
        )
        maker = cast(ModelMaker, model_id.split("/")[0])
        if by_maker[maker] is None:
            by_maker[maker] = []
        cast(list[dict], by_maker[maker]).append(model)  # pyright: ignore[reportArgumentType]

    for maker, models in by_maker.items():
        filename = (
            Path("src/codeweaver/embedding/capabilities") / f"{sanitize_name(maker).lower()}.py"
        )
        if not filename.exists():
            filename.touch()
        _ = filename.write_text(generate_capabilities_file(models, maker))


@app.command(name="from-data")
def from_data() -> None:
    """Uses the existing json data to regenerate all capability files."""
    makers = tuple(MODEL_MAP_DATA.keys())
    for maker in makers:
        model_names = tuple(FLATTENED_ALIASES.get(k, k) for k in MODEL_MAP_DATA[maker])
        models = [
            mod
            for mod_name, mod in DATA.items()
            if mod_name in model_names or FLATTENED_ALIASES.get(mod_name, "SENTINEL") in model_names
        ]
        file = generate_capabilities_file(models, maker)
        write_capabilities_file(maker, file)


@app.default
def get(names: Annotated[list[ModelName], Parameter(help="List of model names.")]) -> None:
    """Get capabilities for a list of model names."""
    models = get_mteb_model_metadata(names)
    simplified: Sequence[SimplifiedModelMeta] = [from_mteb_to_simplified(m) for m in models]
    generate_with_simplified(simplified)


if __name__ == "__main__":
    app()
