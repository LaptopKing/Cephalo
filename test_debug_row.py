f = open(r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\test_debug.log", "w", encoding="utf-8")
import sys
from pathlib import Path
import tree_sitter
import tree_sitter_python

py_lang = tree_sitter.Language(tree_sitter_python.language())
parser = tree_sitter.Parser(py_lang)
p = Path(r"C:\Users\strider-desktop\.gemini\antigravity\scratch\second-brain\brain.py")
content = p.read_bytes()
lines = content.split(b"\n")

tree = parser.parse(content)
f.write("Parsed brain.py with cursor\n")
f.flush()

cursor = tree.walk()
visited = 0
symbols = []

# Depth-first traversal using cursor
has_more = True
while has_more:
    node = cursor.node
    visited += 1
    if node.type in ("function_definition", "class_definition"):
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode('utf-8', 'ignore') if name_node else 'none'
        row = node.start_point.row
        line_str = lines[row].decode('utf-8', 'ignore').strip() if row < len(lines) else ""
        symbols.append((name, node.type, row + 1, line_str))
        f.write(f"Sym #{len(symbols)}: {name} ({node.type}) at row {row+1}: {line_str[:40]}\n")
        f.flush()

    if cursor.goto_first_child():
        continue
    if cursor.goto_next_sibling():
        continue
    
    # backtrack
    backtrack = True
    while backtrack:
        if not cursor.goto_parent():
            has_more = False
            break
        if cursor.goto_next_sibling():
            break

f.write(f"Cursor finished cleanly! Visited {visited} nodes, extracted {len(symbols)} symbols!\n")
f.flush()
f.close()
import os
os._exit(0)
