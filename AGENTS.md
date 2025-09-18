<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# AGENT GUIDELINES: Working on CodeWeaver

## Code Style

**Always review [CODE_STYLE.md](./CODE_STYLE.md) before writing or editing code.**

Channel @tiangolo's FastAPI architectural patterns.

## Context Management

CodeWeaver is a large codebase. Manage your token usage effectively:

### Best Practices
- Load only necessary files/sections using targeted searches
- For large-scale tasks: delegate to other agents or write automation scripts
- Use scripts for repetitive changes (linting fixes, import updates)

### Avoid
- Commands that dump large outputs unless writing to files (then search files, don't read directly)
- Tools without output limiting - always apply filters
- Processing many files simultaneously

### Strategy
Delegate high-context tasks with detailed instructions. Focus on high-level coordination while tools handle details.

## Core Rules

**Golden Rule**: Do exactly what the user asks. No more, no less. If unclear, ask questions.

### Red Flags 🚩

Stop and investigate when:

- API behavior differs from expectations
- Files/functions aren't where expected
- Code behavior contradicts documentation

### Red Flag Response Protocol

1. **Stop** current work
2. **Review** your understanding and plans
3. **Assess** using sequential-thinking tool:
   - Is approach consistent with requirements?
   - Do you have sufficient information?
   - Is the task ambiguous?
   - Could user have made simple error (typo, path)?
   - Is documentation outdated?
   - Did context limits cut relevant details?
4. **Research**:
   - Test hypothesis if possible
   - Use task tool for agent research
   - Internal issues: search files for pattern changes
   - External APIs: use context7/tavily for version-specific info
   - If still unclear: ask user for clarification

### Never Do

- Create workarounds without explicit user authorization
- Write placeholder/mock/toy versions
- Use NotImplementedError or TODO shortcuts
- Change project scope/goals independently

**Bottom line**: No code beats bad code.

### When Stuck

If you need more information or the task is larger/more complex than expected: **Ask the user for guidance**.

## Documentation

Priority order for documentation:

1. **Getting Started**: <5 minute install and first run
2. **Build & Configure**: Customization, extensions, platform development
3. **Contributors**: Contribution guidelines and internal documentation

## Brand Voice & Terminology

### Mission

Bridge the gap between human expectations and AI agent capabilities through "exquisite context." Create beneficial cycles where AI-first tools enhance both agent and human capabilities.

### User Terms

- **Agent/AI Agent** (not "model", "LLM", "tool")

  - **Developer's Agent**: Focused on developer tasks
  - **Context Agent**: Internal agents delivering information

- **Developer/End User**: People using CodeWeaver

  - **Developer User**: Uses CodeWeaver as development tool
  - **Platform Developer**: Builds with/extends CodeWeaver

- **Us**: First person plural (not "Knitli" or "team")
- **Contributors**: External contributors when distinction needed

### Core Values

- **Simplicity**: Transform complexity into clarity, eliminate jargon
- **Humanity**: Enhance human creativity, design people-first
- **Utility**: Solve real problems, meet users where they are
- **Integration**: Power through synthesis, connect disparate elements

### Personality

**We are**: Approachable, thoughtful, clear, empowering, purposeful

**We aren't**: Intimidating, unnecessarily complex, cold, AI-for-AI's-sake

### Communication Style

- Plain language accessible to all skill levels
- Simple examples with visual aids
- Conversational and human, not robotic
- Honest about capabilities and limitations
- Direct focus on user needs and goals

### Vision & Success Metrics

**Vision**: AI tools accessible to everyone, enhancing (not replacing) human creativity
**Success**: User empowerment, accessibility, reduced complexity, workflow integration
