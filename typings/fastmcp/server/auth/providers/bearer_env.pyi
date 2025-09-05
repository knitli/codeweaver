# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from types import EllipsisType

from fastmcp.server.auth.providers.bearer import BearerAuthProvider
from pydantic_settings import BaseSettings

class EnvBearerAuthProviderSettings(BaseSettings):


    model_config = ...
    public_key: str | None = ...
    jwks_uri: str | None = ...
    issuer: str | None = ...
    algorithm: str | None = ...
    audience: str | None = ...
    required_scopes: list[str] | None = ...

class EnvBearerAuthProvider(BearerAuthProvider):

    def __init__(
        self,
        public_key: str | None | EllipsisType = ...,
        jwks_uri: str | None | EllipsisType = ...,
        issuer: str | None | EllipsisType = ...,
        algorithm: str | None | EllipsisType = ...,
        audience: str | None | EllipsisType = ...,
        required_scopes: list[str] | None | EllipsisType = ...,
    ) -> None:
        ...
