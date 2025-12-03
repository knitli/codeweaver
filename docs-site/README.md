<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Documentation Site

This is the Starlight-based documentation site for CodeWeaver.

## POC Status

This is a proof-of-concept migration from Material for MkDocs to Starlight. It includes:

✅ Starlight setup with Tailwind 4
✅ CodeWeaver branding (colors, logos)
✅ Griffe-based Python API documentation generation
✅ Sample migrated docs (Why CodeWeaver, CLI Reference)
✅ Auto-generated API reference for all modules

## Prerequisites

- Node.js 20+ (for Astro/Starlight)
- Python 3.11+ (for API doc generation)
- `griffe` installed: `pip install griffe`

## Installation

```bash
# Install Node dependencies
npm install

# Install Python dependencies (for API doc generation)
pip install griffe
```

## Development

```bash
# Generate API docs from Python source
npm run gen-api-docs

# Start dev server
npm run dev

# Open browser to http://localhost:4321
```

## Building

```bash
# Generate API docs and build site
npm run build

# Preview built site
npm run preview
```

## Project Structure

```
docs-site/
├── src/
│   ├── assets/           # Logos and images
│   ├── content/
│   │   └── docs/         # Documentation markdown files
│   │       ├── index.mdx      # Homepage
│   │       ├── why.md         # Why CodeWeaver
│   │       ├── cli.md         # CLI Reference
│   │       └── api/           # Auto-generated API docs
│   └── styles/
│       └── custom.css    # CodeWeaver branding + Tailwind config
├── public/               # Static assets (favicon, etc.)
├── astro.config.mjs      # Astro + Starlight configuration
└── package.json
```

## API Documentation Generation

API documentation is automatically generated from Python source code using Griffe.

The generator script (`/scripts/gen-api-docs.py`) extracts:
- Module, class, and function docstrings
- Google-style docstring sections (Args, Returns, Raises, Examples)
- Type annotations
- Pydantic model field descriptions (when available)

Generated files are placed in `src/content/docs/api/` and automatically indexed by Starlight.

## Branding

CodeWeaver branding is applied via Tailwind 4 in `src/styles/custom.css`:

**Colors:**
- Primary: `#455b6b` (slate blue)
- Secondary: `#b56c30` (bronze/orange)
- Accent: `#f7f3eb` (off-white)

**Logos:**
- Light mode: `codeweaver-primary.svg` (slate blue bird, orange accent)
- Dark mode: `codeweaver-reverse.svg` (orange bird, slate blue accent)

## Next Steps for Full Migration

See the full migration plan in the main project README. Key remaining tasks:

1. Migrate remaining markdown docs from `/docs/`
2. Set up GitHub Actions workflow for automated builds
3. Configure deployment (Cloudflare Pages or GitHub Pages)
4. Add plugins: RSS feed, social cards, git revision dates
5. Port custom JavaScript features (sortable tables, format blocks)
6. Remove old MkDocs configuration

## References

- [Starlight Documentation](https://starlight.astro.build/)
- [Astro Documentation](https://astro.build/)
- [Tailwind CSS v4](https://tailwindcss.com/blog/tailwindcss-v4)
- [Griffe](https://mkdocstrings.github.io/griffe/)
