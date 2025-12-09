#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

set -e

# [MISE] description="This script automates the resolution of git merge conflicts during a rebase. It's intended for situations where a branch is being rebased onto main, and main is significantly ahead.\n  1. It allows you to specify the file types that require manual review (e.g., markdown files)\n  2. It automatically resolves all other conflicts by favoring the changes from main\n  3. IMPORTANT: It discards any staged changes from the rebased branch for non-targeted files. Use with caution! You can optionally disable this behavior by passing the `--review-staged` flag."
# [MISE] alias="rebase-resolve"
# [MISE] tools="git@latest"
#
# [USAGE] min_usage_version "2.8.0"
# [USAGE] name "Automated Git Rebase Conflict Resolver"
# [USAGE] bin "resolve-rebase"
# [USAGE] version "0.1.0"
# [USAGE] about "Automates git merge conflict resolution during rebase, favoring main branch changes except for specified file types requiring manual review."
# [USAGE]
# [USAGE] flag "-r --review-staged" default=#false help="If set, the script will **not** *discard staged changes* from the rebased branch for non-targeted files. Instead, it will prompt for manual review of all staged changes." env="CW_DEV_REVIEW_STAGED"
# [USAGE] flag "-b --base-branch <branch>" default="main" help="The base branch onto which the current branch is being rebased. Defaults to 'main'."
# [USAGE] flag "-t --target-branch <branch>" default="{{ exec(command='$(git rev-parse --abbrev-ref HEAD)', default='HEAD') }}" help="The branch that is being rebased. Defaults to current branch."
# [USAGE] arg "<globs>" var=#true help="One or more file globs (e.g., *.md) that should require manual review during conflict resolution. May also be specific files." double_dash="optional"
# [USAGE] example "mise //:resolve-rebase -- *.md docs/*.txt" help="Run the rebase conflict resolver, requiring manual review for all markdown files and text files in the docs/ directory." header="Basic Usage" lang="bash"

# usage_globs is a space-separated string when we get it from the command line

GLOBS=()

if [[ -n "$usage_globs" ]]; then
    IFS=' ' read -r -a GLOBS <<< "$usage_globs"
fi

MAIN_BRANCH="${usage_base_branch:-main}"
TARGET_BRANCH="${usage_target_branch:-$(git rev-parse --abbrev-ref HEAD)}"
REVIEW_STAGED="${usage_review_staged:-false}"

file_is_targeted()
                   {
    local file="$1"
    for glob in "${GLOBS[@]}"; do
        # we want to match globs here, shellcheck:
        # shellcheck disable=SC2053
        if [[ "$file" == $glob ]]; then
            return 0
        fi
    done
    return 1
}

staged_files()
               {
    local staged_files
    staged_files=$(git diff --name-only --cached)
    echo "$staged_files"
}

conflicted_files()
                   {
    local conflicted_files
    conflicted_files=$(git diff --name-only --diff-filter=U)
    echo "$conflicted_files"
}

already_in_rebase()
                    {
    if [ -d ".git/rebase-merge" ] || [ -d ".git/rebase-apply" ]; then
        return 0
    else
        return 1
    fi
}

branch_has_file()
                   {
    local file="$1"
    if git cat-file -e "$MAIN_BRANCH:$file" 2> /dev/null; then
        return 0
    fi
    return 1
}

switch_to_target_if_not_in_rebase()
                                    {
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    if ! already_in_rebase && ! [[ "$current_branch" == "$TARGET_BRANCH" ]] > /dev/null 2>&1; then
        echo "Switching to target branch '$TARGET_BRANCH'..."
        echo "We'll stash any uncommitted changes first."
        git stash push -u -m "temp-stash-before-rebase-resolve-$(date +%s)"
        git checkout "$TARGET_BRANCH"
    fi
}

prompt_for_file_review()
                         {
    local file="$1"
    echo " - Please review the file: $file"
}

manual_review_prompt()
                       {
    local files="$*"
    if [[ -n "$files" ]]; then
        echo "================================="
        echo "MANUAL REVIEW REQUIRED"
        echo ""
        echo "For each of the following files, review the changes and resolve the conflicts manually."
        echo "If the file isn't staged yet, use 'git add <file>' after resolving the conflicts."
        echo "If it is staged and you DON'T want to keep the changes, use \"git restore --staged --source=\"$MAIN_BRANCH\" <file>\" to discard them."
        echo "The following files require your manual review:"
        for file in $files; do
            prompt_for_file_review "$file"
        done
        echo "================================="
    fi
}

handle_staged_changes()
                        {
    local staged="$1"
    if [[ "$REVIEW_STAGED" == "true" ]]; then
        manual_review_prompt "$staged"
    else
        local files_requiring_review
        local no_review_needed
        files_requiring_review=()
        no_review_needed=()
        for file in $staged; do
            if file_is_targeted "$file"; then
                files_requiring_review+=("$file")
            else
                no_review_needed+=("$file")
            fi
        done
        if [[ ${#no_review_needed[@]} -gt 0 ]]; then
            echo "Discarding staged changes for the following files (favoring '$MAIN_BRANCH' changes):"
            for file in "${no_review_needed[@]}"; do
                if branch_has_file "$file"; then
                    git restore --staged --worktree --source="$MAIN_BRANCH" "$file"
                    echo " - $file"
                else
                    files_requiring_review+=("$file")
                fi
            done
        fi
        if [[ ${#files_requiring_review[@]} -gt 0 ]]; then
            manual_review_prompt "${files_requiring_review[@]}"
        fi
    fi
}

handle_conflicts()
                   {
    # handle staged changes first since we'll be adding files in the next step
    local staged="$1"
    if [[ -n "$staged" ]]; then
        handle_staged_changes "$staged"
    fi

    local conflicted
    conflicted=$(conflicted_files)
    local files_requiring_review=()

    for file in $conflicted; do
        if file_is_targeted "$file"; then
            files_requiring_review+=("$file")
        else
            echo "Auto-resolving conflict for file: $file (favoring '$MAIN_BRANCH' changes)"
            if branch_has_file "$file"; then
                git checkout --theirs "$file"
                git add "$file"
            else
                files_requiring_review+=("$file")
            fi
        fi
    done

    if [[ ${#files_requiring_review[@]} -gt 0 ]]; then
        manual_review_prompt "${files_requiring_review[@]}"
    fi
}

move_to_next_conflict()
                        {
    local conflicted
    conflicted=$(conflicted_files)
    if [[ -z "$conflicted" ]] && already_in_rebase; then
        echo "All conflicts resolved. Continuing rebase..."
        git rebase --continue
    elif ! already_in_rebase; then
        echo "Looks like we're all done here. Get back to work!"
        exit 0
    fi
}

main()
       {
    switch_to_target_if_not_in_rebase
    while true; do
        local conflicted
        local staged
        staged=$(staged_files)
        conflicted=$(conflicted_files)
        if [[ -z "$conflicted" ]]; then
            # If no conflicts but there are staged changes, handle them
            if [[ "$staged" ]]; then
                handle_staged_changes "$staged"
            else
                move_to_next_conflict
                sleep 1
            fi
        else
            handle_conflicts "$staged"
            move_to_next_conflict
            sleep 1
        fi
    done
}

# just getting the first element is OK since we just need to verify that at least one glob was provided
# shellcheck disable=SC2128
if [[ -z "$GLOBS" ]]; then
    echo "You must specify at least one file glob that requires manual review during conflict resolution."
    exit 1
fi

main
