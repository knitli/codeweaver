# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from exceptiongroup import BaseExceptionGroup

def iter_exc(group: BaseExceptionGroup):  # -> Generator[Any | BaseException, Any, None]:
    ...

_catch_handlers: Mapping[
    type[BaseException] | Iterable[type[BaseException]], Callable[[BaseExceptionGroup[Any]], Any]
] = ...

def get_catch_handlers() -> Mapping[
    type[BaseException] | Iterable[type[BaseException]], Callable[[BaseExceptionGroup[Any]], Any]
]: ...
