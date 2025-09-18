# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from dataclasses import dataclass
from typing import Any

from fastmcp.server.auth.auth import OAuthProvider
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import SecretStr
from typing_extensions import TypedDict

class JWKData(TypedDict, total=False):


    kty: str
    kid: str
    use: str
    alg: str
    n: str
    e: str
    x5c: list[str]
    x5t: str

class JWKSData(TypedDict):


    keys: list[JWKData]

@dataclass(frozen=True, kw_only=True, repr=False)
class RSAKeyPair:
    private_key: SecretStr
    public_key: str
    @classmethod
    def generate(cls) -> RSAKeyPair:
        ...

    def create_token(
        self,
        subject: str = ...,
        issuer: str = ...,
        audience: str | list[str] | None = ...,
        scopes: list[str] | None = ...,
        expires_in_seconds: int = ...,
        additional_claims: dict[str, Any] | None = ...,
        kid: str | None = ...,
    ) -> str:
        ...

class BearerAuthProvider(OAuthProvider):

    def __init__(
        self,
        public_key: str | None = ...,
        jwks_uri: str | None = ...,
        issuer: str | None = ...,
        algorithm: str | None = ...,
        audience: str | list[str] | None = ...,
        required_scopes: list[str] | None = ...,
    ) -> None:
        ...

    async def load_access_token(self, token: str) -> AccessToken | None:
        ...

    async def verify_token(self, token: str) -> AccessToken | None:
        ...

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None: ...
    async def register_client(self, client_info: OAuthClientInformationFull) -> None: ...
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str: ...
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None: ...
    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken: ...
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None: ...
    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken: ...
    async def revoke_token(self, token: AccessToken | RefreshToken) -> None: ...
