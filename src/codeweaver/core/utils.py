"""Internal helper utilities for the core package."""


def truncate_text(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """
    Truncate text to a maximum length, adding an ellipsis if truncated.

    Args:
        text: The input text to truncate.
        max_length: The maximum allowed length of the text (default: 100).
        ellipsis: The string to append if truncation occurs (default: "...").

    Returns:
        The truncated text if it exceeds max_length, otherwise the original text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(ellipsis)] + ellipsis


__all__ = ("truncate_text",)
