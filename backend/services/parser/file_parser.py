"""Tree-sitter-based file parser.

Responsibility: parse a single source file using the appropriate Tree-sitter
grammar and extract a FileAnalysis. Language support is limited to grammars
available as standalone packages (Python, JavaScript, TypeScript, Go).

Other languages in SUPPORTED_EXTENSIONS are recognized but not parsed —
they receive a FileAnalysis with parse_succeeded=False and a clear reason.
"""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Node, Parser

from shared.types.enums import DefinitionKind
from shared.types.pcr_types import DefinitionSummary, FileAnalysis

_PARSEABLE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go",
})


def _load_languages() -> dict[str, Language]:
    """Load available Tree-sitter languages. Returns only successfully loaded ones."""
    langs: dict[str, Language] = {}
    try:
        import tree_sitter_python as tsp
        langs["Python"] = Language(tsp.language())
    except Exception:
        pass
    try:
        import tree_sitter_javascript as tsj
        langs["JavaScript"] = Language(tsj.language())
    except Exception:
        pass
    try:
        import tree_sitter_typescript as tst
        langs["TypeScript"] = Language(tst.language_typescript())
        langs["TypeScriptX"] = Language(tst.language_tsx())
    except Exception:
        pass
    try:
        import tree_sitter_go as tsg
        langs["Go"] = Language(tsg.language())
    except Exception:
        pass
    return langs


_LANGUAGES: dict[str, Language] = _load_languages()

_EXTENSION_TO_LANG_KEY: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScriptX",
    ".go": "Go",
}


def parse_file(path: str, language: str, is_test_file: bool) -> FileAnalysis:
    """Parse a single source file and return a FileAnalysis.

    Args:
        path: Relative file path from repository root.
        language: Language string from the manifest (e.g. "Python").
        is_test_file: Passed through from the FileEntry.

    Returns:
        FileAnalysis with structural signals extracted, or with
        parse_succeeded=False if the file could not be parsed.
    """
    ext = Path(path).suffix.lower()

    if ext not in _PARSEABLE_EXTENSIONS:
        return _unparseable(path, language, is_test_file,
                            f"No Tree-sitter grammar available for '{language}'")

    lang_key = _EXTENSION_TO_LANG_KEY.get(ext)
    ts_language = _LANGUAGES.get(lang_key) if lang_key else None

    if ts_language is None:
        return _unparseable(path, language, is_test_file,
                            f"Tree-sitter grammar for '{language}' failed to load")

    return _parse_with_language(path, language, is_test_file, ts_language)


def parse_file_bytes(
    path: str,
    language: str,
    is_test_file: bool,
    source: bytes,
) -> FileAnalysis:
    """Parse pre-read file bytes. Used internally and in tests."""
    ext = Path(path).suffix.lower()
    lang_key = _EXTENSION_TO_LANG_KEY.get(ext)
    ts_language = _LANGUAGES.get(lang_key) if lang_key else None

    if ts_language is None:
        return _unparseable(path, language, is_test_file,
                            f"No grammar for '{language}'")

    return _parse_bytes(path, language, is_test_file, ts_language, source)


def _parse_with_language(
    path: str,
    language: str,
    is_test_file: bool,
    ts_language: Language,
) -> FileAnalysis:
    try:
        source = Path(path).read_bytes()
    except OSError as exc:
        return _unparseable(path, language, is_test_file, f"IO error: {exc}")
    return _parse_bytes(path, language, is_test_file, ts_language, source)


def _parse_bytes(
    path: str,
    language: str,
    is_test_file: bool,
    ts_language: Language,
    source: bytes,
) -> FileAnalysis:
    parser = Parser(ts_language)
    tree = parser.parse(source)
    root = tree.root_node

    has_errors = root.has_error
    error_summary: str | None = None
    if has_errors:
        error_summary = "Tree-sitter detected syntax errors in this file"

    lines = source.decode("utf-8", errors="replace").splitlines()
    imports = _extract_imports(root, language)
    exports = _extract_exports(root, language)
    definitions = _extract_definitions(root, language)
    max_depth = _compute_max_nesting(root)
    complexity = _compute_complexity_proxy(root)

    return FileAnalysis(
        path=path,
        language=language,
        import_list=imports,
        export_list=exports,
        definition_summaries=definitions,
        max_nesting_depth=max_depth,
        complexity_proxy=complexity,
        is_test_file=is_test_file,
        parse_succeeded=not has_errors,
        parse_error_summary=error_summary,
    )


def _unparseable(
    path: str,
    language: str,
    is_test_file: bool,
    reason: str,
) -> FileAnalysis:
    return FileAnalysis(
        path=path,
        language=language,
        import_list=[],
        export_list=[],
        definition_summaries=[],
        max_nesting_depth=0,
        complexity_proxy=0,
        is_test_file=is_test_file,
        parse_succeeded=False,
        parse_error_summary=reason,
    )


# ---------------------------------------------------------------------------
# Node visitors
# ---------------------------------------------------------------------------

def _extract_imports(root: Node, language: str) -> list[str]:
    results: list[str] = []
    _walk(root, _IMPORT_NODE_TYPES.get(language, set()), results,
          extractor=_import_text)
    return results


def _extract_exports(root: Node, language: str) -> list[str]:
    results: list[str] = []
    _walk(root, _EXPORT_NODE_TYPES.get(language, set()), results,
          extractor=_export_text)
    return results


def _extract_definitions(
    root: Node,
    language: str,
) -> list[DefinitionSummary]:
    results: list[DefinitionSummary] = []
    _collect_definitions(root, language, results)
    return results


def _walk(
    node: Node,
    target_types: set[str],
    results: list[str],
    extractor: object,
) -> None:
    if node.type in target_types:
        text = extractor(node)  # type: ignore[operator]
        if text:
            results.append(text)
    for child in node.children:
        _walk(child, target_types, results, extractor)


def _import_text(node: Node) -> str | None:
    return node.text.decode("utf-8", errors="replace").split("\n")[0][:200]


def _export_text(node: Node) -> str | None:
    return node.text.decode("utf-8", errors="replace").split("\n")[0][:200]


_IMPORT_NODE_TYPES: dict[str, set[str]] = {
    "Python": {"import_statement", "import_from_statement"},
    "JavaScript": {"import_statement", "import_declaration"},
    "TypeScript": {"import_statement", "import_declaration"},
    "TypeScriptX": {"import_statement", "import_declaration"},
    "Go": {"import_declaration", "import_spec"},
}

_EXPORT_NODE_TYPES: dict[str, set[str]] = {
    "JavaScript": {"export_statement"},
    "TypeScript": {"export_statement"},
    "TypeScriptX": {"export_statement"},
}


def _collect_definitions(
    node: Node,
    language: str,
    results: list[DefinitionSummary],
) -> None:
    defn = _try_extract_definition(node, language)
    if defn:
        results.append(defn)
    for child in node.children:
        _collect_definitions(child, language, results)


def _try_extract_definition(
    node: Node,
    language: str,
) -> DefinitionSummary | None:
    kind = _DEFINITION_NODE_TO_KIND.get(language, {}).get(node.type)
    if kind is None:
        return None

    name = _get_definition_name(node)
    if not name:
        return None

    start_line = node.start_point[0]
    end_line = node.end_point[0]
    line_count = max(0, end_line - start_line + 1)
    param_count = _count_parameters(node)
    has_docstring = _has_docstring(node, language)

    return DefinitionSummary(
        name=name,
        kind=kind,
        line_count=line_count,
        parameter_count=param_count,
        has_docstring=has_docstring,
    )


_DEFINITION_NODE_TO_KIND: dict[str, dict[str, DefinitionKind]] = {
    "Python": {
        "function_definition": DefinitionKind.FUNCTION,
        "class_definition": DefinitionKind.CLASS,
    },
    "JavaScript": {
        "function_declaration": DefinitionKind.FUNCTION,
        "arrow_function": DefinitionKind.FUNCTION,
        "class_declaration": DefinitionKind.CLASS,
        "method_definition": DefinitionKind.METHOD,
    },
    "TypeScript": {
        "function_declaration": DefinitionKind.FUNCTION,
        "arrow_function": DefinitionKind.FUNCTION,
        "class_declaration": DefinitionKind.CLASS,
        "method_definition": DefinitionKind.METHOD,
    },
    "TypeScriptX": {
        "function_declaration": DefinitionKind.FUNCTION,
        "arrow_function": DefinitionKind.FUNCTION,
        "class_declaration": DefinitionKind.CLASS,
        "method_definition": DefinitionKind.METHOD,
    },
    "Go": {
        "function_declaration": DefinitionKind.FUNCTION,
        "method_declaration": DefinitionKind.METHOD,
    },
}


def _get_definition_name(node: Node) -> str | None:
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "field_identifier"):
            return child.text.decode("utf-8", errors="replace")
    return None


def _count_parameters(node: Node) -> int:
    for child in node.children:
        if child.type in ("parameters", "formal_parameters", "parameter_list"):
            return sum(
                1 for c in child.children
                if c.type not in ("(", ")", ",", "comment")
            )
    return 0


def _has_docstring(node: Node, language: str) -> bool:
    if language != "Python":
        return False
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for inner in stmt.children:
                        if inner.type == "string":
                            return True
                    return False
    return False


_BRANCH_NODE_TYPES: frozenset[str] = frozenset({
    "if_statement", "elif_clause", "else_clause",
    "match_statement", "case_clause",
    "ternary_expression", "conditional_expression",
    "binary_expression",
})

_LOOP_NODE_TYPES: frozenset[str] = frozenset({
    "for_statement", "while_statement", "do_statement",
    "for_in_statement", "enhanced_for_statement",
})

_NESTING_NODE_TYPES: frozenset[str] = frozenset({
    "if_statement", "elif_clause", "for_statement", "while_statement",
    "try_statement", "with_statement", "match_statement",
    "do_statement", "block",
})


def _compute_complexity_proxy(root: Node) -> int:
    branches = _count_node_types(root, _BRANCH_NODE_TYPES)
    loops = _count_node_types(root, _LOOP_NODE_TYPES)
    return branches + loops


def _count_node_types(node: Node, target_types: frozenset[str]) -> int:
    count = 1 if node.type in target_types else 0
    return count + sum(_count_node_types(c, target_types) for c in node.children)


def _compute_max_nesting(root: Node, current_depth: int = 0) -> int:
    if _node_increases_nesting(root):
        current_depth += 1
    if not root.children:
        return current_depth
    return max(
        _compute_max_nesting(child, current_depth)
        for child in root.children
    )


def _node_increases_nesting(node: Node) -> bool:
    return node.type in _NESTING_NODE_TYPES
