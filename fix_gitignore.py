with open(".gitignore", "r") as f:
    content = f.read()

content = content.replace("""<<<<<<< HEAD
.exportify/
!.exportify/config.toml
=======
.gemini/
gha-creds-*.json
.hypothesis/
>>>>>>> b6cc77c... 🧪 [Testing Improvement] Add tests for conditional branches in run""", """.exportify/
!.exportify/config.toml
.gemini/
gha-creds-*.json
.hypothesis/""")

with open(".gitignore", "w") as f:
    f.write(content)
