"""A class factory that creates backup namespaced providers for various services across CodeWeaver.

Why?

Most CodeWeaver providers are DI-managed singletons, which is the norm for any implementation that wants to maintain configuration consistency across multiple providers and complex interdependencies. An earlier design for backup systems relied on piling providers with multiple configurations and handling for switching between them. It was complex, nearly impossible to manage state effectively, and hard to reason about.

This factory approach allows us to create distinct backup providers that can operate independently of the main providers. Each backup provider can have its own configuration, state, and lifecycle, making it easier to manage backups without interfering with the primary operations of the services. The namespacing also make it easy to identify them by simply checking their name. Does it have `Backup` in its name? Then it's a backup provider.
"""

from __future__ import annotations

from typing import Any, cast

from codeweaver.core import TypeIs, get_container


def _is_backup_type[T: type, BackupT: type](parent: T, backup: BackupT) -> TypeIs[BackupT]:
    """One for the type checkers."""
    return issubclass(backup, parent)

def _register_backup_provider[BackupT: type](backup_class: BackupT, *, singleton: bool = True) -> None:
    """Register the backup provider class in the DI container."""
    container = get_container()
    container.register(backup_class, lambda: backup_class, singleton=singleton)

def create_backup_provider_class[T: type, BackupT: type](
    base_class: type, namespace: dict[str, Any], *, singleton: bool = True
) -> BackupT:
    """Dynamically create a backup provider class based on the given base class.

    Args:
        base_class (type): The base provider class to extend.

    Returns:
        type: A new class that extends the base class with backup-specific behavior.
    """
    class_name = f"Backup{base_class.__name__}"
    kwargs = {
            "__doc__": f"A backup provider class extending {base_class.__name__}.",
            "is_backup_provider": True,
        }
    new_class = type(
        class_name,
        (base_class,),
        namespace,
        **kwargs,
    )
    if _is_backup_type(base_class, new_class):
        _register_backup_provider(new_class, singleton=singleton)
        return cast(BackupT, new_class)
    raise TypeError(f"Created class {class_name} is not a subclass of {base_class.__name__}.")
