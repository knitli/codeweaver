// SPDX-FileCopyrightText: 2026 Knitli Inc.
//
// SPDX-License-Identifier: MIT OR Apache-2.0

import createConfig from "@knitli/astro-docs-template/config";
import { DocsAssets } from "@knitli/docs-components";
import type { DocsTemplateOptions } from "@knitli/astro-docs-template/config";
import { remarkVersion } from "./src/plugins/remark-version";

const { codeweaverPrimary, codeweaverReverse } = DocsAssets;

const configOptions: DocsTemplateOptions = {
  appName: "CodeWeaver",
  description: "CodeWeaver is a code search engine for AI agents, designed to provide precise results that give agents exactly what they need for their tasks -- no more, no less.",
  rootDir: import.meta.dirname,
  llmConfig: {
    llmDescription: "CodeWeaver is an advanced code search engine tailored for AI agents, delivering precise and relevant code snippets to empower agents in their tasks. With a focus on accuracy and efficiency, CodeWeaver ensures that agents receive exactly what they need, enhancing their performance and capabilities. It uses state-of-the-art sparse and dense embeddings, model reranking, and a language-agnostic understanding of AST nodes to provide unmatched code search results. It exposes a single tool for agents to query of Model Context Protocol, `find_code`, which returns a ranked list of code and documentation snippets relevant to the agent's query.",
    promotePatterns: ["guides/installation", "guides/configuration", "guides/profiles", "guides/**", "reference/**", "examples/**", "api/**"],
    demotePatterns: ["_*", "contributors", "changelog*", "announcements", "contributing", "*code*conduct*", "*security*", "*license*"],
  },
  is_codeweaver: true,
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
  siderbarConfig: [
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
        { label: 'Provider Registry', slug: 'api/providers' },
        {
          label: 'API Reference',
          autogenerate: { directory: 'api' },
        },
      ],
    },
  ],
};

const config = createConfig(configOptions) as ReturnType<typeof createConfig>;

// Inject remark-version plugin for {{VERSION}} substitution in markdown
const existingRemarkPlugins = config.markdown?.remarkPlugins ?? [];
config.markdown = {
  ...config.markdown,
  remarkPlugins: [...existingRemarkPlugins, remarkVersion],
};

export default config;
