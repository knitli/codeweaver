# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

__all__ = [
    "AcceptedElicitation",
    "CancelledElicitation",
    "DeclinedElicitation",
    "ScalarElicitationType",
    "get_elicitation_schema",
]
logger = ...
T = TypeVar("T")

class AcceptedElicitation[T](BaseModel):


    action: Literal["accept"] = ...
    data: T

@dataclass
class ScalarElicitationType[T]:
    value: T

def get_elicitation_schema[T](response_type: type[T]) -> dict[str, Any]:
    ...

def validate_elicitation_json_schema(schema: dict[str, Any]) -> None:
    ...
