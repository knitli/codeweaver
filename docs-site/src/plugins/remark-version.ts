// SPDX-FileCopyrightText: 2026 Knitli Inc.
//
// SPDX-License-Identifier: MIT OR Apache-2.0

/**
 * Remark plugin that replaces {{VERSION}} tokens in markdown content
 * with the current version derived from `git describe`.
 *
 * Runs at build time — no runtime cost.
 */

import { execFileSync } from "node:child_process";
import { visit } from "unist-util-visit";
import type { Root, Text } from "mdast";

let cachedVersion: string | undefined;

function getVersion(): string {
  if (cachedVersion !== undefined) return cachedVersion;

  try {
    const raw = execFileSync("git", ["describe", "--tags", "--always"], {
      encoding: "utf-8",
      timeout: 5000,
    }).trim();

    // Convert git describe output to clean version:
    //   v0.2.0                        -> 0.2.0
    //   v0.2.0-3-gabcdef              -> 0.2.0-dev
    //   v0.1.0-alpha.5-103-gabcdef    -> 0.1.0-dev
    //   v0.2.0-beta.1                 -> 0.2.0-beta.1
    const match = raw.match(/^v?(\d+\.\d+\.\d+)(?:-[a-z]+\.\d+)?(?:-(\d+)-g[a-f0-9]+)?$/);
    if (match) {
      const baseVersion = match[1];
      const commitDistance = match[2];
      cachedVersion = commitDistance ? `${baseVersion}-dev` : baseVersion;
    } else {
      cachedVersion = raw.replace(/^v/, "");
    }
  } catch {
    cachedVersion = "0.0.0-unknown";
  }

  return cachedVersion;
}

export function remarkVersion(): (tree: Root) => void {
  return (tree: Root) => {
    const version = getVersion();

    visit(tree, "text", (node: Text) => {
      if (node.value.includes("{{VERSION}}")) {
        node.value = node.value.replaceAll("{{VERSION}}", version);
      }
    });
  };
}
