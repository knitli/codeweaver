# sourcery skip: lambdas-should-be-short
#!/usr/bin/env python3
"""
SPDX-FileCopyrightText: 2025 Knitli Inc. <knitli@knit.li>
SPDX-License-Identifier: MIT OR Apache-2.0

Generate comprehensive contributor lists from CLA signatures across all Knitli repositories.

Usage:
    python scripts/contributors.py --format markdown
    python scripts/contributors.py --format json
    python scripts/contributors.py --format csv
    python scripts/contributors.py --by-repo
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def fetch_cla_signatures() -> dict[str, list[dict[str, str]]]:
    """Clone .github repo and read all CLA signature files."""
    print("📥 Fetching CLA signatures from knitli/.github...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone .github repo
        binary = shutil.which("gh")
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "repo",
                "clone",
                "knitli/.github",
                f"{tmpdir}/.github",
                "--",
                "--depth",
                "1",
                "--quiet",
            ],
            executable=binary,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"❌ Failed to clone .github repo: {result.stderr}")
            sys.exit(1)

        # Read all signature JSON files
        cla_dir = Path(tmpdir) / ".github" / "cla-signatures"
        signatures_by_repo = {}

        for json_file in cla_dir.glob("*.json"):
            repo_name = json_file.stem  # e.g., "codeweaver" from "codeweaver.json"
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                signatures_by_repo[repo_name] = data.get("signedContributors", [])
                print(
                    f"  ✓ Loaded {len(signatures_by_repo[repo_name])} signatures from {repo_name}"
                )
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Skipping {json_file.name}: Invalid JSON - {e}")

        return signatures_by_repo


def aggregate_contributors(
    signatures_by_repo: dict[str, list[dict[str, str]]],
) -> dict[str, dict[str, str | list | set | None]]:
    """Aggregate contributors across all repos."""
    contributors = defaultdict(
        lambda: {
            "name": None,
            "id": None,
            "repos": set(),
            "contributions": [],
            "first_contribution": None,
        }
    )

    for repo_name, signatures in signatures_by_repo.items():
        for sig in signatures:
            user_id = sig.get("id")
            if not user_id:
                continue

            contributor = contributors[user_id]
            contributor["name"] = sig.get("name")
            contributor["id"] = user_id
            contributor["repos"].add(repo_name)
            contributor["contributions"].append({
                "repo": repo_name,
                "pr_number": sig.get("pullRequestNo"),
                "date": sig.get("created_at"),
            })

            # Track first contribution
            created_at = sig.get("created_at")
            if created_at and (
                not contributor["first_contribution"]
                or created_at < contributor["first_contribution"]
            ):
                contributor["first_contribution"] = created_at

    # Convert sets to lists for JSON serialization
    for contributor in contributors.values():
        contributor["repos"] = sorted(contributor["repos"])

    return dict(contributors)


def generate_markdown(contributors: dict[str, dict[str, str | list | set | None]]) -> str:
    """Generate CONTRIBUTORS.md file."""
    sorted_contributors = sorted(
        contributors.values(), key=lambda c: c["first_contribution"] or "9999-12-31"
    )

    lines = [
        "# Contributors",
        "",
        "Thank you to everyone who has contributed to Knitli projects! 🎉",
        "",
        "This list is automatically generated from CLA signatures across all repositories.",
        "",
        "## All Contributors",
        "",
    ]

    for contributor in sorted_contributors:
        name = contributor["name"]
        repo_count = len(contributor["repos"])
        contribution_count = len(contributor["contributions"])
        if not contributor["repos"]:
            continue
        repos = ", ".join(f"`{repo}`" for repo in contributor["repos"])
        plural_contrib = "s" if contribution_count > 1 else ""
        plural_repo = "s" if repo_count > 1 else ""

        lines.append(
            f"- [@{name}](https://github.com/{name}) - "
            f"{contribution_count} contribution{plural_contrib} "
            f"across {repo_count} repo{plural_repo} ({repos})"
        )

    total_contributions = sum(len(c["contributions"]) for c in contributors.values())

    lines.extend([
        "",
        "## Statistics",
        "",
        f"- **Total Contributors**: {len(contributors)}",
        f"- **Total Contributions**: {total_contributions}",
        f"- **Generated**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
    ])

    return "\n".join(lines)


def generate_json(contributors: dict[str, dict[str, str | list | set | None]]) -> str:
    """Generate contributors.json file."""
    # Convert for JSON serialization
    contributors: list[dict[str, str | list | set | None]] = []
    contributors.extend(
        {
            "name": data["name"],
            "id": data["id"],
            "github_url": f"https://github.com/{data['name']}",
            "first_contribution": data["first_contribution"],
            "total_contributions": len(data["contributions"]),
            "repos": data["repos"],
            "contributions": data["contributions"],
        }
        for data in contributors.values()
    )
    contributors.sort(key=lambda c: c["first_contribution"] or "9999-12-31")

    return json.dumps(
        {
            "generated_at": f"{datetime.now(UTC).isoformat()}Z",
            "total_contributors": len(contributors),
            "contributors": contributors,
        },
        indent=2,
    )


def generate_csv(contributors: dict[str, dict[str, str | list | set | None]]) -> str:
    """Generate contributors.csv file."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "name",
        "github_url",
        "id",
        "first_contribution",
        "total_contributions",
        "repos",
    ])

    # Data rows
    sorted_contributors = sorted(
        contributors.values(), key=lambda c: c["first_contribution"] or "9999-12-31"
    )

    for contributor in sorted_contributors:
        writer.writerow([
            contributor["name"],
            f"https://github.com/{contributor['name']}",
            contributor["id"],
            contributor["first_contribution"] or "",
            len(contributor["contributions"]),
            ";".join(contributor["repos"]),  # ty: ignore[no-matching-overload]
        ])

    return output.getvalue()


def generate_by_repo(signatures_by_repo: dict[str, list[dict[str, str]]]) -> str:
    """Generate per-repo contributor breakdown."""
    lines = ["# Contributors by Repository", ""]

    for repo_name in sorted(signatures_by_repo.keys()):
        signatures = signatures_by_repo[repo_name]
        lines.extend((f"## {repo_name}", "", f"Total contributors: {len(signatures)}", ""))
        for sig in sorted(signatures, key=lambda s: s.get("created_at", "")):
            name = sig.get("name")
            pr = sig.get("pullRequestNo")
            date = sig.get("created_at", "").split("T")[0]  # Just the date part
            lines.append(f"- [@{name}](https://github.com/{name}) - PR #{pr} ({date})")

        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate contributor lists from CLA signatures")
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "csv"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--by-repo",
        action="store_true",
        help="Generate per-repo breakdown instead of aggregated list",
    )
    parser.add_argument(
        "--output", type=Path, help="Output file path (default: auto-generated based on format)"
    )

    args = parser.parse_args()

    # Fetch signatures
    signatures_by_repo = fetch_cla_signatures()

    if not signatures_by_repo:
        print("⚠️  No signature files found")
        return

    print(f"✅ Found {len(signatures_by_repo)} repositories with signatures")

    # Generate output
    if args.by_repo:
        output = generate_by_repo(signatures_by_repo)
        default_filename = "CONTRIBUTORS_BY_REPO.md"
    else:
        contributors = aggregate_contributors(signatures_by_repo)
        print(f"✅ Found {len(contributors)} unique contributors")

        if args.format == "markdown":
            output = generate_markdown(contributors)
            default_filename = "CONTRIBUTORS.md"
        elif args.format == "json":
            output = generate_json(contributors)
            default_filename = "contributors.json"
        elif args.format == "csv":
            output = generate_csv(contributors)
            default_filename = "contributors.csv"

    # Write output
    output_path = args.output or Path.cwd() / default_filename
    output_path.write_text(output, encoding="utf-8")

    print(f"📄 Generated: {output_path}")
    print("✨ Done!")


if __name__ == "__main__":
    main()
