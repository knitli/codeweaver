<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Skills

This directory is reserved for future Agent Skills that will extend CodeWeaver's capabilities.

## Coming Soon

We're planning to add skills for:
- **Code exploration workflows**: Guided codebase discovery
- **Architecture analysis**: Understanding system structure
- **Refactoring assistance**: Code improvement patterns
- **Documentation generation**: Context-aware docs

## Agent Skills Standard

Skills follow the [Agent Skills](https://agentskills.io) open standard, making them compatible with:
- Claude Code
- Cursor
- Windsurf
- Gemini CLI
- GitHub Copilot
- And other Agent Skills-compatible tools

## Contributing

Interested in contributing skills? Open a [plugin contribution issue](https://github.com/knitli/codeweaver/issues/new?template=plugin-contribution.yml) to propose a new skill or track progress on planned skills.

## Structure

Each skill should follow this structure:
```
skills/
  my-skill/
    SKILL.md          # Core prompt (YAML frontmatter + Markdown)
    scripts/          # Executable code
    references/       # Supporting documentation
    assets/           # Templates and files
```

See [Agent Skills Specification](https://agentskills.io/specification) for details.
