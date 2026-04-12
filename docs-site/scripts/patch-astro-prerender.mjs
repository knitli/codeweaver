#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Knitli Inc.
//
// SPDX-License-Identifier: MIT OR Apache-2.0

/**
 * Patches Astro 6's build pipeline to fix two bugs:
 *
 * 1. extractRelevantChunks misses prerender chunks that contain
 *    @@ASTRO_MANIFEST_REPLACE@@ but don't have SERIALIZED_MANIFEST_RESOLVED_ID
 *    in their moduleIds (happens with @astrojs/cloudflare prerender environment)
 *
 * 2. manifestBuildPostHook has the same moduleIds check, preventing manifest
 *    injection into prerender chunks
 *
 * 3. mutate() in runManifestInjection doesn't update chunk.code, causing
 *    contentAssetsBuildPostHook to overwrite manifest injection with original code
 *
 * See: withastro/astro#15650
 * TODO: Remove once Astro publishes a fix
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function patchFile(relPath, patches) {
  const absPath = resolve(ROOT, "node_modules", relPath);
  let content = readFileSync(absPath, "utf-8");
  let changed = false;

  for (const [search, replace] of patches) {
    if (content.includes(search)) {
      content = content.replace(search, replace);
      changed = true;
    }
  }

  if (changed) {
    writeFileSync(absPath, content);
    console.log(`  ✓ patched ${relPath}`);
  } else {
    console.log(`  ⊘ ${relPath} (already patched or no match)`);
  }
}

console.log("Patching Astro prerender build...");

// 1. Fix mutate() to update chunk.code so subsequent hooks see mutations
patchFile("astro/dist/core/build/static-build.js", [
  [
    `const mutate = (fileName, newCode, prerender) => {
    mutations.set(fileName, { code: newCode, prerender });
  };`,
    `const mutate = (fileName, newCode, prerender) => {
    mutations.set(fileName, { code: newCode, prerender });
    const chunk = chunks.find(c => c.fileName === fileName);
    if (chunk) chunk.code = newCode;
  };`,
  ],
  // 2. Fix extractRelevantChunks to also check for manifest placeholder in code
  [
    `const needsManifestInjection = chunk.moduleIds.includes(SERIALIZED_MANIFEST_RESOLVED_ID);`,
    `const needsManifestInjection = chunk.moduleIds.includes(SERIALIZED_MANIFEST_RESOLVED_ID) || chunk.code.includes("@@ASTRO_MANIFEST_REPLACE@@");`,
  ],
]);

// 3. Fix manifestBuildPostHook to find prerender chunks by code content
patchFile("astro/dist/core/build/plugins/plugin-manifest.js", [
  [
    `(c) => c.prerender && c.moduleIds.includes(SERIALIZED_MANIFEST_RESOLVED_ID)`,
    `(c) => c.prerender && (c.moduleIds.includes(SERIALIZED_MANIFEST_RESOLVED_ID) || c.code.includes(MANIFEST_REPLACE))`,
  ],
]);

console.log("Done.");
