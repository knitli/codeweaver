#!/bin/bash
# Auto-resolve rebase conflicts: choose main for all files except Python files

echo "Checking for conflicts..."

# Get list of conflicted files
conflicted_files=$(git diff --name-only --diff-filter=U)

if [ -z "$conflicted_files" ]; then
    echo "No conflicts found!"
    exit 0
fi

python_conflicts=()
non_python_resolved=0

# Process each conflicted file
for file in $conflicted_files; do
  if [[ "$file" == *.py ]]; then
    echo "⚠️  MANUAL REVIEW NEEDED: $file (Python file)"
    python_conflicts+=("$file")
  else
    echo "✅ Auto-resolving (using main): $file"
    git checkout --ours "$file"
    git add "$file"
    ((non_python_resolved++))
  fi
done

echo ""
echo "Summary:"
echo "  - Non-Python files auto-resolved: $non_python_resolved"
echo "  - Python files requiring manual review: ${#python_conflicts[@]}"

if [ ${#python_conflicts[@]} -gt 0 ]; then
    echo ""
    echo "Python files with conflicts:"
    for py_file in "${python_conflicts[@]}"; do
        echo "  - $py_file"
    done
    echo ""
    echo "Please manually resolve these Python conflicts, then run:"
    echo "  git add <files>"
    echo "  git rebase --continue"
    exit 1
else
    echo ""
    echo "All conflicts resolved! Continuing rebase..."
    git rebase --continue
fi
