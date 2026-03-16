with open("src/codeweaver/providers/reranking/providers/fastembed.py", "r") as f:
    content = f.read()

old_block = """        else:
            return response.tolist()"""

new_block = """        else:
            if hasattr(response, "tolist"):
                return response.tolist()
            return list(response)"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/reranking/providers/fastembed.py", "w") as f:
    f.write(content)
