# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

class FastMCPError(Exception):
    ...


class ValidationError(FastMCPError):
    ...


class ResourceError(FastMCPError):
    ...


class ToolError(FastMCPError):
    ...


class PromptError(FastMCPError):
    ...


class InvalidSignature(Exception):
    ...


class ClientError(Exception):
    ...


class NotFoundError(Exception):
    ...


class DisabledError(Exception):
    ...

