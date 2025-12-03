// SPDX-FileCopyrightText: 2025 Knitli Inc.
// SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
//
// SPDX-License-Identifier: MIT OR Apache-2.0

import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  integrations: [
    starlight({
      title: 'CodeWeaver',
      description: 'Official CodeWeaver documentation - semantic code search and understanding',
      logo: {
        light: './src/assets/codeweaver-primary.svg',
        dark: './src/assets/codeweaver-reverse.svg',
      },
      favicon: '/codeweaver-favico.png',
      social: {
        github: 'https://github.com/knitli/codeweaver',
      },
      customCss: [
        './src/styles/custom.css',
      ],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Why CodeWeaver?', slug: 'why' },
            { label: 'CLI Reference', slug: 'cli' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Publishing', slug: 'guides/publishing' },
            { label: 'Versioning', slug: 'guides/versioning' },
          ],
        },
        {
          label: 'Advanced',
          items: [
            { label: 'Vector Store Validation', slug: 'advanced/vector-store-validation' },
            { label: 'Indexer Deduplication', slug: 'advanced/indexer-deduplication-analysis' },
          ],
        },
        {
          label: 'Registry',
          items: [
            { label: 'Submission Guide', slug: 'registry/submission' },
          ],
        },
        {
          label: 'Docker',
          items: [
            { label: 'Build Notes', slug: 'docker/build-notes' },
          ],
        },
        {
          label: 'API Reference',
          autogenerate: { directory: 'api' },
        },
        {
          label: 'Development',
          items: [
            { label: 'Release Checklist', slug: 'dev/release-checklist' },
          ],
        },
      ],
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
