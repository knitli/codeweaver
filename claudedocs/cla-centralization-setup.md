# CLA Centralization Setup Guide

This guide shows how to centralize CLA signatures in the existing `knitli/.github` repository.

## Current Structure

Your `knitli/.github` repo currently has:
```
knitli/.github/
├── .gitignore
├── LICENSE
└── profile/
    └── README.md  # Organization profile
```

## Goal Structure

After setup:
```
knitli/.github/
├── .gitignore
├── LICENSE
├── .github/
│   └── workflows/
│       └── cla-check.yml        # ← Reusable workflow (single source of truth)
├── profile/
│   └── README.md
└── cla-signatures/
    ├── README.md
    └── codeweaver.json          # (auto-created by CLA bot)
```

---

## Architecture

### Centralized Reusable Workflow

The CLA checking logic lives in **one place**: `knitli/.github/.github/workflows/cla-check.yml`

**Benefits**:
- ✅ **Single source of truth**: Update once, applies to all repos
- ✅ **Automatic updates**: Bug fixes propagate immediately
- ✅ **Consistent behavior**: All repos use identical logic
- ✅ **Minimal configuration**: Each repo needs only 3 lines of config

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ knitli/.github (Central Configuration)                      │
├─────────────────────────────────────────────────────────────┤
│ .github/workflows/cla-check.yml  ← Reusable workflow        │
│ cla-signatures/                   ← All signature files     │
│   ├── codeweaver.json                                       │
│   ├── thread.json                                           │
│   └── other-repo.json                                       │
└─────────────────────────────────────────────────────────────┘
                        ▲
                        │ calls
                        │
┌───────────────────────┴─────────────────────────────────────┐
│ Each Repository (knitli/codeweaver, knitli/thread, etc.)   │
├─────────────────────────────────────────────────────────────┤
│ .github/workflows/cla.yml  ← Tiny caller workflow (~25 lines)│
│                                                              │
│   jobs:                                                      │
│     cla-check:                                               │
│       uses: knitli/.github/.github/workflows/cla-check.yml@main
│       with:                                                  │
│         repo_name: "codeweaver"                              │
│       secrets: inherit                                       │
└─────────────────────────────────────────────────────────────┘
```

### Workflow Execution

1. **PR opened** → Triggers local `cla.yml` in repo
2. **Local workflow** → Calls reusable workflow in `.github` repo
3. **Reusable workflow** → Checks membership → Runs CLA assistant
4. **CLA assistant** → Stores signature in `knitli/.github/cla-signatures/{repo}.json`

---

## Setup Steps

### Step 1: Add CLA Signatures Directory

```bash
# Clone the .github repo
cd /tmp
gh repo clone knitli/.github
cd .github

# Create CLA signatures directory
mkdir -p cla-signatures

# Create README explaining what this is
cat > cla-signatures/README.md << 'EOF'
# CLA Signatures

This directory stores Contributor License Agreement (CLA) signatures for all Knitli repositories.

## Files

Each repository has its own JSON file:
- `codeweaver.json` - CLA signatures for knitli/codeweaver
- (Additional repos will be added as needed)

## How It Works

The CLA Assistant GitHub Action automatically:
1. Checks if PR authors have signed the CLA
2. Prompts unsigned contributors with instructions
3. Records signatures in this directory when users agree

## Bot Allowlist

The following accounts are exempt from CLA requirements:
- `bashandbone` (founder)
- `github-actions[bot]`
- `dependabot[bot]`
- `codegen-sh[bot]`
- `changeset-bot`
- `claude[bot]`
- `copilot`

## Privacy Note

While this repository is public, signature files only contain:
- GitHub username
- Timestamp
- PR/Issue number

No email addresses or personal information are stored.

## Manual Access

To view signatures:
```bash
cat cla-signatures/codeweaver.json | jq
```

To verify a specific user:
```bash
cat cla-signatures/codeweaver.json | jq '.signedContributors[] | select(.name=="username")'
```
EOF

# Commit and push
git add cla-signatures
git commit -m "chore: add CLA signatures directory"
git push origin main
```

### Step 2: Create Personal Access Token (PAT)

The workflow needs a token with write access to the `.github` repo.

1. Go to: https://github.com/settings/tokens?type=beta
2. Click **"Generate new token"** (fine-grained)
3. Configure:
   - **Token name**: `CLA Assistant - .github repo`
   - **Expiration**: 1 year (or custom, max 1 year)
   - **Resource owner**: `knitli`
   - **Repository access**: Only select repositories
     - ✅ Select: `knitli/.github`
   - **Repository permissions**:
     - **Contents**: Read and write ✅
     - **Pull requests**: Read and write ✅
     - **Metadata**: Read-only (automatically included)

4. Click **"Generate token"**
5. **Copy the token** (you won't see it again!)

### Step 3: Add Secret to Repository

Add the token as a secret to **codeweaver** (and any other repos that need CLA checking):

**Option A: Using GitHub CLI**
```bash
cd /home/knitli/codeweaver

# Add the secret
gh secret set CLA_ACCESS_TOKEN

# Paste the token when prompted
```

**Option B: Using Web UI**
1. Go to: https://github.com/knitli/codeweaver/settings/secrets/actions
2. Click **"New repository secret"**
3. Name: `CLA_ACCESS_TOKEN`
4. Value: [paste your token]
5. Click **"Add secret"**

**Important**: You'll need to add this secret to **every repository** that uses the CLA workflow.

### Step 4: Verify the Workflow

The workflow in `codeweaver/.github/workflows/cla.yml` is already configured correctly:

```yaml
# Lines 91-94 in cla.yml
remote-organization-name: knitli
remote-repository-name: .github
path-to-signatures: cla-signatures/codeweaver.json
```

No changes needed! ✅

### Step 5: Test the Setup

1. **Create a test PR** (or wait for an external contributor)
2. The workflow should:
   - ✅ Run on PR creation
   - ✅ Check if author is a Knitli org member
   - ✅ Skip CLA for members (bashandbone, org members)
   - ✅ Prompt external contributors for CLA signature

3. **For external contributors**, they should see:
   ```
   👋 Hey @username,

   ## Thanks for your contribution to Thread! 🧵

   ### You need to agree to the CLA first... 🖊️
   ...
   ```

4. **After commenting agreement**, the bot should:
   - ✅ Record signature in `knitli/.github/cla-signatures/codeweaver.json`
   - ✅ Add a commit to the `.github` repo
   - ✅ Update PR status to passing

### Step 6: Verify Signature Storage

Check that signatures are being stored correctly:

```bash
# Clone .github repo
cd /tmp
gh repo clone knitli/.github
cd .github

# View signatures (after first contributor signs)
cat cla-signatures/codeweaver.json | jq

# Expected format:
# {
#   "signedContributors": [
#     {
#       "name": "username",
#       "id": 12345,
#       "comment_id": 67890,
#       "created_at": "2025-11-24T20:00:00Z",
#       "repoId": 999999,
#       "pullRequestNo": 42
#     }
#   ]
# }
```

---

## Adding Other Repositories

To add CLA checking to other Knitli repos (e.g., `thread`), simply create a workflow file that calls the centralized reusable workflow.

### Option A: Using Reusable Workflow (Recommended)

**Benefits**: Single source of truth, automatic updates, minimal configuration

Create `.github/workflows/cla.yml` in your new repo:

```yaml
# SPDX-FileCopyrightText: 2025 Knitli Inc. <knitli@knit.li>
# SPDX-License-Identifier: MIT OR Apache-2.0

name: CLA Assistant

on:
  issue_comment:
    types: [created]
  pull_request_target:
    types: [opened, closed, synchronize]

jobs:
  cla-check:
    uses: knitli/.github/.github/workflows/cla-check.yml@main
    with:
      repo_name: "thread"  # ← Change this to match your repo
      cla_document_url: "https://github.com/knitli/thread/blob/main/CONTRIBUTORS_LICENSE_AGREEMENT.md"  # ← Update URL
    secrets: inherit
```

**That's it!** The org-level `CLA_ACCESS_TOKEN` secret is automatically available.

**Updates**: When the reusable workflow is updated in `knitli/.github`, all repos using it automatically get the fixes.

### Option B: Standalone Workflow (Legacy)

If you need repo-specific customization:

```bash
# Copy the full workflow
curl -o .github/workflows/cla.yml https://raw.githubusercontent.com/knitli/codeweaver/003-our-aim-to/.github/workflows/cla.yml

# Update repo-specific values
sed -i 's/codeweaver/thread/g' .github/workflows/cla.yml
```

**Drawback**: Must manually update when the workflow changes.

---

## Troubleshooting

### "Error: Resource not accessible by personal access token"

**Problem**: Token doesn't have correct permissions

**Solution**:
1. Check token has `Contents: Read and write` permission for `knitli/.github`
2. Regenerate token if needed
3. Update secret: `gh secret set CLA_ACCESS_TOKEN`

### "CLA Assistant not commenting on PR"

**Problem**: Workflow condition not met or secret missing

**Solution**:
1. Check workflow runs: https://github.com/knitli/codeweaver/actions
2. Verify `CLA_ACCESS_TOKEN` secret exists: `gh secret list`
3. Check PR author isn't in allowlist or org member

### "Signature not being recorded"

**Problem**: Token permissions or branch mismatch

**Solution**:
1. Verify `.github` repo has `main` branch (not `master`)
2. Check token permissions include write access
3. Look at workflow logs for detailed error

### "Permission denied when committing signature"

**Problem**: Using `GITHUB_TOKEN` instead of `PERSONAL_ACCESS_TOKEN`

**Solution**:
Workflow should have both tokens:
```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  PERSONAL_ACCESS_TOKEN: ${{ secrets.CLA_ACCESS_TOKEN }}
```

---

## Token Management

### Rotation Schedule

Fine-grained tokens expire after max 1 year. Set a calendar reminder to rotate:

1. **30 days before expiration**:
   - Generate new token with same permissions
   - Update secret in **all** repos using CLA workflow

2. **After updating all repos**:
   - Delete old token from GitHub settings

### Revocation

If token is compromised:

1. **Immediately revoke**: https://github.com/settings/tokens
2. **Generate new token** (follow Step 2)
3. **Update secret in all repos**:
   ```bash
   for repo in codeweaver thread other-repo; do
     cd /path/to/$repo
     gh secret set CLA_ACCESS_TOKEN
   done
   ```

---

## Benefits of This Setup

✅ **Centralized**: All CLA signatures in one place
✅ **Reusable**: Same token works for all repos
✅ **Auditable**: Git history tracks all signatures
✅ **Scalable**: Easy to add new repositories
✅ **Secure**: Fine-grained token with minimal permissions
✅ **Standards-Compliant**: Uses official `.github` repo convention

---

## Next Steps

1. ✅ Add `cla-signatures/` directory to `.github` repo
2. ✅ Generate fine-grained PAT
3. ✅ Add `CLA_ACCESS_TOKEN` secret to codeweaver
4. ✅ Test with a PR (or wait for external contributor)
5. ✅ Add workflow to other repos as needed

---

## Quick Reference

**Token URL**: https://github.com/settings/tokens
**.github repo**: https://github.com/knitli/.github
**Reusable workflow**: `knitli/.github/.github/workflows/cla-check.yml`
**Local workflow**: `.github/workflows/cla.yml` (in each repo)
**Secret name**: `CLA_ACCESS_TOKEN` (org-level)
**Signature path**: `cla-signatures/{repo-name}.json`

---

## Generating Contributor Lists

Each CLA signature includes the `repoId`, which allows you to track contributions across all repositories.

### Signature Data Structure

Each signature stores:
```json
{
  "name": "username",           // GitHub username
  "id": 12345,                  // GitHub user ID
  "comment_id": 67890,          // Comment ID where they agreed
  "body": "I read the...",      // Comment text
  "created_at": "2025-11-24T...", // Timestamp
  "repoId": "999999",           // Repository ID ✅
  "pullRequestNo": 42           // PR number
}
```

### Generate Lists

**Using Python script** (recommended):
```bash
# Generate CONTRIBUTORS.md
python scripts/project/contributors.py --format markdown

# Generate contributors.json
python scripts/project/contributors.py --format json

# Generate contributors.csv
python scripts/project/contributors.py --format csv

# Per-repo breakdown
python scripts/project/contributors.py --by-repo
```

**Using Bash script**:
```bash
# Generate CONTRIBUTORS.md
./scripts/project/generate-contributors-list.sh markdown

# Generate JSON
./scripts/project/generate-contributors-list.sh json

# Generate CSV
./scripts/project/generate-contributors-list.sh csv
```

### Example Output

**CONTRIBUTORS.md**:
```markdown
# Contributors

- [@contributor1](https://github.com/contributor1) - 3 contributions across 2 repos (`codeweaver`, `thread`)
- [@contributor2](https://github.com/contributor2) - 1 contribution across 1 repo (`codeweaver`)
```

**contributors.json**:
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
