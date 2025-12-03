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
      social: [
        {
          label: 'GitHub',
          icon: 'github',
          href: 'https://github.com/knitli/codeweaver',
        },
      ],
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
          label: 'API Reference',
          link: '/api/',
        },
      ],
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
