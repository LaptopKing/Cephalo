#!/usr/bin/env python3
"""
Cephalo - AST Code Symbol & Definition Indexer (symbol_extractor.py)
===================================================================
Token-efficient Abstract Syntax Tree (AST) code symbol search engine inspired
by XERJ's 'def' primitive. Replaces wasteful full-file grepping by parsing source
code into AST nodes and returning exact definitions, line numbers, and signatures.

Supported Languages (via Tree-sitter):
- Python (.py)
- TypeScript / TSX (.ts, .tsx)
- JavaScript / JSX (.js, .jsx)
- Go (.go)
- Rust (.rs)
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Force UTF-8 on Windows terminal/pipes
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("cephalo.symbol_extractor")

# Try importing tree-sitter and language modules
HAS_TREE_SITTER = False
PARSERS: Dict[str, Any] = {}

try:
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_go
    import tree_sitter_rust

    py_lang = tree_sitter.Language(tree_sitter_python.language())
    PARSERS[".py"] = (tree_sitter.Parser(py_lang), "python")

    js_lang = tree_sitter.Language(tree_sitter_javascript.language())
    PARSERS[".js"] = (tree_sitter.Parser(js_lang), "javascript")
    PARSERS[".jsx"] = (tree_sitter.Parser(js_lang), "javascript")

    ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    PARSERS[".ts"] = (tree_sitter.Parser(ts_lang), "typescript")

    tsx_lang = tree_sitter.Language(tree_sitter_typescript.language_tsx())
    PARSERS[".tsx"] = (tree_sitter.Parser(tsx_lang), "tsx")

    go_lang = tree_sitter.Language(tree_sitter_go.language())
    PARSERS[".go"] = (tree_sitter.Parser(go_lang), "go")

    rust_lang = tree_sitter.Language(tree_sitter_rust.language())
    PARSERS[".rs"] = (tree_sitter.Parser(rust_lang), "rust")

    HAS_TREE_SITTER = True
except Exception as e:
    logger.debug(f"Tree-sitter initialization failed ({e}), fallback regex enabled.")
    HAS_TREE_SITTER = False


IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".cache",
    ".turbo",
    "coverage",
    "target",
    "data",
}


@dataclass
class SymbolDefinition:
    name: str
    kind: str  # function, class, interface, type, struct, method
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    language: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        loc = f"{self.file_path}#L{self.start_line}-L{self.end_line}"
        doc_part = f"\n  > {self.docstring}" if self.docstring else ""
        return (
            f"- **`{self.name}`** (`{self.kind}`) — [{self.file_path}:L{self.start_line}](file:///{self.file_path.replace(os.sep, '/')})\n"
            f"  ```\n  {self.signature}\n  ```{doc_part}"
        )


class CodeSymbolIndexer:
    """
    Traverses codebases, parses AST nodes, and queries symbols and definitions.
    """

    SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path(__file__).resolve().parent).resolve()

    def find_definitions(
        self,
        symbol_name: str,
        target_dir: Optional[Path] = None,
        exact: bool = False,
        max_results: int = 20,
    ) -> List[SymbolDefinition]:
        """
        Searches the target directory for functions, classes, and types matching symbol_name.
        """
        search_dir = (target_dir or self.root_dir).resolve()
        results: List[SymbolDefinition] = []
        pattern = re.compile(f"^{re.escape(symbol_name)}$" if exact else re.escape(symbol_name), re.IGNORECASE)

        for file_path in self._walk_source_files(search_dir):
            if len(results) >= max_results:
                break
            try:
                symbols = self.extract_symbols_from_file(file_path)
                for sym in symbols:
                    if pattern.search(sym.name):
                        results.append(sym)
                        if len(results) >= max_results:
                            break
            except Exception as e:
                logger.debug(f"Failed to extract symbols from {file_path}: {e}")

        return results

    def extract_symbols_from_file(self, file_path: Path) -> List[SymbolDefinition]:
        """Extracts AST symbols from a single code file."""
        ext = file_path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return []

        try:
            content_bytes = file_path.read_bytes()
        except Exception:
            return []

        rel_path = str(file_path)
        try:
            rel_path = str(file_path.relative_to(self.root_dir))
        except ValueError:
            pass

        if HAS_TREE_SITTER and ext in PARSERS:
            return self._extract_tree_sitter_symbols(file_path, content_bytes, rel_path, ext)
        elif ext == ".py":
            return self._extract_python_ast_symbols(content_bytes, rel_path)
        else:
            return self._extract_regex_symbols(content_bytes, rel_path, ext)

    def _walk_source_files(self, base_dir: Path):
        """Yields supported source code files, skipping ignored directories."""
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    yield Path(root) / file

    def _extract_tree_sitter_symbols(
        self,
        file_path: Path,
        content_bytes: bytes,
        rel_path: str,
        ext: str,
    ) -> List[SymbolDefinition]:
        parser, lang_name = PARSERS[ext]
        try:
            tree = parser.parse(content_bytes)
        except Exception:
            return []

        lines = content_bytes.split(b"\n")
        symbols: List[SymbolDefinition] = []

        def get_line_text(start_row: int, end_row: int) -> str:
            sub = lines[start_row : min(end_row + 1, len(lines))]
            return b"\n".join(sub).decode("utf-8", errors="ignore").strip()

        def get_node_text(node) -> str:
            return node.text.decode("utf-8", errors="ignore").strip()

        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            node_type = node.type

            # Python function & class
            if lang_name == "python":
                if node_type == "function_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_node_text(name_node)
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=name,
                                kind="function",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="python",
                            )
                        )
                elif node_type == "class_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_node_text(name_node)
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=name,
                                kind="class",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="python",
                            )
                        )

            # TypeScript / JavaScript
            elif lang_name in ("typescript", "tsx", "javascript"):
                if node_type in ("function_declaration", "generator_function_declaration"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="function",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language=lang_name,
                            )
                        )
                elif node_type == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="class",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language=lang_name,
                            )
                        )
                elif node_type == "interface_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="interface",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language=lang_name,
                            )
                        )
                elif node_type == "type_alias_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="type",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language=lang_name,
                            )
                        )

            # Go
            elif lang_name == "go":
                if node_type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="function",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="go",
                            )
                        )
                elif node_type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="method",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="go",
                            )
                        )
                elif node_type == "type_declaration":
                    first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                    m = re.search(r"type\s+([A-Za-z0-9_]+)\s+(struct|interface)", first_line)
                    if m:
                        symbols.append(
                            SymbolDefinition(
                                name=m.group(1),
                                kind=m.group(2),
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="go",
                            )
                        )

            # Rust
            elif lang_name == "rust":
                if node_type == "function_item":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind="function",
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="rust",
                            )
                        )
                elif node_type in ("struct_item", "enum_item", "trait_item"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        kind = node_type.replace("_item", "")
                        first_line = lines[node.start_point.row].decode("utf-8", errors="ignore").strip()
                        symbols.append(
                            SymbolDefinition(
                                name=get_node_text(name_node),
                                kind=kind,
                                file_path=rel_path,
                                start_line=node.start_point.row + 1,
                                end_line=node.end_point.row + 1,
                                signature=first_line,
                                language="rust",
                            )
                        )

            if node.children:
                stack.extend(reversed(node.children))

        return symbols

    def _extract_python_ast_symbols(self, content_bytes: bytes, rel_path: str) -> List[SymbolDefinition]:
        """Fallback Python AST parser using standard library."""
        try:
            tree = ast.parse(content_bytes)
        except Exception:
            return []

        symbols: List[SymbolDefinition] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = f"def {node.name}(...)"
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="function",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=sig,
                        docstring=ast.get_docstring(node),
                        language="python",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                sig = f"class {node.name}"
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="class",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=sig,
                        docstring=ast.get_docstring(node),
                        language="python",
                    )
                )
        return symbols

    def _extract_regex_symbols(self, content_bytes: bytes, rel_path: str, ext: str) -> List[SymbolDefinition]:
        """Ultra-fast regex fallback when tree-sitter grammar is unavailable."""
        text = content_bytes.decode("utf-8", errors="ignore")
        lines = text.split("\n")
        symbols: List[SymbolDefinition] = []

        patterns = [
            (r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", "function"),
            (r"^(?:export\s+)?class\s+([A-Za-z0-9_$]+)", "class"),
            (r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", "interface"),
            (r"^(?:export\s+)?type\s+([A-Za-z0-9_$]+)", "type"),
            (r"^func\s+(?:\([^\)]+\)\s+)?([A-Za-z0-9_]+)\s*\(", "function"),
            (r"^(?:pub\s+)?fn\s+([A-Za-z0-9_]+)", "function"),
            (r"^(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)", "struct"),
        ]

        for i, line in enumerate(lines, 1):
            s_line = line.strip()
            for pat, kind in patterns:
                m = re.search(pat, s_line)
                if m:
                    symbols.append(
                        SymbolDefinition(
                            name=m.group(1),
                            kind=kind,
                            file_path=rel_path,
                            start_line=i,
                            end_line=i,
                            signature=s_line,
                            language=ext.lstrip("."),
                        )
                    )
                    break
        return symbols


if __name__ == "__main__":
    import sys
    indexer = CodeSymbolIndexer()
    query = sys.argv[1] if len(sys.argv) > 1 else "search"
    matches = indexer.find_definitions(query)
    print(f"Found {len(matches)} symbols matching '{query}':")
    for m in matches:
        print(m.to_markdown())
