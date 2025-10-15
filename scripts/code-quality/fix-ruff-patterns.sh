#!/bin/bash

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# fix-ruff-patterns.sh - Apply comprehensive fixes for ruff violations
# Applies fixes for TRY401, G004, and TRY300 patterns in Python code
# These are very common anti-patterns that ruff can't fix automatically
# But we can! ... mostly.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_VERIFY=false
DEBUG=false
DRY_RUN=false
TARGETS=()

for arg in "$@"; do
    case $arg in
        --skip-verify)
            SKIP_VERIFY=true
            ;;
        --debug)
            DEBUG=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        *)
            TARGETS+=("$arg")
            ;;
    esac
done

# Default to current directory if no targets provided
if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS=(".")
fi

# Debug output function
debug_log()
            {
    if [ "$DEBUG" = true ]; then
        echo -e "${BLUE}[DEBUG] $1${NC}" >&2
    fi
}

echo -e "${BLUE}🔧 Fixing ruff patterns (TRY401, G004, TRY300)...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}🔍 DRY RUN MODE - No changes will be made${NC}"
fi

# Track changes
CHANGES_MADE=0
TOTAL_FILES_PROCESSED=0

# Get script directory for relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBSCRIPT_DIR="$SCRIPT_DIR/ruff-fixes"

# Function to calculate file checksums for change detection
calculate_checksums()
                      {
    target_dir="$1"
    find "$target_dir" -name "*.py" -type f -exec sha256sum {} \; 2> /dev/null | sort
}

# Function to count Python files
count_python_files()
                     {
    count=0
    for target in "${TARGETS[@]}"; do
        if [ -f "$target" ] && [[ "$target" == *.py ]]; then
            ((count++))
        elif [ -d "$target" ]; then
            dir_count=$(find "$target" -name "*.py" -type f | wc -l)
            ((count += dir_count))
        fi
    done
    echo $count
}

TOTAL_FILES_PROCESSED=$(count_python_files)
debug_log "Found $TOTAL_FILES_PROCESSED Python files to process"

# Create temporary directory for checksums
TEMP_DIR=$(mktemp -d)
trap 'rm -rf $TEMP_DIR' EXIT

# Calculate initial checksums
INITIAL_CHECKSUMS="$TEMP_DIR/initial.checksums"
for target in "${TARGETS[@]}"; do
    if [ -f "$target" ]; then
        sha256sum "$target" >> "$INITIAL_CHECKSUMS" 2> /dev/null || true
    elif [ -d "$target" ]; then
        calculate_checksums "$target" >> "$INITIAL_CHECKSUMS"
    fi
done
sort -o "$INITIAL_CHECKSUMS" "$INITIAL_CHECKSUMS" 2> /dev/null || touch "$INITIAL_CHECKSUMS"

# Function to check if files changed
files_changed()
                {
    debug_log "Checking for file changes..."
    current_checksums="$TEMP_DIR/current.checksums"
    debug_log "Clearing current checksums file: $current_checksums" > "$current_checksums"  # Clear the file

    for target in "${TARGETS[@]}"; do
        debug_log "Processing target: $target"
        if [ -f "$target" ]; then
            debug_log "Target is a file, calculating checksum"
            sha256sum "$target" >> "$current_checksums" 2> /dev/null || true
        elif [ -d "$target" ]; then
            debug_log "Target is a directory, calculating checksums for all Python files"
            calculate_checksums "$target" >> "$current_checksums"
        fi
        debug_log "Finished processing target: $target"
    done
    debug_log "Sorting current checksums"
    sort -o "$current_checksums" "$current_checksums" 2> /dev/null || touch "$current_checksums"

    debug_log "Comparing checksums..."
    debug_log "Initial checksums file: $INITIAL_CHECKSUMS"
    debug_log "Current checksums file: $current_checksums"
    if ! diff -q "$INITIAL_CHECKSUMS" "$current_checksums" > /dev/null 2>&1; then
        debug_log "Changes detected"
        debug_log "Updating initial checksums"
        cp "$current_checksums" "$INITIAL_CHECKSUMS"
        debug_log "Files changed function returning 0 (changes detected)"
        return 0  # Files changed
    else
        debug_log "No changes detected"
        debug_log "Files changed function returning 1 (no changes)"
        return 1  # No changes
    fi
}

# Step 1: Use Python script for G004 (f-string conversion)
echo -e "${YELLOW}Step 1: Converting logging f-strings to % format...${NC}"
debug_log "Running f_string_converter.py on targets: ${TARGETS[*]}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN] Would run f-string conversion${NC}"
else
    python3 "$SUBSCRIPT_DIR/f_string_converter.py" "${TARGETS[@]}"
    fstring_exit_code=$?
    debug_log "F-string converter exit code: $fstring_exit_code"
    if [ $fstring_exit_code -eq 0 ]; then
        debug_log "About to check for file changes after f-string conversion"
        if files_changed; then
            debug_log "About to increment CHANGES_MADE counter"
            CHANGES_MADE=$((CHANGES_MADE + 1))
            debug_log "CHANGES_MADE counter incremented to: $CHANGES_MADE"
            echo -e "${GREEN}✅ F-string conversion applied changes${NC}"
            debug_log "Changes detected after f-string conversion"
        else
            echo -e "${GREEN}✅ F-string conversion complete (no changes needed)${NC}"
            debug_log "No changes detected after f-string conversion"
        fi
        debug_log "Finished f-string conversion step"
    else
        echo -e "${RED}❌ F-string converter failed${NC}"
        debug_log "F-string converter failed, exiting"
        exit 1
    fi
fi

# Step 2: Remove redundant exception references with punctuation cleanup
echo -e "${YELLOW}Step 2: Removing redundant exception references...${NC}"
debug_log "Running punctuation_cleaner.py on targets: ${TARGETS[*]}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN] Would run punctuation cleanup${NC}"
else
    python3 "$SUBSCRIPT_DIR/punctuation_cleaner.py" "${TARGETS[@]}"
    punctuation_exit_code=$?
    debug_log "Punctuation cleaner exit code: $punctuation_exit_code"
    if [ $punctuation_exit_code -eq 0 ]; then
        debug_log "About to check for file changes after punctuation cleanup"
        if files_changed; then
            CHANGES_MADE=$((CHANGES_MADE + 1))
            echo -e "${GREEN}✅ Exception reference cleanup applied changes${NC}"
            debug_log "Changes detected after punctuation cleanup"
        else
            echo -e "${GREEN}✅ Exception reference cleanup complete (no changes needed)${NC}"
            debug_log "No changes detected after punctuation cleanup"
        fi
        debug_log "Finished punctuation cleanup step"
    else
        echo -e "${RED}❌ Punctuation cleaner failed${NC}"
        exit 1
    fi
fi

# Step 3: Move return statements from try to else blocks
echo -e "${YELLOW}Step 3: Moving return statements from try to else blocks...${NC}"
debug_log "Running try_return_fixer.py on targets: ${TARGETS[*]}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}[DRY RUN] Would run try/return fixes${NC}"
else
    # Check if try_return_fixer.py exists, if not fall back to ast-grep rules
    if [ -f "$SUBSCRIPT_DIR/try_return_fixer.py" ]; then
        if python3 "$SUBSCRIPT_DIR/try_return_fixer.py" "${TARGETS[@]}"; then
            if files_changed; then
                CHANGES_MADE=$((CHANGES_MADE + 1))
                echo -e "${GREEN}✅ Try/return fixes applied changes${NC}"
            else
                echo -e "${GREEN}✅ Try/return fixes complete (no changes needed)${NC}"
            fi
        else
            echo -e "${RED}❌ Try/return fixer failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  Using ast-grep fallback for try/return fixes${NC}"
        # Fallback to ast-grep rules (with improved logic)
        ast_grep_changes=0
        for rule in fix-try-return-simple fix-try-return-as fix-try-return-multiple fix-try-return-multiple-as fix-try-return-bare-except; do
            debug_log "Applying ast-grep rule: $rule"
            if ast-grep scan -r "$SUBSCRIPT_DIR/rules/$rule.yml" --update-all "${TARGETS[@]}" > /dev/null 2>&1; then
                if files_changed; then
                    ((ast_grep_changes++))
                    debug_log "Rule $rule made changes"
                fi
            fi
        done

        if [ $ast_grep_changes -gt 0 ]; then
            CHANGES_MADE=$((CHANGES_MADE + 1))
            echo -e "${GREEN}✅ Applied $ast_grep_changes try/return fix(es)${NC}"
        else
            echo -e "${GREEN}✅ Try/return fixes complete (no changes needed)${NC}"
        fi
    fi
fi

# Summary
echo
echo -e "${BLUE}📊 PROCESSING SUMMARY${NC}"
echo -e "Files processed: $TOTAL_FILES_PROCESSED"
echo -e "Components that made changes: $CHANGES_MADE"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}🔍 DRY RUN completed - no actual changes were made${NC}"
    echo -e "${BLUE}💡 Run without --dry-run to apply fixes${NC}"
elif [ $CHANGES_MADE -gt 0 ]; then
    echo -e "${GREEN}🎉 Applied fixes from $CHANGES_MADE component(s)! Run 'git diff' to review changes.${NC}"
else
    echo -e "${GREEN}✨ No fixes needed - your code already follows best practices!${NC}"
fi

# Optional: Run ruff to verify fixes
if [ "$SKIP_VERIFY" = true ]; then
    echo -e "${BLUE}🚀 Skipping ruff verification (--skip-verify flag used)${NC}"
elif [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}🚀 Skipping ruff verification (dry run mode)${NC}"
elif command -v ruff &> /dev/null; then
    echo -e "${YELLOW}Verifying fixes with ruff...${NC}"
    debug_log "Running ruff check on targets: ${TARGETS[*]}"

    # Run ruff check with simpler approach
    debug_log "About to run ruff check..."
    if ruff check "${TARGETS[@]}" --select=TRY401,G004,TRY300 > /dev/null 2>&1; then
        echo -e "${GREEN}🎯 Perfect! No remaining TRY401/G004/TRY300 violations!${NC}"
        debug_log "Ruff verification passed"
    else
        # Count violations by running ruff again (simpler than capturing output)
        violation_output=$(ruff check "${TARGETS[@]}" --select=TRY401,G004,TRY300 2>&1 || true)
        violation_count=$(echo "$violation_output" | grep -c "TRY401\|G004\|TRY300" || echo "0")
        if [ "$violation_count" -gt 0 ]; then
            echo -e "${YELLOW}⚠️  $violation_count violation(s) remain and may need manual review${NC}"
            # Print summary of violations: filepath, lint code, line number
            echo -e "${YELLOW}Unfixed violations:${NC}"
            echo "$violation_output" | grep -E "TRY401|G004|TRY300" | awk -F: '{
                # Format: filepath:line:col: code [message]
                split($0, parts, ":");
                filepath=parts[1];
                line=parts[2];
                rest=substr($0, index($0,$3));
                match(rest, /([A-Z0-9]+) /, codearr);
                code=codearr[1];
                printf("%s:%s - %s\n", filepath, line, code);
            }'
            if [ "$DEBUG" = true ]; then
                echo -e "${BLUE}[DEBUG] Remaining violations (full details):${NC}"
                echo "$violation_output" | grep "TRY401\|G004\|TRY300" | head -10
            fi
        else
            echo -e "${YELLOW}⚠️  Ruff check failed but no violations detected${NC}"
            debug_log "Ruff output: $violation_output"
        fi
        echo "Run: ruff check ${TARGETS[*]} --select=TRY401,G004,TRY300 for details"
    fi
else
    echo -e "${BLUE}💡 Install ruff to verify fixes: pip install ruff${NC}"
fi

# Final debug information
if [ "$DEBUG" = true ]; then
    echo -e "${BLUE}[DEBUG] Script completed successfully${NC}"
    echo -e "${BLUE}[DEBUG] Temporary directory: $TEMP_DIR${NC}"
fi

# Ensure script exits with success code
exit 0
