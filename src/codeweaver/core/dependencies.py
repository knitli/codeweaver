"""Core dependency types and factories."""

from typing import Annotated

from codeweaver.core.di import depends


type NoneDep = Annotated[None, depends(lambda: None)]

__all__ = ("NoneDep",)
