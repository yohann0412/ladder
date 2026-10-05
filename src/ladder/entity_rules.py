"""Per-language rules that say which syntax nodes are named definitions and how to name them."""

from collections.abc import Callable
from dataclasses import dataclass

from tree_sitter import Node

from ladder.syntax import walk

Namer = Callable[[Node, bytes], tuple[str, str] | None]


@dataclass(frozen=True)
class Rule:
    """How one definition node type becomes an entity.

    The namer returns the definition's own name and the name that qualifies the
    definitions nested in it (they differ for a Rust impl, whose methods are `Type.method`),
    or None when the node is not a definition after all.
    """

    kind: str
    namer: Namer
    holds_methods: bool = False


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _same(name: str) -> tuple[str, str]:
    return name, name


def _field(node: Node, source: bytes, field: str) -> str | None:
    child = node.child_by_field_name(field)
    return None if child is None else _text(child, source)


def _named(node: Node, source: bytes) -> tuple[str, str] | None:
    name = _field(node, source, "name")
    return None if name is None else _same(name)


def _named_with_body(node: Node, source: bytes) -> tuple[str, str] | None:
    return None if node.child_by_field_name("body") is None else _named(node, source)


def _first_type(node: Node, source: bytes) -> str | None:
    found = next((n for n in walk(node) if n.type == "type_identifier"), None)
    return None if found is None else _text(found, source)


def _go_method(node: Node, source: bytes) -> tuple[str, str] | None:
    name = _field(node, source, "name")
    receiver = node.child_by_field_name("receiver")
    owner = None if receiver is None else _first_type(receiver, source)
    if name is None:
        return None
    return _same(name if owner is None else f"{owner}.{name}")


def _rust_impl(node: Node, source: bytes) -> tuple[str, str] | None:
    target = node.child_by_field_name("type")
    if target is None:
        return None
    owner = _first_type(target, source) or _text(target, source)
    trait = _field(node, source, "trait")
    implemented = _text(target, source)
    name = f"impl {implemented}" if trait is None else f"impl {trait} for {implemented}"
    return name, owner


C_NAME_TYPES = frozenset(
    {
        "identifier",
        "field_identifier",
        "qualified_identifier",
        "destructor_name",
        "operator_name",
        "template_function",
    }
)


def _c_function(node: Node, source: bytes) -> tuple[str, str] | None:
    current = node.child_by_field_name("declarator")
    while current is not None and current.type not in C_NAME_TYPES:
        inner = current.child_by_field_name("declarator")
        named = current.named_children
        current = inner if inner is not None else (named[0] if named else None)
    return None if current is None else _same(_text(current, source))


JS_FUNCTION_VALUES = frozenset(
    {"arrow_function", "function_expression", "function", "generator_function"}
)


def _js_top_level_function(node: Node, source: bytes) -> tuple[str, str] | None:
    value = node.child_by_field_name("value")
    name = node.child_by_field_name("name")
    holder = None if node.parent is None else node.parent.parent
    if holder is not None and holder.type == "export_statement":
        holder = holder.parent
    if value is None or name is None or holder is None:
        return None
    if value.type not in JS_FUNCTION_VALUES or name.type != "identifier":
        return None
    return None if holder.type != "program" else _same(_text(name, source))


def _js_class_member(node: Node, source: bytes) -> tuple[str, str] | None:
    parent = node.parent
    if parent is None or parent.type not in ("class_body", "interface_body", "object_type"):
        return None
    return _named(node, source)


def _ruby_singleton_method(node: Node, source: bytes) -> tuple[str, str] | None:
    name = _field(node, source, "name")
    owner = _field(node, source, "object")
    if name is None:
        return None
    return _same(name if owner is None else f"{owner}.{name}")


def _ruby_singleton_class(node: Node, source: bytes) -> tuple[str, str] | None:
    owner = _field(node, source, "value")
    return None if owner is None else _same(owner)


FUNCTION = Rule("function", _named)
C_FUNCTION = Rule("function", _c_function)
CONTAINER_RULES = {
    "struct_specifier": Rule("struct", _named_with_body, holds_methods=True),
    "union_specifier": Rule("union", _named_with_body, holds_methods=True),
    "enum_specifier": Rule("enum", _named_with_body, holds_methods=True),
}
JAVASCRIPT_RULES = {
    "function_declaration": FUNCTION,
    "generator_function_declaration": FUNCTION,
    "class_declaration": Rule("class", _named, holds_methods=True),
    "method_definition": Rule("method", _js_class_member),
    "variable_declarator": Rule("function", _js_top_level_function),
}
TYPESCRIPT_RULES = {
    **JAVASCRIPT_RULES,
    "abstract_class_declaration": Rule("class", _named, holds_methods=True),
    "abstract_method_signature": Rule("method", _js_class_member),
    "method_signature": Rule("method", _js_class_member),
    "interface_declaration": Rule("interface", _named, holds_methods=True),
    "type_alias_declaration": Rule("type", _named),
    "enum_declaration": Rule("enum", _named),
}
RULES: dict[str, dict[str, Rule]] = {
    "python": {
        "function_definition": FUNCTION,
        "class_definition": Rule("class", _named, holds_methods=True),
    },
    "javascript": JAVASCRIPT_RULES,
    "typescript": TYPESCRIPT_RULES,
    "tsx": TYPESCRIPT_RULES,
    "go": {
        "function_declaration": FUNCTION,
        "method_declaration": Rule("method", _go_method),
        "type_spec": Rule("type", _named),
        "type_alias": Rule("type", _named),
    },
    "rust": {
        "function_item": FUNCTION,
        "function_signature_item": FUNCTION,
        "struct_item": Rule("struct", _named, holds_methods=True),
        "enum_item": Rule("enum", _named, holds_methods=True),
        "union_item": Rule("union", _named, holds_methods=True),
        "trait_item": Rule("trait", _named, holds_methods=True),
        "impl_item": Rule("impl", _rust_impl, holds_methods=True),
        "mod_item": Rule("module", _named_with_body),
        "type_item": Rule("type", _named),
        "macro_definition": Rule("macro", _named),
    },
    "java": {
        "class_declaration": Rule("class", _named, holds_methods=True),
        "interface_declaration": Rule("interface", _named, holds_methods=True),
        "enum_declaration": Rule("enum", _named, holds_methods=True),
        "record_declaration": Rule("record", _named, holds_methods=True),
        "annotation_type_declaration": Rule("annotation", _named, holds_methods=True),
        "method_declaration": Rule("method", _named),
        "constructor_declaration": Rule("constructor", _named),
    },
    "c_sharp": {
        "class_declaration": Rule("class", _named, holds_methods=True),
        "interface_declaration": Rule("interface", _named, holds_methods=True),
        "struct_declaration": Rule("struct", _named, holds_methods=True),
        "enum_declaration": Rule("enum", _named, holds_methods=True),
        "record_declaration": Rule("record", _named, holds_methods=True),
        "method_declaration": Rule("method", _named),
        "constructor_declaration": Rule("constructor", _named),
        "local_function_statement": FUNCTION,
    },
    "scala": {
        "class_definition": Rule("class", _named, holds_methods=True),
        "object_definition": Rule("object", _named, holds_methods=True),
        "trait_definition": Rule("trait", _named, holds_methods=True),
        "enum_definition": Rule("enum", _named, holds_methods=True),
        "function_definition": FUNCTION,
        "function_declaration": FUNCTION,
    },
    "c": {"function_definition": C_FUNCTION, **CONTAINER_RULES},
    "cpp": {
        "function_definition": C_FUNCTION,
        "class_specifier": Rule("class", _named_with_body, holds_methods=True),
        **CONTAINER_RULES,
    },
    "ruby": {
        "class": Rule("class", _named, holds_methods=True),
        "module": Rule("module", _named, holds_methods=True),
        "singleton_class": Rule("singleton_class", _ruby_singleton_class, holds_methods=True),
        "method": FUNCTION,
        "singleton_method": Rule("function", _ruby_singleton_method),
    },
    "php": {
        "function_definition": FUNCTION,
        "class_declaration": Rule("class", _named, holds_methods=True),
        "interface_declaration": Rule("interface", _named, holds_methods=True),
        "trait_declaration": Rule("trait", _named, holds_methods=True),
        "enum_declaration": Rule("enum", _named, holds_methods=True),
        "method_declaration": Rule("method", _named),
    },
    "bash": {"function_definition": FUNCTION},
}
