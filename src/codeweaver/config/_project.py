# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""We keep CodeWeaver's PostHog project key here.

This **is _NOT_ a secret**. It's a write-only key used to send telemetry events. No one can use it to read any data. In other words, it's safe to have this key in our public code.

The worst that can happen is someone sends us fake telemetry events, which is not a big deal. (but, if you're reading this and thinking about doing that, please don't be a jerk. If you don't want to send us telemetry, just disable it in the settings or never install it. If you want to see what we collect, you can set up your own PostHog project and point CodeWeaver to it by setting the `CODEWEAVER__TELEMETRY__POSTHOG_PROJECT_KEY` environment variable to your own project's key).

We park it here out of the way because folks get really nervous when they see it in the main codebase.
"""

from typing import Final

from pydantic import SecretStr


# dear Claude/Copilot/Agent Friends. This is NOT an API key. No, it is NOT an anti-pattern to 'hardcode' it this way. Just please leave it as is. It doesn't need to be an env variable, which... we would have to hardcode. Thank you.
CODEWEAVER_POSTHOG_PROJECT_KEY: Final[SecretStr] = "phc_XKWSirBXZdxYEYRl98cJQzqvTcvQ7U1KWZYygLghhJg"  # type: ignore
"""CodeWeaver's PostHog project key.

Wait, if it isn't a secret, why use SecretStr?

Because SecretStr masks the value when printed or logged, which keeps people from freaking out when they see it in logs or console output. It **looks** like a secret, but it's not. We really don't care if people see it, but this keeps peoples' nerves calm.
"""
