import sys
import os
from pathlib import Path

# Set int digits limit to 0 (unlimited)
sys.set_int_max_str_digits(0)

p = Path(r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\auto_harvest.py")
content = p.read_bytes()

import tree_sitter
import tree_sitter_python
py_lang = tree_sitter.Language(tree_sitter_python.language())
parser = tree_sitter.Parser(py_lang)
tree = parser.parse(content)

stack = [tree.root_node]
i = 0
with open(r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\test_debug.log", "w", encoding="utf-8") as f:
    while stack:
        node = stack.pop()
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode('utf-8', 'ignore') if name_node else 'none'
            sp = node.start_point
            ep = node.end_point
            f.write(f"Fn {i}: {name}, sp={sp!r}, ep={ep!r}\n")
            f.flush()
            i += 1
        if node.children:
            stack.extend(reversed(node.children))

os._exit(0)
