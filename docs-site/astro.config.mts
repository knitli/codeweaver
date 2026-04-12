// SPDX-FileCopyrightText: 2026 Knitli Inc.
//
// SPDX-License-Identifier: MIT OR Apache-2.0

import { existsSync, copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import type { Plugin } from "vite";
import createConfig from "@knitli/astro-docs-template/config";
import { DocsAssets } from "@knitli/docs-components";
import type { DocsTemplateOptions } from "@knitli/astro-docs-template/config";

const { codeweaverPrimary, codeweaverReverse } = DocsAssets;

const __dirname = import.meta.dirname;

/**
 * Workaround for Astro 6 + vite 6 environment build bug where prerender
 * entry chunks are written to dist/_astro/ instead of the prerender
 * environment's configured outDir (e.g. dist/.prerender/).
 *
 * This plugin copies .js/.mjs files from _astro/ to the prerender outDir
 * after each non-client environment build, ensuring the default prerenderer
 * can find its entry point.
 *
 * See: withastro/astro#15650
 * TODO: Remove once Astro fixes vite 6 env outDir routing
 */
function fixPrerenderEntryPlugin(): Plugin {
  let root = "";
  return {
    name: "fix-prerender-entry-location",
    enforce: "post",
    sharedDuringBuild: true,
    configResolved(config) {
      root = config.root;
    },
    writeBundle() {
      const env = this.environment;
      if (!env || env.name === "client") return;

      const outDir: string = env.config?.build?.outDir;
      if (!outDir) return;

      const astroDir = join(root, "dist", "_astro");
      if (!existsSync(astroDir)) return;

      const copyRecursive = (srcDir: string, destDir: string) => {
        if (!existsSync(srcDir)) return;
        for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
          const srcPath = join(srcDir, entry.name);
          const destPath = join(destDir, entry.name);
          if (entry.isDirectory()) {
            if (entry.name === ".vite" || entry.name === "_astro") continue;
            copyRecursive(srcPath, destPath);
          } else if (
            (entry.name.endsWith(".js") || entry.name.endsWith(".mjs")) &&
            !existsSync(destPath)
          ) {
            mkdirSync(dirname(destPath), { recursive: true });
            copyFileSync(srcPath, destPath);
          }
        }
      };
      copyRecursive(astroDir, outDir);
    },
  };
}

const configOptions: DocsTemplateOptions = {
  appName: "CodeWeaver",
  description: "CodeWeaver is a code search engine for AI agents, designed to provide precise results that give agents exactly what they need for their tasks -- no more, no less.",
  rootDir: __dirname,
  cloudflareConfigPath: `${__dirname}/wrangler.jsonc`,
  llmConfig: {
    llmDescription: "CodeWeaver is an advanced code search engine tailored for AI agents, delivering precise and relevant code snippets to empower agents in their tasks. With a focus on accuracy and efficiency, CodeWeaver ensures that agents receive exactly what they need, enhancing their performance and capabilities. It uses state-of-the-art sparse and dense embeddings, model reranking, and a language-agnostic understanding of AST nodes to provide unmatched code search results. It exposes a single tool for agents to query of Model Context Protocol, `find_code`, which returns a ranked list of code and documentation snippets relevant to the agent's query.",
    promotePatterns: ["guides/installation", "guides/configuration", "guides/profiles", "guides/**", "reference/**", "examples/**", "api/**"],
    demotePatterns: ["_*", "contributors", "changelog*", "announcements", "contributing", "*code*conduct*", "*security*", "*license*"],
  },
  is_codeweaver: true,
  pluginConfigs: {
    // Relative markdown links (e.g. `./foo.md`) are rewritten by Astro at
    // build time, but starlight-links-validator reads the raw remark AST
    // and rejects them by default. Turn that check off so in-content links
    // can stay portable across base changes.
    //
    // `errorOnLocalLinks` is also disabled: the generated API reference
    // pulls docstrings from the Python source and some of them contain
    // example localhost URLs (dev server addresses) which the validator
    // would otherwise flag as invalid.
    starlightLinksValidator: {
      errorOnRelativeLinks: false,
      errorOnLocalLinks: false,
      // Routes emitted by other Starlight plugins (e.g. starlight-changelogs)
      // aren't part of the content collection, so the validator can't see
      // them and would flag links to them as invalid. Whitelist them here.
      exclude: ["/codeweaver/changelog", "/codeweaver/changelog/**"],
    },
  },
  shikiConfig: {
    themes: {
      // @ts-expect-error -- the config expects specific themes
      light: "ayu-light" as const,
      // @ts-expect-error -- the config expects specific themes
      dark: "ayu-dark" as const,
    },
    bundledLangs: [
      "ansi",
      "bash",
      "git-commit",
      "json",
      "markdown",
      "python",
      "toml",
      "yaml"
    ]
  },
  logoDark: codeweaverReverse,
  logoLight: codeweaverPrimary,
  // Cast: @knitli/astro-docs-template's sidebarConfig type only allows
  // `{ label, autogenerate }` entries, but at runtime the value is passed
  // straight through to Starlight's richer sidebar schema (items, slug,
  // nested groups, etc.). TODO: widen the template interface upstream.
  sidebarConfig: [
    {
      label: 'Getting Started',
      items: [
        { label: 'Why CodeWeaver?', slug: 'why' },
        { label: 'Installation & Setup', slug: 'guides/installation' },
      ],
    },
    {
      label: 'Core Concepts',
      items: [
        { label: 'Exquisite Context', slug: 'concepts/exquisite-context' },
        { label: 'DI Architecture', slug: 'concepts/di-system' },
        { label: 'Language Support', slug: 'concepts/languages' },
        { label: 'Roadmap', slug: 'concepts/roadmap' },
      ],
    },
    {
      label: 'Guides',
      items: [
        { label: 'Configuration', slug: 'guides/configuration' },
        { label: 'Choosing a Profile', slug: 'guides/profiles' },
        { label: 'Resilience & Fallbacks', slug: 'guides/resilience' },
        { label: 'Local-Only Operation', slug: 'guides/local-only' },
        { label: 'Custom Providers', slug: 'guides/custom-providers' },
      ],
    },
    {
      label: 'Reference',
      items: [
        { label: 'CLI Reference', slug: 'cli' },
        {
          label: 'API Reference',
          collapsed: true,
          autogenerate: { directory: 'api', collapsed: true },
        },
      ],
    },
  ] as unknown as DocsTemplateOptions['sidebarConfig'],
};

const config = await createConfig(configOptions);

// Workaround: Remove cloudflare adapter for build. Astro 6 + @astrojs/cloudflare
// has unfixed vite 6 environment build bugs (withastro/astro#15650).
// Since this is output: "static", the adapter isn't needed for building.
// TODO: Re-enable once @astrojs/cloudflare publishes the fix from PR #15694
config.adapter = undefined;

// Add vite plugin to fix prerender entry location + env var workaround
config.vite = {
  ...config.vite,
  plugins: [...(config.vite?.plugins || []), fixPrerenderEntryPlugin()],
  // Workaround for @knitli/docs-components Footer using `const { env } = import.meta`
  // which doesn't work in Node.js (import.meta.env is set by vite but import.meta
  // itself doesn't have an env property when destructured in Node). This ensures
  // import.meta.env is statically replaced during build.
  define: {
    ...config.vite?.define,
    "import.meta.env.PUBLIC_DOCS_PRODUCT": JSON.stringify("CodeWeaver"),
  },
};


export default config;
