# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import os
import re


def update_imports(root_dir):
    pattern1 = re.compile(r'from codeweaver.providers.provider import ([^,\n]+(?:, [^,\n]+)*)')

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                # Skip the source file itself to avoid self-reference issues if we wanted
                # but here we WANT to update it too if it matches (though it shouldn't)
                if 'src/codeweaver/providers/provider.py' in path:
                    continue
                if 'src/codeweaver/core/types/provider.py' in path:
                    continue

                with open(path, 'r') as f:
                    content = f.read()

                new_content = content

                def replace_func(match):
                    imports = match.group(1)
                    # Check if it imports Provider or ProviderKind
                    if 'Provider' in imports or 'ProviderKind' in imports:
                        # If it only imports these, replace the whole line
                        # If it imports others too, it's more complex, but usually it's just these two.
                        # Let's check what else is in providers.provider.
                        # Provider, ProviderKind, ProviderEnvVars

                        import_list = [i.strip() for i in imports.split(',')]
                        core_imports = []
                        other_imports = []
                        for imp in import_list:
                            name = imp.split(' as ')[0]
                            if name in ['Provider', 'ProviderKind']:
                                core_imports.append(imp)
                            else:
                                other_imports.append(imp)

                        res = []
                        if core_imports:
                            res.append(f"from codeweaver.core.types.provider import {', '.join(core_imports)}")
                        if other_imports:
                            res.append(f"from codeweaver.providers.provider import {', '.join(other_imports)}")
                        return '\n'.join(res)
                    return match.group(0)

                new_content = pattern1.sub(replace_func, content)

                if new_content != content:
                    with open(path, 'w') as f:
                        f.write(new_content)
                    print(f"Updated {path}")

if __name__ == "__main__":
    update_imports('src/codeweaver')
