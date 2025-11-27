<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Project Management Scripts

Scripts for project management, contributor tracking, and cross-repository analysis.

## Scripts

### contributors.py

**Purpose**: Generate comprehensive contributor lists from CLA signatures across all Knitli repositories.

**Usage**:
```bash
# Generate markdown list
python scripts/project/contributors.py --format markdown

# Generate JSON data
python scripts/project/contributors.py --format json

# Generate CSV export
python scripts/project/contributors.py --format csv

# Per-repo breakdown
python scripts/project/contributors.py --by-repo

# Custom output path
python scripts/project/contributors.py --format markdown --output /path/to/CONTRIBUTORS.md
```

**Requirements**: Python 3.7+, GitHub CLI (`gh`)

**What it does**:
1. Clones `knitli/.github` repo temporarily
2. Reads all CLA signature files from `cla-signatures/`
3. Aggregates contributors across repos
4. Generates formatted output

**Data tracked**:
- GitHub username and ID
- Total contributions across all repos
- Which repos they've contributed to
- First contribution date
- Individual PR numbers
- Repository ID for cross-repo tracking

### generate-contributors-list.sh

**Purpose**: Bash version of the contributor list generator.

**Usage**:
```bash
./scripts/project/generate-contributors-list.sh markdown
./scripts/project/generate-contributors-list.sh json
./scripts/project/generate-contributors-list.sh csv
```

**Requirements**: bash, jq, GitHub CLI (`gh`)

**Features**: Same functionality as `contributors.py` but in pure bash.

## Background

These scripts integrate with the centralized CLA workflow stored in `knitli/.github`:
- CLA signatures are stored in `knitli/.github/cla-signatures/{repo-name}.json`
- Each signature includes `repoId` for cross-repository tracking
- Scripts aggregate data across all repositories for unified contributor lists

## Output Examples

### Markdown Format
```markdown
# Contributors

- [@contributor1](https://github.com/contributor1) - 3 contributions across 2 repos (`codeweaver`, `thread`)
- [@contributor2](https://github.com/contributor2) - 1 contribution across 1 repo (`codeweaver`)

## Statistics
- **Total Contributors**: 2
- **Total Contributions**: 4
```

### JSON Format
```json
{
  "generated_at": "2025-11-24T20:00:00Z",
  "total_contributors": 2,
  "contributors": [
    {
      "name": "contributor1",
      "id": 12345,
      "repos": ["codeweaver", "thread"],
      "total_contributions": 3
    }
  ]
}
```

## See Also

- [CLA Centralization Setup Guide](../../claudedocs/cla-centralization-setup.md)
- [Main Scripts README](../README.md)
