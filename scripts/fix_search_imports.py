# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import os


def update_search_imports(root_dir):
    old_import = "codeweaver.engine.search"
    new_import = "codeweaver.providers.vector_stores.search"

    for root, _dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()

                if old_import in content:
                    new_content = content.replace(old_import, new_import)
                    with open(path, "w") as f:
                        f.write(new_content)
                    print(f"Updated {path}")


if __name__ == "__main__":
    update_search_imports("src/codeweaver")
    update_search_imports("tests")
