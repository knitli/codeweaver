import re

with open("src/codeweaver/core/types/service_cards.py", "r") as f:
    content = f.read()

# Make sure we don't accidentally catch and hide ValueError if `_apply_handler` causes one.
old_block = """        except (ImportError, AttributeError, KeyError, ValueError) as e:
            raise ValueError(
                f"Failed to resolve {target} class for provider {self.provider} and category {self.category}. Reason: {e}"
            ) from None"""

new_block = """        except (ImportError, AttributeError, KeyError):
            raise ValueError(
                f"Failed to resolve {target} class for provider {self.provider} and category {self.category}."
            ) from None"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/core/types/service_cards.py", "w") as f:
    f.write(content)
