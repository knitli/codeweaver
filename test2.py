from typing import get_origin, Union
import types

def is_union(a):
    origin = get_origin(a)
    return origin is Union or origin is types.UnionType

print(is_union(Union[None]))
