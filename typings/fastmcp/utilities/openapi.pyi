# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import Any, Literal, TypeVar

from fastmcp.utilities.types import FastMCPBaseModel
from openapi_pydantic import (
    OpenAPI,
    Operation,
    Parameter,
    PathItem,
    Reference,
    RequestBody,
    Response,
    Schema,
)
from openapi_pydantic.v3.v3_0 import OpenAPI as OpenAPI_30
from openapi_pydantic.v3.v3_0 import Operation as Operation_30
from openapi_pydantic.v3.v3_0 import Parameter as Parameter_30
from openapi_pydantic.v3.v3_0 import PathItem as PathItem_30
from openapi_pydantic.v3.v3_0 import Reference as Reference_30
from openapi_pydantic.v3.v3_0 import RequestBody as RequestBody_30
from openapi_pydantic.v3.v3_0 import Response as Response_30
from openapi_pydantic.v3.v3_0 import Schema as Schema_30

logger = ...
type HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"]
type ParameterLocation = Literal["path", "query", "header", "cookie"]
type JsonSchema = dict[str, Any]

def format_array_parameter(
    values: list, parameter_name: str, is_query_parameter: bool = ...
) -> str | list:
    ...

def format_deep_object_parameter(param_value: dict, parameter_name: str) -> dict[str, str]:
    ...

class ParameterInfo(FastMCPBaseModel):


    name: str
    location: ParameterLocation
    required: bool = ...
    schema_: JsonSchema = ...
    description: str | None = ...
    explode: bool | None = ...
    style: str | None = ...

class RequestBodyInfo(FastMCPBaseModel):


    required: bool = ...
    content_schema: dict[str, JsonSchema] = ...
    description: str | None = ...

class ResponseInfo(FastMCPBaseModel):


    description: str | None = ...
    content_schema: dict[str, JsonSchema] = ...

class HTTPRoute(FastMCPBaseModel):


    path: str
    method: HttpMethod
    operation_id: str | None = ...
    summary: str | None = ...
    description: str | None = ...
    tags: list[str] = ...
    parameters: list[ParameterInfo] = ...
    request_body: RequestBodyInfo | None = ...
    responses: dict[str, ResponseInfo] = ...
    schema_definitions: dict[str, JsonSchema] = ...
    extensions: dict[str, Any] = ...

__all__ = [
    "HTTPRoute",
    "HttpMethod",
    "JsonSchema",
    "ParameterInfo",
    "ParameterLocation",
    "RequestBodyInfo",
    "ResponseInfo",
    "extract_output_schema_from_responses",
    "format_deep_object_parameter",
    "parse_openapi_to_http_routes",
]
TOpenAPI = TypeVar("TOpenAPI", OpenAPI, OpenAPI_30)
TSchema = TypeVar("TSchema", Schema, Schema_30)
TReference = TypeVar("TReference", Reference, Reference_30)
TParameter = TypeVar("TParameter", Parameter, Parameter_30)
TRequestBody = TypeVar("TRequestBody", RequestBody, RequestBody_30)
TResponse = TypeVar("TResponse", Response, Response_30)
TOperation = TypeVar("TOperation", Operation, Operation_30)
TPathItem = TypeVar("TPathItem", PathItem, PathItem_30)

def parse_openapi_to_http_routes(openapi_dict: dict[str, Any]) -> list[HTTPRoute]:
    ...

class OpenAPIParser[TOpenAPI: (OpenAPI, OpenAPI_30), TReference: (Reference, Reference_30), TSchema: (Schema, Schema_30), TParameter: (Parameter, Parameter_30), TRequestBody: (RequestBody, RequestBody_30), TResponse: (Response, Response_30), TOperation: (Operation, Operation_30), TPathItem: (PathItem, PathItem_30)]:

    def __init__(
        self,
        openapi: TOpenAPI,
        reference_cls: type[TReference],
        schema_cls: type[TSchema],
        parameter_cls: type[TParameter],
        request_body_cls: type[TRequestBody],
        response_cls: type[TResponse],
        operation_cls: type[TOperation],
        path_item_cls: type[TPathItem],
    ) -> None:
        ...

    def parse(self) -> list[HTTPRoute]:
        ...

def clean_schema_for_display(schema: JsonSchema | None) -> JsonSchema | None:
    ...

def generate_example_from_schema(schema: JsonSchema | None) -> Any:
    ...

def format_json_for_description(data: Any, indent: int = ...) -> str:
    ...

def format_description_with_responses(
    base_description: str,
    responses: dict[str, Any],
    parameters: list[ParameterInfo] | None = ...,
    request_body: RequestBodyInfo | None = ...,
) -> str:
    ...

def extract_output_schema_from_responses(
    responses: dict[str, ResponseInfo], schema_definitions: dict[str, Any] | None = ...
) -> dict[str, Any] | None:
    ...
