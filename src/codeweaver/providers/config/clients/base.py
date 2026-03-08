# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base ClientOptions for all provider clients."""

from __future__ import annotations

import logging
import os

from typing import TYPE_CHECKING, Any

from beartype.typing import ClassVar
from pydantic import AnyUrl, ConfigDict, SecretStr, model_validator

from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel
from codeweaver.core.types.provider import Provider


if TYPE_CHECKING:
    from codeweaver.core.types.provider import SDKClient


logger = logging.getLogger(__name__)


class ClientOptions(BasedModel):
    """A base class for provider client options.

    Client options are specific to the underlying SDK client that's used. They are not
    necessarily the same as the *provider*. The provider is who you pay, while the client
    if what you use to connect. For the most part, this is intuitive but there are some
    exceptions. The biggest exception is Azure, which does not have its own provider class,
    because it instead uses either Cohere or OpenAI providers. You're connecting to and paying Azure,
    but using the correct provider class for what you're trying to do.

    The standard way to pass client options to a provider is with the `as_settings()` method, which provides a kwargs dictionary.
    """

    model_config = BASEDMODEL_CONFIG | ConfigDict(frozen=True, from_attributes=True)
    _core_provider: ClassVar[Provider] = Provider.NOT_SET
    _providers: ClassVar[tuple[Provider, ...]] = ()

    def __init__(self, **data: Any) -> None:
        """Initialize the ClientOptions."""
        from codeweaver.core.di import get_container

        try:
            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Dependency injection container not available, skipping registration of ClientOptions: %s",
                e,
            )
        # Remove backup-related parameters if present (for backward compatibility)
        data.pop("_as_backup", None)

        object.__setattr__(self, "_core_provider", data.pop("_core_provider", Provider.NOT_SET))
        object.__setattr__(self, "_providers", data.pop("_providers", ()))
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _handle_env_vars(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Handle environment variables before initialization."""
        env_vars = cls.assemble_env_vars()
        if values and not isinstance(values, dict):
            values = values.model_dump()
        return env_vars | (values or {})

    @staticmethod
    def _filter_values(value: Any) -> Any:
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return str(value) if isinstance(value, AnyUrl) else value

    def as_settings(self) -> dict[str, Any]:
        """Return the client options as a dictionary suitable for passing as settings to the client constructor."""
        settings = self.model_dump(
            exclude={"_core_provider", "_providers", "tag", "advanced_http_options"}
        )
        return {k: self._filter_values(v) for k, v in settings.items()}

    @property
    def core_provider(self) -> Provider:
        """Return the core provider this client options class is most associated with."""
        return self._core_provider

    @property
    def providers(self) -> tuple[Provider, ...]:
        """Return the providers this client options class can apply to."""
        return self._providers

    @classmethod
    def _client_env_vars(cls) -> dict[str, tuple[str, ...] | dict[str, Any]]:
        # sourcery skip: low-code-quality
        """Return a dictionary of environment variables for the client options, mapping client variable names to the environment variable name."""
        # Access _core_provider from class __dict__ to avoid pydantic descriptor issues
        core_provider = cls.__dict__.get("_core_provider", Provider.NOT_SET)
        if core_provider == Provider.NOT_SET:
            # Fallback to parent class if not set in current class
            for base in cls.__mro__[1:]:
                if "_core_provider" in base.__dict__:
                    core_provider = base.__dict__["_core_provider"]
                    break
        env_vars = core_provider.all_envs_for_client(core_provider.variable)
        mapped_vars = {}
        fields = tuple(cls.model_fields)
        for env_var in env_vars:
            variables = env_var.variables if "variables" in env_var._asdict() else ()
            if (
                (
                    var_name := env_var.variable_name
                    if "variable_name" in env_var._asdict()
                    else None
                )
                and variables
                and (
                    client_var := next(
                        (var.variable for var in variables if var.dest == "client"), None
                    )
                )
            ):
                mapped_vars[var_name] = {client_var.variable: env_var.env}
            elif var_name and var_name in fields:
                mapped_vars[var_name] = (
                    (env_var.env,)
                    if var_name not in mapped_vars
                    else (mapped_vars[var_name] + (env_var.env,))
                )
            elif variables:
                for var in variables:
                    if var.dest == "client" and var.variable in fields:
                        mapped_vars[var.variable] = (
                            (env_var.env,)
                            if var.variable not in mapped_vars
                            else (mapped_vars[var.variable] + (env_var.env,))
                        )
        return mapped_vars

    @classmethod
    def _handle_env_tuple(cls, var_name: str, env_var_names: tuple[str, ...]) -> dict[str, Any]:
        if var_name not in cls.model_fields:
            return {}
        if value := next(
            (os.getenv(env_var) for env_var in env_var_names if os.getenv(env_var)), None
        ):
            return {var_name: value}
        return {}

    @classmethod
    def _handle_env_dict(cls, var_name: str, env_var_names: dict[str, Any]) -> dict[str, Any]:
        if var_name not in cls.model_fields:
            return {}
        for client_var, env_var in env_var_names.items():
            if (value := os.getenv(env_var)) and client_var == var_name:
                return {var_name: value}
        return {}

    @classmethod
    def assemble_env_vars(cls) -> dict[str, Any]:
        """Apply environment variables to the client options."""
        env_vars = cls._client_env_vars()
        response_map: dict[str, Any] = {}
        for var_name, env_var_names in env_vars.items():
            if var_name not in cls.model_fields:
                continue
            if isinstance(env_var_names, tuple):
                response_map |= cls._handle_env_tuple(var_name, env_var_names)
                continue
            # it's a dictionary
            response_map |= cls._handle_env_dict(var_name, env_var_names)
        return response_map if response_map and response_map.values() else {}

    @property
    def sdk_client(self) -> SDKClient:
        """Return an instance of the underlying SDK client, initialized with the client options."""
        return SDKClient.from_string(self.core_provider.variable)


__all__ = ("ClientOptions",)
