#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 Knitli Inc. <knitli@knit.li>
# SPDX-License-Identifier: MIT OR Apache-2.0
#
# Generate a comprehensive contributors list from CLA signatures across all repos
#
# Usage:
#   ./scripts/generate-contributors-list.sh [output-format]
#
# Formats:
#   markdown  - Generate CONTRIBUTORS.md (default)
#   json      - Generate contributors.json
#   csv       - Generate contributors.csv

set -euo pipefail

OUTPUT_FORMAT="${1:-markdown}"
TEMP_DIR=$(mktemp -d)
CLA_REPO="knitli/.github"
CLA_DIR="cla-signatures"

# Clone the .github repo to access CLA signatures
echo "📥 Fetching CLA signatures from ${CLA_REPO}..."
gh repo clone "${CLA_REPO}" "${TEMP_DIR}/.github" -- --depth 1 --quiet

cd "${TEMP_DIR}/.github/${CLA_DIR}"

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq is required but not installed"
    echo "Install: sudo apt-get install jq"
    exit 1
fi

# Aggregate all contributors across all signature files
echo "🔍 Processing signature files..."

# Create a combined JSON with repo information
ALL_CONTRIBUTORS=$(cat *.json 2>/dev/null | jq -s '
  # Flatten all signedContributors arrays
  [.[].signedContributors[]] |

  # Group by user ID to consolidate across repos
  group_by(.id) |

  # For each user, collect their repos and details
  map({
    name: .[0].name,
    id: .[0].id,
    first_contribution: ([.[].created_at] | min),
    total_contributions: length,
    repos: [.[].repoId] | unique,
    pull_requests: [.[].pullRequestNo]
  }) |

  # Sort by first contribution date
  sort_by(.first_contribution)
' || echo "[]")

CONTRIBUTOR_COUNT=$(echo "${ALL_CONTRIBUTORS}" | jq 'length')
echo "✅ Found ${CONTRIBUTOR_COUNT} unique contributors"

# Generate output based on format
case "${OUTPUT_FORMAT}" in
  markdown)
    OUTPUT_FILE="${TEMP_DIR}/CONTRIBUTORS.md"

    cat > "${OUTPUT_FILE}" << 'EOF'
# Contributors

Thank you to everyone who has contributed to Knitli projects! 🎉

This list is automatically generated from CLA signatures across all repositories.

## All Contributors

EOF

    echo "${ALL_CONTRIBUTORS}" | jq -r '.[] |
      "- [@\(.name)](https://github.com/\(.name)) - \(.total_contributions) contribution\(if .total_contributions > 1 then "s" else "" end) across \(.repos | length) repo\(if (.repos | length) > 1 then "s" else "" end)"
    ' >> "${OUTPUT_FILE}"

    cat >> "${OUTPUT_FILE}" << 'EOF'

## Statistics

EOF

    echo "- **Total Contributors**: ${CONTRIBUTOR_COUNT}" >> "${OUTPUT_FILE}"
    echo "- **Total Contributions**: $(echo "${ALL_CONTRIBUTORS}" | jq '[.[].total_contributions] | add')" >> "${OUTPUT_FILE}"
    echo "- **Generated**: $(date -u +%Y-%m-%d)" >> "${OUTPUT_FILE}"

    echo "📄 Generated: ${OUTPUT_FILE}"
    cat "${OUTPUT_FILE}"
    ;;

  json)
    OUTPUT_FILE="${TEMP_DIR}/contributors.json"
    echo "${ALL_CONTRIBUTORS}" | jq '{
      generated_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
      total_contributors: length,
      contributors: .
    }' > "${OUTPUT_FILE}"

    echo "📄 Generated: ${OUTPUT_FILE}"
    cat "${OUTPUT_FILE}" | jq
    ;;

  csv)
    OUTPUT_FILE="${TEMP_DIR}/contributors.csv"

    echo "name,github_url,id,first_contribution,total_contributions,repos" > "${OUTPUT_FILE}"
    echo "${ALL_CONTRIBUTORS}" | jq -r '.[] |
      [.name, "https://github.com/\(.name)", .id, .first_contribution, .total_contributions, (.repos | join(";"))] |
      @csv
    ' >> "${OUTPUT_FILE}"

    echo "📄 Generated: ${OUTPUT_FILE}"
    cat "${OUTPUT_FILE}"
    ;;

  *)
    echo "❌ Unknown format: ${OUTPUT_FORMAT}"
    echo "Valid formats: markdown, json, csv"
    exit 1
    ;;
esac

# Copy to original directory if we're in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    ORIGINAL_DIR=$(git rev-parse --show-toplevel)
    cp "${OUTPUT_FILE}" "${ORIGINAL_DIR}/"
    echo "✅ Copied to: ${ORIGINAL_DIR}/$(basename "${OUTPUT_FILE}")"
fi

# Cleanup
rm -rf "${TEMP_DIR}"

echo "✨ Done!"
