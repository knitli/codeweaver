#!/usr/bin/env -S uv run -s
# ///script
# requires-python = "3.13"
# dependencies = ["pydantic>=2.12.5", "black>=25.12.0", "rich>=14.2.0", "cyclopts>=4.3.0", "mteb>=2.3.10", "fastembed>=0.7.4"]
# ///
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""A helper script for converting MTEB model metadata to CodeWeaver capabilities.

Note that the models in the MTEB dataset are only those with validated scores on MTEB tasks,
so it's not a complete list of all possible models. It get most of the popular ones, at least for dense models. Sparse models are less well represented, with the opensearch-project models the only ones in the database for now.
"""

from __future__ import annotations

import functools
import re
import sys

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, NotRequired, Required, TypedDict, cast

import black

from cyclopts import App, Parameter
from mteb import AbsTask, get_model_meta, get_model_metas
from mteb.models import ModelMeta, SentenceTransformerEncoderWrapper, sentence_transformers_loader
from pydantic import (
    AnyUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PastDatetime,
    computed_field,
    field_serializer,
)
from pydantic_core import from_json
from rich.console import Console
from typing_extensions import TypeIs


# make sure codeweaver is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from codeweaver.providers.embedding.capabilities.types import PartialCapabilities
from codeweaver.providers.provider import Provider


# TODO: Finish refactor to use these inline constants and eliminate the hf-models.json
# we'll use the secondary_providers.json but everything
# else can be generated from MTEB and these constants
type ModelName = str
"""The Hugging Face name for a model, in the HF format of organization/name."""


JSON_CACHE = Path(__file__).parent / "hf-models.json"
SECONDARY_PROVIDERS_JSON = Path(__file__).parent / "secondary_providers.json"

SECONDARY_PROVIDERS_DATA: dict[
    Literal["fireworks", "groq", "hf-inference", "ollama", "together"], list[ModelName]
] = from_json(SECONDARY_PROVIDERS_JSON.read_bytes())


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


OLLAMA_ALIASES = {
    "BAAI/bge-large-en-v1.5": "bge-large-en:335m",
    "BAAI/bge-m3": "bge-m3:567m",
    "Snowflake/snowflake-arctic-embed-l-v2.0": "snowflake-arctic-embed2:568m",
    "ibm-granite/granite-embedding-278m-multilingual": "granite-embedding:278m",
    "ibm-granite/granite-embedding-30m-english": "granite-embedding:30m",
    "mixedbread-ai/mxbai-embed-large-v1": "mxbai-embed-large",
    "nomic-ai/nomic-embed-text-v1.5": "nomic-embed-text",
    "sentence-transformers/all-MiniLM-L6-v2": "all-minilm:22m",
}
"""Most secondary providers use the Hugging Face names directly, but Ollama does things differently, so we have to map them here. Keys are HF names and values are Ollama names.

Note: FastEmbed also has some aliases, but we handle those dynamically below.
"""

KNOWN_SPARSE_MODELS = {
    Provider.FASTEMBED: [
        "Qdrant/bm25",
        "Qdrant/bm42-all-minilm-l6-v2-attentions",
        "Qdrant/minicoil-v1",
        {"Qdrant/Splade_PP_en_v1": "prithivida/Splade_PP_en_v1"},
    ],
    Provider.SENTENCE_TRANSFORMERS: [
        "ibm-granite/granite-embedding-30m-sparse",
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-distill",
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini",
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-distill",
        "opensearch-project/opensearch-neural-sparse-encoding-doc-v3-gte",
        "prithivida/Splade_PP_en_v2",
    ],
}


def get_metas() -> Sequence[ModelMeta]:
    """Get all MTEB model metadata."""
    return [m for m in get_model_metas() if "Sentence Transformers" in m.framework]


def get_rerankers() -> Sequence[ModelMeta]:
    """Get all MTEB reranker model metadata."""
    return [m for m in get_metas() if m.is_cross_encoder]


def get_hf_name(model: dict[str, Any]) -> str | None:
    """
    Get the Hugging Face name for a model from its fastembed metadata.
    """
    return hf_name if (hf_name := model.get("sources", {}).get("hf")) else None


def fastembed_embedding_models(data: Sequence[ModelMeta]) -> dict[ModelName, ModelMeta]:
    """
    Get the fastembed embedding models from the MTEB data.
    """
    from fastembed import TextEmbedding

    models = TextEmbedding.list_supported_models()
    hf_names = [
        hf_name if (hf_name := get_hf_name(model)) is not None else model["model"]
        for model in models
    ]
    return {model.name: model for model in data if model.name in hf_names}


def fastembed_sparse_models(data: Sequence[ModelMeta]) -> dict[ModelName, ModelMeta]:
    """
    Get the fastembed sparse models from the MTEB data.
    """
    from fastembed import SparseTextEmbedding

    models = SparseTextEmbedding.list_supported_models()
    hf_names = [
        hf_name if (hf_name := get_hf_name(model)) is not None else model["model"]
        for model in models
    ]
    return {model.name: model for model in data if model.name in hf_names}


def get_fastembed_aliases(*, sparse: bool = False) -> dict[ModelName, ModelName]:
    """Get the fastembed aliases from the MTEB data."""
    from fastembed import SparseTextEmbedding, TextEmbedding

    embedding_models = (
        SparseTextEmbedding.list_supported_models()
        if sparse
        else TextEmbedding.list_supported_models()
    )
    return {
        hf_name: model["model"]
        for model in embedding_models
        if (hf_name := get_hf_name(model)) is not None
    }


console = Console(markup=True, soft_wrap=True)
app = App(name="mteb-to-codeweaver")
Names = Annotated[list[ModelName], Parameter(help="List of model names.")]

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
        return [
            model
            for model in get_model_metas(**(kwargs or {}))
            if "Sentence Transformers" in model.framework
        ]
    if isinstance(models, str) and not kwargs:
        return get_model_meta(models)
    return get_model_metas(
        models if isinstance(models, list | set | tuple) else [models], **(kwargs or {})
    )


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

    if not (prompts := check_for_prompts({"loader": loader})):  # ty:ignore[missing-typed-dict-key]
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
    return next((value for key, value in prompts.items() if key in keys and value), None)


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
    "minishlab",
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


type AliasMap = dict[
    Annotated[Provider, BeforeValidator(lambda v: Provider.from_string(v))],
    dict[ModelName, ModelName],
]
"""A mapping of providers to the Hugging Face names, as keys, and the provider equivalent as values."""

type DataMap = dict[ModelName, SimplifiedModelMeta]

type ModelMap = dict[
    ModelMaker,
    dict[
        ModelName,
        tuple[Annotated[HFModelProviders, BeforeValidator(lambda v: Provider.from_string(v))], ...],
    ],
]
"""A mapping of model makers to their models and the providers that support each model."""


def is_a_dictionary_really_pyright(value: Any) -> TypeIs[dict[str, Any]]:
    """A type guard to convince pyright that something is a dictionary."""
    return isinstance(value, dict) and all(isinstance(k, str) for k in value)


def is_a_modelmeta(value: Any) -> TypeIs[ModelMeta]:
    """A type guard to convince pyright that something is a ModelMeta."""
    return isinstance(value, ModelMeta) and hasattr(value, "model_dump")


def do_nothing(value: Any) -> None:
    """A no-op function."""


def dict_to_partial(v: dict[str, Any] | str | ModelMeta) -> Callable[..., Any]:
    """Validator for ModelMeta, handling conversions."""
    new_loader: Callable[..., Any] = do_nothing
    if isinstance(v, str):
        v = from_json(v)
        v: dict[str, Any] | ModelMeta
    new_v = v.copy() if isinstance(v, dict) else v.model_copy(deep=True)
    if isinstance(v, dict) and v.get("loader") and is_a_dictionary_really_pyright(v):
        new_loader = (
            functools.partial(sentence_transformers_loader, **v.get("loader", {}))
            if isinstance(v.get("loader"), dict)
            else lambda _: None
        )  # type: ignore
        if (
            cast(dict, v).get("license")
            and "jinaai" in v.get("name", "")
            and "qwen" in v.get("license", "")
        ):  # type: ignore
            cast(dict, new_v)["license"] = "cc-by-nc-4.0"
        if v.get("name") and v.get("name", "").startswith("snowflake-arctic-embed2"):
            cast(dict, new_v)["name"] = "Snowflake/snowflake-arctic-embed-v2.0-ollama"
        new_v = cast(dict, new_v) | {"loader": new_loader}
    elif isinstance(v, ModelMeta):
        if (
            v.loader
            and not hasattr(v.loader, "keywords")
            and is_a_dictionary_really_pyright(v.loader)
        ):
            if is_a_dictionary_really_pyright(v.loader):
                new_loader: Callable[..., SentenceTransformerEncoderWrapper] = functools.partial(
                    sentence_transformers_loader, **v.loader
                )
        elif not hasattr(v.loader, "keywords") and callable(v.loader):
            new_loader = v.loader
        else:
            new_loader = v.loader  # ty:ignore[invalid-assignment]
        if v.license and v.name and "jinaai" in v.name and "qwen" in v.license:
            cast(ModelMeta, new_v).license = "cc-by-nc-4.0"
        cast(ModelMeta, new_v).loader = new_loader  # ty:ignore[invalid-assignment]
    return new_v  # ty:ignore[invalid-return-type]


class RootJson(BaseModel):
    """The root structure of the JSON file."""

    model_config = ConfigDict(
        str_strip_whitespace=True, populate_by_name=True, use_enum_values=True
    )

    models: Annotated[
        dict[ModelName, Annotated[ModelMeta, BeforeValidator(dict_to_partial)]],
        Field(default_factory=dict, description="""A mapping of model names to their metadata."""),
    ]

    _json_path: ClassVar[Path] = JSON_CACHE

    @field_serializer("models", mode="plain")
    def serialize_models(self, value: dict[ModelName, ModelMeta]) -> dict[ModelName, ModelMeta]:
        """Serialize the models for JSON output."""
        for key, model in value.items():
            if model.loader and hasattr(model.loader, "keywords"):
                model.loader = model.loader.keywords  # ty:ignore[invalid-assignment]
            else:
                model.loader = {}  # type: ignore
            value[key] = model
        return value

    @property
    def flattened_aliases(self) -> dict[ModelName, ModelName]:
        """A flattened mapping of all aliases."""
        return {k: v for val in self.aliases.values() for k, v in val.items()}

    @computed_field
    @property
    def model_map(self) -> ModelMap:
        """A computed field for the model map."""
        mapping: ModelMap = defaultdict(lambda: defaultdict(list))
        for model_name in self.models:
            maker = model_name.split("/")[0]
            providers: list[HFModelProviders] = []
            providers.extend(
                provider
                for provider, aliases in self.aliases.items()
                if model_name in aliases.values()
            )
            mapping[maker][model_name] = tuple(providers)
        return mapping

    @computed_field
    @property
    def aliases(self) -> AliasMap:
        """A computed field for the alias map."""
        alias_map: AliasMap = defaultdict(dict)
        for provider, aliases in KNOWN_ALIASES.items():
            for hf_name, alias in aliases.items():
                alias_map[Provider.from_string(provider)][hf_name] = alias
        return alias_map | {Provider.FASTEMBED: get_fastembed_aliases()}

    def save(self) -> int:
        """Save the JSON data to the file."""
        return self._json_path.write_text(self.model_dump_json(indent=4))

    @classmethod
    def from_model_metas(cls, models: Sequence[ModelMeta]) -> RootJson:
        """Create a RootJson instance from a sequence of ModelMeta objects."""
        models = [{model.name: model} for model in models if models and model is not None]  # ty:ignore[invalid-assignment]
        return cls(models=models)

    @classmethod
    def load(cls) -> RootJson:
        """Load the JSON data from the file."""
        return cls.model_validate_json(cls._json_path.read_text())


"""
    _ROOT = RootJson.load()
    DATA = _ROOT.models
    MODEL_MAP_DATA = _ROOT.model_map
    ALIAS_MAP_DATA = _ROOT.aliases
    SPARSE_MODELS = _ROOT.sparse_models

    FLATTENED_ALIASES = _ROOT.flattened_aliases
else:
    DATA = {}
    MODEL_MAP_DATA = {}
    ALIAS_MAP_DATA = {}
    SPARSE_MODELS = {}
    FLATTENED_ALIASES = {}
"""


def mteb_to_capabilities(model: SimplifiedModelMeta) -> PartialCapabilities:
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
        other["memory_usage_mb"] = int(mem_usage)  # ty:ignore[invalid-assignment]
        other["memory_usage_gb"] = round(int(mem_usage) / 1024, 2)  # ty:ignore[invalid-assignment]
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
        caps["other"] = cast(dict[str, Any], caps.get("other", {})) | {
            "model": {
                "instruction": "Given search results containing code snippets, tree-sitter parse trees, documentation and code comments from a codebase, retrieve relevant Documents that answer the Query."
            }
        }
    return cast(PartialCapabilities, caps)


def from_mteb_to_simplified(obj: ModelMeta) -> SimplifiedModelMeta:
    """
    Convert a Pydantic MTEB model metadata object to a SimplifiedModelMeta dictionary.
    """
    # loader is a functools.partial, we're going to grab its kwargs
    if isinstance(obj, ModelMeta) and isinstance(obj.loader, dict):
        return SimplifiedModelMeta(dict(obj))  # ty:ignore[missing-typed-dict-key]
    mapped_obj = obj.model_copy(deep=True).model_dump(mode="python")
    mapped_obj["loader"] = mapped_obj["loader"] if isinstance(mapped_obj["loader"], dict) else {}
    if (loader := obj.loader) and hasattr(loader, "keywords"):
        mapped_obj = mapped_obj | {
            "loader": cast(dict[str, Any], cast(functools.partial, loader).keywords) or {}
        }
    else:
        mapped_obj["loader"] = {}
    return SimplifiedModelMeta(mapped_obj)  # ty:ignore[missing-typed-dict-key]


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
    # REUSE-IgnoreStart
    header = [
        "# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY. The `mteb_to_codeweaver.py` script is used to generate this file.",
        f'"""Capabilities for {model_maker} embedding models."""',
        "# SPDX-FileCopyrightText: 2025 Knitli Inc.",
        "# SPDX-License-Identifier: MIT OR Apache-2.0",
        "# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>",
        "from __future__ import annotations",
        "",
        "from typing import Literal",
        "",
        "from codeweaver.provider import Provider",
        "from codeweaver.embedding.capabilities.base import EmbeddingCapabilities, EmbeddingModelCapabilities, PartialCapabilities",
        "",
        "",
        # REUSE-IgnoreEnd
    ]
    cap_partials = [mteb_to_capabilities(model) for model in models]
    for cap_partial in cap_partials:
        if not isinstance(cap_partial["output_dtypes"], tuple):
            cap_partial["output_dtypes"] = (cap_partial["output_dtypes"],)  # ty:ignore[invalid-assignment]
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
        formatted_dict = format_python_dict(caps, indent_level=0)
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
                target_versions={
                    black.TargetVersion.PY312,
                    black.TargetVersion.PY313,
                    black.TargetVersion.PY314,
                }
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
        name = FLATTENED_ALIASES[cast(str, name.lower())]
    return name.replace("-", "_").replace(".", "_").replace("/", "_").replace(":", "_").upper()


def write_capabilities_file(maker: ModelMaker, content: str) -> None:
    """Write the capabilities file for a specific model maker."""
    filename = (
        Path("src/codeweaver/providers/embedding/capabilities")
        / f"{sanitize_name(maker).lower()}.py"
    )
    if not filename.exists():
        filename.touch()
    existing_content = filename.read_text()
    if existing_content == content:
        return
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
        cast(list[dict], by_maker[maker]).append(model)

    for maker, models in by_maker.items():
        filename = (
            Path("src/codeweaver/providers/embedding/capabilities")
            / f"{sanitize_name(maker).lower()}.py"
        )
        if not filename.exists():
            filename.touch()
        _ = filename.write_text(generate_capabilities_file(models, maker))


@app.command(name="add-to-json")
def add_to_json(
    names: Names,
    *,
    alias_mapping: Annotated[
        dict[Provider, dict[ModelName, ModelName]] | None,
        Parameter(
            accepts_keys=True,
            json_dict=True,
            help="A mapping of providers to the Hugging Face names, as keys, and the provider equivalent as values.",
        ),
    ] = None,
    rewrite_cw_modules: Annotated[
        bool,
        Parameter(
            name=["--rewrite-capabilities"],
            help="Whether to regenerate the CodeWeaver capability modules. Default is False.",
        ),
    ] = False,
) -> None:
    """Get capabilities for a list of model names and add to JSON."""
    if models := get_mteb_model_metadata(names):
        if isinstance(models, ModelMeta):
            _ROOT.models[cast(ModelName, models.name)] = models
        else:
            _ROOT.models.update({cast(ModelName, model.name): model for model in models})
    else:
        console.print(f"[red]No models found for names: {names}[/red]")
        return
    _ROOT.aliases.update(alias_mapping or {})
    output = _ROOT.save()
    console.print(f"[green]Saved {_ROOT._json_path!s} with {output} characters.[/green]")
    if rewrite_cw_modules:
        generate_with_simplified([from_mteb_to_simplified(m) for m in models])


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
        if not file.strip():
            continue
        write_capabilities_file(maker, file)


@app.default
def get(names: Names) -> None:
    """Get capabilities for a list of model names."""
    models = get_mteb_model_metadata(names)
    simplified: Sequence[SimplifiedModelMeta] = [from_mteb_to_simplified(m) for m in models]
    generate_with_simplified(simplified)


if __name__ == "__main__":
    app()
