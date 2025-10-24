<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Pydantic-Settings v2.11+ - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Configuration Architecture*

## Summary

**Feature Name**: Unified Configuration Management System  
**Feature Description**: Comprehensive configuration framework using pydantic-settings as the foundation for CodeWeaver's multi-source configuration management  
**Feature Goal**: Enable unified configuration management across FastMCP, pydantic-ai providers, and CodeWeaver-specific settings with flexible sources and environment variable mapping

**Primary External Surface(s)**: `BaseSettings` class, `SettingsConfigDict`, settings sources system (`PydanticBaseSettingsSource`), nested model support, environment variable mapping, custom settings sources

**Integration Confidence**: High - Mature API with extensive customization capabilities, proven patterns for complex integrations, and comprehensive documentation

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `BaseSettings` | Generic Class | `class BaseSettings(BaseModel)` | Primary configuration model with multi-source loading |
| `SettingsConfigDict` | Configuration Class | Model configuration container | Global settings behavior configuration |
| `PydanticBaseSettingsSource` | Abstract Base Class | Settings source interface | Base for custom configuration sources |
| `EnvSettingsSource` | Settings Source | Environment variables source | Loads from environment with prefixes/mapping |
| `DotEnvSettingsSource` | Settings Source | .env file source | Loads from dotenv files |
| `TomlConfigSettingsSource` | Settings Source | TOML file source | Loads from TOML configuration files |
| `PyprojectTomlConfigSettingsSource` | Settings Source | pyproject.toml source | Loads from pyproject.toml files |
| `JsonConfigSettingsSource` | Custom Source Example | JSON file source | Custom JSON configuration loading |
| `CliSettingsSource` | Settings Source | Command-line arguments source | CLI argument parsing and validation |

## Signatures

### Core BaseSettings Class

**Name**: `BaseSettings.__init__`  
**Import Path**: `from pydantic_settings import BaseSettings`  
**Concrete Path**: `pydantic_settings/main.py:BaseSettings.__init__`  
**Signature**: `def __init__(__pydantic_self__, **values: Any) -> None`

**Params**:
- `**values: Any` (optional) - Direct initialization values, takes precedence based on source priority
- `_env_file: Optional[Union[Path, str, List[Union[Path, str]]]]` - Override env file(s) at runtime
- `_env_file_encoding: Optional[str]` - Override env file encoding at runtime  
- `_secrets_dir: Optional[Union[Path, str, List[Union[Path, str]]]]` - Override secrets directory at runtime

**Returns**: `BaseSettings` instance  
**Errors**: `ValidationError` for invalid settings, `SettingsError` for source loading issues  
**Notes**: Supports runtime parameter overrides for flexible deployment scenarios

**Type Information**:
```python
class BaseSettings(BaseModel):
    model_config: SettingsConfigDict = SettingsConfigDict()
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources and their priority order"""
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)
```

### Settings Configuration

**Name**: `SettingsConfigDict`  
**Import Path**: `from pydantic_settings import SettingsConfigDict`  
**Signature**: Configuration dictionary for global settings behavior

**Key Parameters**:
- `env_prefix: str = ""` - Global prefix for environment variables
- `env_file: Optional[Union[Path, str, List[Union[Path, str]]]] = None` - Dotenv file path(s)
- `env_file_encoding: Optional[str] = None` - Dotenv file encoding
- `env_nested_delimiter: Optional[str] = None` - Delimiter for nested environment variables
- `env_nested_max_split: int = -1` - Maximum nesting depth for environment parsing
- `secrets_dir: Optional[Union[Path, str, List[Union[Path, str]]]] = None` - Directory for secret files
- `case_sensitive: bool = True` - Case sensitivity for environment variable matching
- `toml_file: Optional[Union[Path, str, List[Union[Path, str]]]] = None` - TOML configuration file(s)
- `pyproject_toml_table_header: tuple[str, ...] = ("tool", "pydantic-settings")` - TOML table location
- `nested_model_default_partial_update: bool = True` - Partial update behavior for nested models
- `cli_parse_args: bool = False` - Enable CLI argument parsing
- `validate_default: bool = True` - Validate default values

### Custom Settings Source Interface

**Name**: `PydanticBaseSettingsSource`  
**Import Path**: `from pydantic_settings import PydanticBaseSettingsSource`  
**Signature**: Abstract base class for custom settings sources

**Required Methods**:
```python
class PydanticBaseSettingsSource:
    def __init__(self, settings_cls: type[BaseSettings]) -> None: ...
    
    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str
    ) -> tuple[Any, str, bool]:
        """Get field value from this source
        Returns: (value, source_key, value_is_complex)
        """
        
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool
    ) -> Any:
        """Prepare/transform field value before validation"""
        
    def __call__(self) -> dict[str, Any]:
        """Return all settings from this source"""
```

### Environment Variable Mapping

**Name**: Environment Variable Processing  
**Signature**: Flexible environment variable to field mapping

**Mapping Rules**:
```python
# Basic mapping with prefix
env_prefix = "CODEWEAVER_"  # Field 'database_url' → 'CODEWEAVER_DATABASE_URL'

# Nested model mapping with delimiter
env_nested_delimiter = "__"  # Field 'database.password' → 'DATABASE__PASSWORD'

# Combined prefix + nested
# Field 'providers.voyage.api_key' → 'CODEWEAVER_PROVIDERS__VOYAGE__API_KEY'

# Alias override (bypasses prefix)
api_key: str = Field(alias='CUSTOM_API_KEY')  # Reads exactly 'CUSTOM_API_KEY'
```

## Type Graph

```
BaseSettings -> extends -> BaseModel
BaseSettings -> contains -> SettingsConfigDict
BaseSettings -> uses -> tuple[PydanticBaseSettingsSource, ...]

SettingsConfigDict -> configures -> EnvSettingsSource
SettingsConfigDict -> configures -> DotEnvSettingsSource  
SettingsConfigDict -> configures -> TomlConfigSettingsSource
SettingsConfigDict -> configures -> FileSecretSettingsSource

PydanticBaseSettingsSource -> implemented_by -> EnvSettingsSource
PydanticBaseSettingsSource -> implemented_by -> DotEnvSettingsSource
PydanticBaseSettingsSource -> implemented_by -> TomlConfigSettingsSource
PydanticBaseSettingsSource -> implemented_by -> Custom[JsonConfigSettingsSource]
PydanticBaseSettingsSource -> implemented_by -> Custom[AWSSecretsManagerSettingsSource]
PydanticBaseSettingsSource -> implemented_by -> Custom[AzureKeyVaultSettingsSource]
PydanticBaseSettingsSource -> implemented_by -> Custom[GoogleSecretManagerSettingsSource]

BaseSettings -> supports -> BaseModel (nested models)
BaseSettings -> supports -> Field (validation and aliases)
BaseSettings -> supports -> Union types
BaseSettings -> supports -> Optional types
BaseSettings -> supports -> complex types (List, Dict, etc.)
```

## Request/Response Schemas

### Multi-Source Configuration Flow

**Configuration Loading Process**:
```python
# 1. Source Priority (default order)
sources = [
    init_settings,      # Direct initialization arguments
    env_settings,       # Environment variables  
    dotenv_settings,    # .env files
    file_secret_settings # Secret files
]

# 2. Field Resolution Process
for source in sources:
    if source.has_field(field_name):
        value = source.get_field_value(field_name)
        prepared_value = source.prepare_field_value(field_name, value)
        if prepared_value is not None:
            return prepared_value  # First non-None value wins
```

### Environment Variable Schema

**Environment Variable Structure**:
```python
# Flat field
CODEWEAVER_DATABASE_URL = "postgresql://..."

# Nested model with delimiter  
CODEWEAVER_VECTOR_STORE__URL = "http://localhost:6333"
CODEWEAVER_VECTOR_STORE__COLLECTION_NAME = "codebase"
CODEWEAVER_VECTOR_STORE__API_KEY = "secret_key"

# Complex type as JSON
CODEWEAVER_PROVIDERS = '{"voyage": {"api_key": "key"}, "qdrant": {"url": "http://localhost:6333"}}'

# List as JSON or comma-separated
CODEWEAVER_IGNORE_PATTERNS = '["*.pyc", "*.log"]'
CODEWEAVER_IGNORE_PATTERNS = "*.pyc,*.log"  # Alternative format
```

### TOML Configuration Schema

**TOML File Structure**:
```toml
# Basic settings
server_name = "CodeWeaver"
max_tokens = 10000

# Nested model
[vector_store]
url = "http://localhost:6333"  
collection_name = "codebase"
timeout = 30

# Provider configuration
[[providers]]
kind = "embedding"
name = "voyage"
api_key = "your_key"
model = "voyage-code-3"

[[providers]]
kind = "vector_store" 
name = "qdrant"
url = "http://localhost:6333"
```

## Patterns

### Multi-Source Integration Pattern

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class CodeWeaverSettings(BaseSettings):
    """Unified configuration for CodeWeaver with multiple sources"""
    
    model_config = SettingsConfigDict(
        env_prefix="CODEWEAVER_",
        env_nested_delimiter="__",
        env_file=[".env", ".env.local", ".env.prod"],
        toml_file=["pyproject.toml", ".codeweaver.toml"],
        secrets_dir="/var/run/secrets",
        nested_model_default_partial_update=True,
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server settings
    server_name: str = "CodeWeaver"
    version: str = "0.1.0"
    debug: bool = False
    
    # Nested provider configuration
    providers: ProviderConfig = ProviderConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
```

### Custom Settings Source Pattern

```python
from pathlib import Path
import json
from typing import Any
from pydantic.fields import FieldInfo
from pydantic_settings import PydanticBaseSettingsSource

class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom JSON configuration source"""
    
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        json_file: Optional[Path] = None,
        json_file_encoding: Optional[str] = None,
    ):
        super().__init__(settings_cls)
        self.json_file = json_file or Path("config.json")
        self.json_file_encoding = json_file_encoding or "utf-8"
    
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        if not self.json_file.exists():
            return None, field_name, False
            
        try:
            content = self.json_file.read_text(encoding=self.json_file_encoding)
            data = json.loads(content)
            value = data.get(field_name)
            return value, field_name, isinstance(value, (dict, list))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, field_name, False
    
    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value
    
    def __call__(self) -> dict[str, Any]:
        if not self.json_file.exists():
            return {}
            
        try:
            content = self.json_file.read_text(encoding=self.json_file_encoding)
            return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
```

### Provider Configuration Pattern

```python
from typing import Literal, Union, Optional
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

class BaseProviderConfig(BaseModel):
    """Base configuration for all providers"""
    name: str
    enabled: bool = True
    timeout: int = 30
    retries: int = 3

class VoyageEmbeddingConfig(BaseProviderConfig):
    """Voyage AI embedding provider configuration"""
    provider_type: Literal["voyage"] = "voyage"
    api_key: str = Field(..., description="Voyage AI API key")
    model: str = "voyage-code-3"
    batch_size: int = 100

class OpenAIEmbeddingConfig(BaseProviderConfig):
    """OpenAI embedding provider configuration"""
    provider_type: Literal["openai"] = "openai"
    api_key: str = Field(..., description="OpenAI API key")
    model: str = "text-embedding-3-small"
    dimensions: Optional[int] = None

class QdrantConfig(BaseProviderConfig):
    """Qdrant vector store configuration"""
    provider_type: Literal["qdrant"] = "qdrant"
    url: str = "http://localhost:6333"
    collection_name: str = "codebase"
    vector_size: int = 1536

# Union type for provider configs
ProviderConfig = Union[
    VoyageEmbeddingConfig,
    OpenAIEmbeddingConfig, 
    QdrantConfig
]

class CodeWeaverSettings(BaseSettings):
    """Main settings with provider configuration"""
    providers: List[ProviderConfig] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def validate_providers(self):
        """Ensure required providers are configured"""
        provider_types = {p.provider_type for p in self.providers}
        
        if not any(t in provider_types for t in ["voyage", "openai"]):
            raise ValueError("At least one embedding provider required")
            
        if "qdrant" not in provider_types:
            raise ValueError("Vector store provider required")
            
        return self
```

### Settings Source Customization Pattern

```python
class CodeWeaverSettings(BaseSettings):
    """CodeWeaver settings with custom source priority"""
    
    # Configuration fields...
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Custom source priority for CodeWeaver"""
        
        # Create custom sources
        json_source = JsonConfigSettingsSource(settings_cls)
        toml_source = TomlConfigSettingsSource(settings_cls)
        
        # Custom priority: init > env > JSON > TOML > dotenv > secrets
        return (
            init_settings,      # Runtime overrides (highest priority)
            env_settings,       # Environment variables  
            json_source,        # JSON config files
            toml_source,        # TOML config files
            dotenv_settings,    # .env files
            file_secret_settings # Secret files (lowest priority)
        )
```

## Differences vs Project Requirements

### Alignment Strengths

1. **Multi-Source Configuration**: Perfect match for CodeWeaver's complex configuration needs (FastMCP settings, pydantic-ai providers, CodeWeaver-specific settings)

2. **Nested Model Support**: Native support for complex nested configurations with environment variable mapping via `env_nested_delimiter`

3. **Flexible Integration**: Custom settings sources enable integration with FastMCP's BaseSettings and pydantic-ai provider configurations

4. **Environment Variable Flexibility**: Comprehensive mapping options support the unified `CODEWEAVER_*` environment variable strategy

5. **Runtime Configuration**: Support for runtime parameter overrides enables flexible deployment scenarios

6. **Type Safety**: Full pydantic validation ensures type-safe configuration across all sources

7. **Secret Management**: Built-in support for Docker secrets and cloud secret managers aligns with enterprise deployment requirements

### FastMCP Integration Strategy

**Recommended Approach**: Composition over inheritance with unified environment variables

```python
from fastmcp.settings import Settings as FastMCPSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class CodeWeaverSettings(BaseSettings):
    """Unified CodeWeaver settings"""
    
    model_config = SettingsConfigDict(
        env_prefix="CODEWEAVER_",
        env_nested_delimiter="__",
        # Map CODEWEAVER_* to FastMCP equivalent internally
    )
    
    # CodeWeaver-specific settings
    max_tokens: int = 10000
    vector_store: VectorStoreConfig
    providers: List[ProviderConfig]
    
    # FastMCP settings via nested model
    fastmcp: FastMCPSettings = FastMCPSettings()
    
    @model_validator(mode='after')
    def sync_fastmcp_settings(self):
        """Sync CodeWeaver settings to FastMCP format"""
        # Map unified settings to FastMCP structure
        # e.g., self.fastmcp.server_name = self.server_name
        return self
```

### Pydantic-AI Provider Integration Strategy

**Recommended Approach**: Custom settings source for provider configuration

```python
from pydantic_ai import OpenAIProvider, AnthropicProvider
from typing import Dict, Any

class PydanticAIProviderSource(PydanticBaseSettingsSource):
    """Custom source for pydantic-ai provider configuration"""
    
    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._provider_mapping = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            # ... other providers
        }
    
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Map CodeWeaver provider config to pydantic-ai providers"""
        if field_name == "pydantic_ai_providers":
            # Transform CodeWeaver provider configs to pydantic-ai format
            providers = self._build_provider_instances()
            return providers, field_name, True
        return None, field_name, False
    
    def _build_provider_instances(self) -> Dict[str, Any]:
        """Build pydantic-ai provider instances from CodeWeaver config"""
        # Implementation maps CodeWeaver providers to pydantic-ai providers
        pass

class CodeWeaverSettings(BaseSettings):
    """Settings with pydantic-ai integration"""
    
    # CodeWeaver provider configs
    providers: List[ProviderConfig]
    
    # Generated pydantic-ai providers (populated by custom source)
    pydantic_ai_providers: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (
            init_settings,
            PydanticAIProviderSource(settings_cls),  # Custom provider mapping
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
```

## Blocking Questions

1. **Settings Inheritance Strategy**: Should CodeWeaver inherit from FastMCP's BaseSettings or use composition? Composition provides better isolation but requires mapping logic.

2. **Environment Variable Translation**: How should `CODEWEAVER_*` environment variables be mapped to FastMCP's expected `FASTMCP_*` format? Custom source or model validator approach?

3. **Provider Configuration Persistence**: Should pydantic-ai provider instances be cached/persisted or rebuilt on each settings reload? Performance vs. flexibility trade-off.

4. **Configuration File Precedence**: What should be the precedence order for multiple TOML files (pyproject.toml vs .codeweaver.toml vs config.toml)?

5. **Runtime Configuration Updates**: Does CodeWeaver need hot-reload capability for configuration changes, or is restart acceptable?

## Non-blocking Questions

1. **Performance Characteristics**: What are the performance implications of multiple settings sources with complex nested models?

2. **Configuration Validation**: Should configuration validation happen at startup or lazily when settings are accessed?

3. **Secret Management Strategy**: Which secret management approach (Docker secrets, cloud providers, or custom) should be the primary recommendation?

4. **CLI Integration**: How should pydantic-settings CLI capabilities integrate with cyclopts for CodeWeaver's CLI interface?

## Sources

[Context7 Official Documentation | Context7 ID: /pydantic/pydantic-settings | Reliability: 5]
- Core API patterns and BaseSettings usage
- Settings sources customization and priority system  
- Environment variable mapping and nested model support
- Custom settings source implementation patterns
- Integration examples with cloud services and secret management
- CLI integration patterns and configuration file handling

[Pydantic-Settings GitHub Repository | https://github.com/pydantic/pydantic-settings | Reliability: 5]  
- Source code implementation details and patterns
- Advanced configuration examples and edge cases
- Integration patterns with other pydantic ecosystem packages
- Custom settings source implementations

[Pydantic-Settings Documentation | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | Reliability: 5]
- Complete API reference and configuration options
- Best practices for complex configuration scenarios  
- Integration guidance with FastAPI/FastMCP patterns
- Performance considerations and optimization strategies

---

*This research provides comprehensive API intelligence for integrating pydantic-settings into CodeWeaver's unified configuration architecture. All patterns address the specific questions raised in FastMCP and pydantic-ai research, providing clear recommendations for composition-based integration strategies that maintain type safety and flexibility while avoiding over-abstraction.*