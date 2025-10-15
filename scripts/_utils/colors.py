#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: lilydjwg
# Licensing: lilydjwg doesn't add licenses to most of her(?) gists and repos, but when she does, it's MIT. So we're assuming MIT.
# Usually not something you should do, but this is a test script for ANSI escape codes, so it's not like it's important...
# And she has a slew of public gists and repos, so it's probably safe to assume she wants them to be used.
"""Show terminal colors and attributes. A test script for ANSI escape codes. Based on [this](https://gist.github.com/lilydjwg/fdeaf79e921c2f413f44b6f613f6ad53) gist by lilydjwg."""

from collections.abc import Callable
from functools import partial
from typing import Literal


type ColorWeight = Literal[0, 1, 2, "1;2"]

type PartialColorFunc = Callable[[int], None]
type SepFunc = Callable[[int], None]


def colors16() -> None:
    """Show basic 16 colors, foreground & background."""
    for bold in [0, 1]:
        for i in range(30, 38):
            for j in range(40, 48):
                print(f"\x1b[{bold};{i};{j}m {bold};{i};{j} |\x1b[0m", end="")
            print()
        print()

    for bold in [0, 1]:
        for i in range(90, 98):
            for j in range(100, 108):
                print(f"\x1b[{bold};{i};{j}m {bold};{i};{j} |\x1b[0m", end="")
            print()
        print()


def color1(c: int, n: ColorWeight = 0) -> None:
    """n: 0 normal, 1 bold, 2 dim, '1;2' bold dim."""
    print(f"\x1b[{n};38;5;{c}m{c:4}\x1b[0m", end="")


def color1_sep(c: int) -> None:
    """Separate every 6 colors, and a newline every 18 colors."""
    if (c - 15) % 18 == 0:
        print()


def color2(c: int) -> None:
    """Show color 2."""
    print(f"\x1b[48;5;{c}m  \x1b[0m", end="")


def color2_sep(c: int) -> None:
    """Separate every 6 colors, and a newline every 36 colors."""
    if (c - 15) % 36 == 0:
        print()
    elif (c - 15) % 6 == 0:
        print(" ", end="")


def colors256(
    color: PartialColorFunc, sepfunc: SepFunc
) -> None:  # sourcery skip: extract-duplicate-method
    """Show 256 colors."""
    for i in range(8):
        color(i)
    print()
    for i in range(8, 16):
        color(i)
    print("\n")

    for i in range(16, 232):
        color(i)
        sepfunc(i)
    print()

    for i in range(232, 256):
        color(i)
    print("\n")


def colors_gradient() -> None:
    """Show true colors gradient."""
    s = "/\\" * 40
    for col in range(77):
        r = 255 - col * 255 // 76
        g = col * 510 // 76
        b = col * 255 // 76
        if g > 255:
            g = 510 - g
        print(
            f"\x1b[48;2;{r};{g};{b}m\x1b[38;2;{255 - r};{255 - g};{255 - b}m{s[col]}\x1b[0m", end=""
        )
    print()


def other_attributes() -> None:
    """Show other attributes."""
    # https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_(Select_Graphics_Representation)_parameters
    for i in range(10):
        print(f" \x1b[{i}mSGR {i:2}\x1b[m", end=" ")
    print(" \x1b[53mSGR 53\x1b[m", end=" ")  # overline
    print("\n")
    # https://askubuntu.com/a/985386/235132
    for i in range(1, 6):
        print(f" \x1b[4:{i}mSGR 4:{i}\x1b[m", end=" ")
    print(" \x1b[21mSGR 21\x1b[m", end=" ")

    print(" \x1b[4:3m\x1b[58;2;135;0;255mtruecolor underline\x1b[59m\x1b[4:0m", end=" ")
    print(" \x1b]8;;https://askubuntu.com/a/985386/235132\x1b\\hyperlink\x1b]8;;\x1b\\")


def main() -> None:  # sourcery skip: extract-duplicate-method
    """Main function."""
    print("basic 16 colors, foreground & background:\n")
    colors16()

    print("256 colors:\n")
    colors256(color1, color1_sep)

    print("256 colors, bold:\n")
    colors256(partial(color1, n=1), color1_sep)

    print("256 colors, dim:\n")
    colors256(partial(color1, n=2), color1_sep)

    print("256 colors, bold dim:\n")
    colors256(partial(color1, n="1;2"), color1_sep)

    print("256 colors, solid background:\n")
    colors256(color2, color2_sep)

    print("true colors gradient:\n")
    colors_gradient()

    print("other attributes:\n")
    other_attributes()


if __name__ == "__main__":
    main()
