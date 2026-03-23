// SPDX-FileCopyrightText: 2025 Knitli Inc.
// SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
//
// SPDX-License-Identifier: MIT OR Apache-2.0

import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

import starlightChangelogs from 'starlight-changelogs';
import starlightLinksValidator from 'starlight-links-validator'
import starlightScrollToTop from 'starlight-scroll-to-top';
import { starlightIconsPlugin, starlightIconsIntegration } from 'starlight-plugin-icons';
import starlightPageActions from 'starlight-page-actions';
import astroD2 from 'astro-d2';
import markdoc from '@astrojs/markdoc';

// https://astro.build/config
export default defineConfig({
  integrations: [starlight({
    title: 'CodeWeaver',
    description: 'Official CodeWeaver documentation - semantic code search and understanding',
    logo: {
      light: './src/assets/codeweaver-primary.svg',
      dark: './src/assets/codeweaver-reverse.svg',
    },
    favicon: '/codeweaver-favico.png',

    social: [
      {
        label: 'GitHub',
        icon: 'github',
        href: 'https://github.com/knitli/codeweaver',
      },
    ],
    components: {
      PageFrame: '@knitli/docs-components/PageFrame.astro',
      Footer: '@knitli/docs-components/Footer.astro',
    },
    customCss: [
      '@knitli/docs-components/assets/styles/variables.css',
      './src/styles/custom.css',
    ],
    sidebar: [
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
          { label: 'Roadmap to Alpha 7', slug: 'concepts/roadmap' },
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
    plugins: [
      starlightLinksValidator(),
      starlightScrollToTop({ showOnHomepage: false }),
      starlightChangelogs(),
      starlightIconsPlugin(),
      starlightPageActions({ actions: { claude: true, chatgpt: true, markdown: true }, share: true }),
    ],
  }), starlightIconsIntegration(), astroD2({ skipGeneration: true }), markdoc()],
  vite: {
    plugins: [],
    define: {
      'import.meta.env.PUBLIC_DOCS_PRODUCT': JSON.stringify('CodeWeaver'),
    },
  },
});
