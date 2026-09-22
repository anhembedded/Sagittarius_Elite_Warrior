"""The AST resolver `test_guard_scans_its_registered_root.py` (`BOT-142`)
reads a guard's real `.glob`/`.rglob` calls through — split into its own file
so the guard-file itself stays under `architecture-rule.md` §5.4's 400-line
threshold (review finding on `BOT-142`'s own PR).

Handles: a literal `/`-chain from a `parents[N]` hop or a same-file landmark
function (`_repo_root()`/`_bot_root()`); simple aliasing
(`_DOMAIN_DIR = _SCRIPTS_DIR`); a tuple of such chains iterated in a
`for`/comprehension. What it deliberately does not handle — an imported root
table, a root behind a function parameter, a bare-string tuple joined at the
call site, a non-literal pattern, a runtime-discovered subdirectory, or no
glob call at all — is named per-guard in `test_guard_scans_its_registered_
root.py`'s own `_UNRESOLVABLE_GUARDS`, not here: this module only resolves,
it does not decide what counts as in or out of scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

GLOB_METHODS = frozenset({"glob", "rglob"})


def is_parents_hop(node: ast.expr) -> bool:
    """`Path(__file__).resolve().parents[N]` — a repo-root landmark hop."""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and isinstance(node.value.value, ast.Call)
        and isinstance(node.value.value.func, ast.Attribute)
        and node.value.value.func.attr == "resolve"
    )


def is_landmark_root_function(func_def: ast.FunctionDef) -> bool:
    """A zero-argument function that walks `Path(__file__).resolve().parents`
    looking for a landmark file — the shape every guard's own local
    `_repo_root()`/`_bot_root()` helper uses instead of a hop count
    (`test_no_root_is_found_by_counting.py`'s own rule is why)."""
    if func_def.args.args or func_def.args.vararg or func_def.args.kwarg:
        return False
    dumped = ast.dump(func_def)
    return "__file__" in dumped and "parents" in dumped


def root_variable_names(tree: ast.Module) -> set[str]:
    """Every name (any scope) bound to 'the repository root': a direct
    `parents[N]` hop, or a call to a same-file landmark-search function."""
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        value = node.value
        is_landmark_call = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in functions
            and is_landmark_root_function(functions[value.func.id])
        )
        if is_parents_hop(value) or is_landmark_call:
            roots.add(name)
    return roots


def literal_chain(node: ast.expr, roots: set[str], paths: dict[str, str]) -> str | None:
    """The repo-root-relative path a `/`-chain, alias or root reference
    builds, or `None` if it involves anything else (a loop variable, a
    function parameter, an imported name)."""
    if is_parents_hop(node):
        return ""
    if isinstance(node, ast.Name):
        if node.id in roots:
            return ""
        return paths.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = literal_chain(node.left, roots, paths)
        if left is None:
            return None
        if not isinstance(node.right, ast.Constant) or not isinstance(
            node.right.value, str
        ):
            return None
        segment = node.right.value
        return f"{left}/{segment}" if left else segment
    return None


def literal_list(
    node: ast.expr,
    roots: set[str],
    paths: dict[str, str],
    tuple_paths: dict[str, list[str]],
) -> list[str] | None:
    """A `Tuple`/`List` of chains (or a name already resolved to one),
    resolved element-by-element, or `None` if any element is not a literal
    chain (a bare string, a loop variable, ...)."""
    if isinstance(node, ast.Name):
        return tuple_paths.get(node.id)
    if isinstance(node, (ast.Tuple, ast.List)):
        resolved: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                inner = literal_list(element.value, roots, paths, tuple_paths)
                if inner is None:
                    return None
                resolved.extend(inner)
                continue
            chain = literal_chain(element, roots, paths)
            if chain is None:
                return None
            resolved.append(chain)
        return resolved
    return None


def bindings(
    tree: ast.Module, roots: set[str]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Every name (any scope) bound to a resolvable chain or tuple-of-chains,
    in source order — later assignments may reference earlier ones
    (`_DOMAIN_DIR = _SCRIPTS_DIR`)."""
    paths: dict[str, str] = {}
    tuple_paths: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        chain = literal_chain(node.value, roots, paths)
        if chain is not None:
            paths[name] = chain
            continue
        resolved_list = literal_list(node.value, roots, paths, tuple_paths)
        if resolved_list is not None:
            tuple_paths[name] = resolved_list
    return paths, tuple_paths


def loop_target_paths(
    tree: ast.Module,
    roots: set[str],
    paths: dict[str, str],
    tuple_paths: dict[str, list[str]],
) -> dict[str, set[str]]:
    """`for target in ITER` and comprehension `for target in ITER`, wherever
    `ITER` resolves to a tuple of chains: `target` stands for each of them
    inside that loop's body."""
    targets: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.comprehension)):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        resolved_list = literal_list(node.iter, roots, paths, tuple_paths)
        if resolved_list is not None:
            targets.setdefault(node.target.id, set()).update(resolved_list)
    return targets


def resolved_rows(guard_path: Path) -> set[tuple[str, str]]:
    """Every (root, pattern) this guard's own AST literally scans via
    `.glob(pattern)`/`.rglob(pattern)`, following simple chains, aliases and
    tuple-of-chains loops. Empty when nothing resolves."""
    tree = ast.parse(guard_path.read_text(encoding="utf-8"))
    roots = root_variable_names(tree)
    paths, tuple_paths = bindings(tree, roots)
    loop_targets = loop_target_paths(tree, roots, paths, tuple_paths)

    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in GLOB_METHODS
        ):
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        pattern = node.args[0].value
        if not isinstance(pattern, str):
            continue
        receiver = node.func.value
        direct = literal_chain(receiver, roots, paths)
        if direct is not None:
            found.add((direct, pattern))
            continue
        if isinstance(receiver, ast.Name) and receiver.id in loop_targets:
            for candidate_root in loop_targets[receiver.id]:
                found.add((candidate_root, pattern))
    return found


def contains(root: str, candidate: str) -> bool:
    """`candidate` is `root` itself, or a path under it."""
    return candidate == root or candidate.startswith(f"{root}/")
