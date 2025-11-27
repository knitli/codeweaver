<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Privacy Policy

## We Care About Your Privacy 🔒

CodeWeaver collects minimal telemetry to help us make the tool better. This document explains what we collect, why, and how you can opt out. If anything's unclear, [email Adam](mailto:adam@knit.li) or post in the [forum](https://github.com/knitli/codeweaver/discussions).

---

## What We Collect 📊

**Usage Data** (anonymous):
- Commands you run (e.g., `cw search`, `cw index`)
- Error messages and crash reports
- Performance metrics (indexing speed, search latency)
- Feature usage patterns (which tools you and your AI agents use most)

**Technical Data**:
- Operating system and version
- Python version
- CodeWeaver version
- Project size (file count, lines of code)

**What We DON'T Collect** 🚫:
- Your actual code or file contents
- File names or directory structures
- API keys or credentials
- Personally identifiable information (PII)
- IP addresses or location data
- Anything inside your repositories

---

## Why We Collect It 🤔

We use this data to:
- **Fix bugs faster**: Crash reports help us identify and fix problems
- **Improve performance**: Metrics show us where to optimize
- **Prioritize features**: Usage patterns guide what to build next
- **Make better decisions**: Data beats guesswork

We're a small team trying to build something useful. This data helps us focus on what actually matters to you.

---

## How We Use It 🛠️

- **Internal analysis only**: We analyze data to improve CodeWeaver
- **No selling**: We will never sell your data to anyone, ever
- **No advertising**: We don't use it for ads or marketing
- **Aggregate only**: We look at patterns across all users, not individuals
- **Secure storage**: Data is encrypted and stored securely

---
## Third Parties 🧑‍🤝‍🧑

We don't provide any data to third parties except to process and store it.

We use [PostHog](https://posthog.com) as our telemetry service and data warehouse. They have great docs on how they process data if you want to know more.

---

## How Long We Keep It ⏰

- **Usage data**: 90 days, then automatically deleted
- **Crash reports**: 30 days, then automatically deleted
- **Aggregate metrics**: Indefinitely (no personal info, just stats like "average search time")

---

## How to Opt Out 🚪

You can disable telemetry anytime:

**Environment variable**
```bash
export CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true
```

**Config file** (`~/.config/codeweaver/codeweaver.toml`) or in the root of your project:
```toml
[telemetry]
disable_telemetry = true
```

Opting out doesn't affect functionality. CodeWeaver works exactly the same way.

## ...Opting In 🐀

**You can also *opt in* to more detailed telemetry.** If you do, we'll collect information on queries and results. 

**Query and result information really helps us refine CodeWeaver's core search capability.** If you do opt in:
- We can't garauntee the information *won't* be identifying because of the nature of queries and results
- We will screen out identifying information as best we can.
- Like our usual telemetry, we won't share it with anyone, and we'll appreciate you ::heart::

You can opt in with:

**Environment variable**:
```bash
export CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true
```

**Config file**:
```toml
[telemetry]
tools_over_privacy = true
```


---

## Your Rights 📜

You have the right to:
- **Opt out**: Disable telemetry completely (see above)
- **Ask questions**: Email us about what data we have
- **Request deletion**: We have no way of knowing what data is yours though... 
- **Be informed**: We'll update this policy if anything changes

---

## Changes to This Policy 🔄

If we update this policy, we'll:
- Post the new version on GitHub
- Update the version number in CodeWeaver
- Notify you in the release notes

Continued use of CodeWeaver after changes means you accept the updated policy.

---

## Open Source Transparency 👁️

CodeWeaver is open source, so you can see exactly what we collect:
- Check the telemetry code in the repository
- Inspect the data before it's sent
- Submit a PR to improve privacy

We believe in radical transparency. If something seems off, call us out.

---

## Legal Stuff 👩‍⚖️

- **Data Controller**: Knitli Inc., a Delaware corporation
- **Governing Law**: Delaware, USA
- **GDPR Compliance**: We don't process EU user data differently (we collect minimal data from everyone)
- **CCPA Compliance**: California residents have the right to opt out and request deletion (see above)

---

## Contact Us 💬

Questions, concerns, or just want to chat about privacy?

- **Email**: [adam@knit.li](mailto:adam@knit.li)
- **Forum**: [GitHub Discussions](https://github.com/knitli/codeweaver/discussions)
- **Issues**: [GitHub Issues](https://github.com/knitli/codeweaver/issues)

We're real people who care about doing the right thing. Don't hesitate to reach out.

---

## Thanks for trusting us with your data! 🙏

We take that responsibility seriously and promise to use it only to make CodeWeaver better for you.

---

**Last updated**: 2025-11-25
**Effective date**: 2025-11-25
