import os
import ast
import shutil
import re
import textwrap

PROJECTS_DIR = "projects"
DOCS_DIR = "documents"

TARGET_PROJECTS = {
    "wbc-analyzer": "WBC Analyzer",
    "kinematic": "Kinematic Action Recognition",
    "listing-pilot": "Listing Pilot",
    "popcorn-wagon": "Popcorn Wagon",
    "portal-cleaner-ultimate": "Portal Cleaner Ultimate"
}

_SKIP_DIRS = {"venv", ".git", "__pycache__", ".venv", "node_modules", "dist", "build"}


def _get_source_lines(source: str) -> list[str]:
    return source.splitlines()


def _inline_comments(source: str) -> list[str]:
    comments = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text:
                comments.append(text)
    return comments


def _arg_str(args: ast.arguments) -> str:
    """Reconstruct a readable argument list from an ast.arguments node."""
    parts = []
    posonlyargs = getattr(args, 'posonlyargs', [])
    all_args = list(posonlyargs) + list(args.args)
    defaults_offset = len(all_args) - len(args.defaults)

    for i, arg in enumerate(all_args):
        part = arg.arg
        if arg.annotation:
            part += f": {ast.unparse(arg.annotation)}"
        default_idx = i - defaults_offset
        if default_idx >= 0:
            part += f" = {ast.unparse(args.defaults[default_idx])}"
        parts.append(part)

    if args.vararg:
        v = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            v += f": {ast.unparse(args.vararg.annotation)}"
        parts.append(v)
    elif args.kwonlyargs:
        parts.append("*")

    for i, arg in enumerate(args.kwonlyargs):
        part = arg.arg
        if arg.annotation:
            part += f": {ast.unparse(arg.annotation)}"
        if args.kw_defaults[i] is not None:
            part += f" = {ast.unparse(args.kw_defaults[i])}"
        parts.append(part)

    if args.kwarg:
        k = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            k += f": {ast.unparse(args.kwarg.annotation)}"
        parts.append(k)

    return ", ".join(parts)


def _return_str(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if node.returns:
        return f" -> {ast.unparse(node.returns)}"
    return ""


def extract_rich_context(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except Exception as e:
        return f"[read error: {e}]"

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fall back to comment-only extraction for unparseable files
        comments = _inline_comments(source)
        return "--- Inline Comments ---\n" + "\n".join(comments) if comments else ""

    sections: list[str] = []

    # Module docstring
    module_doc = ast.get_docstring(tree)
    if module_doc:
        sections.append(f"--- Module Docstring ---\n{module_doc.strip()}")

    # Module-level constants (ALL_CAPS assignments)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    try:
                        val = ast.unparse(node.value)
                        sections.append(f"CONSTANT: {target.id} = {val}")
                    except Exception:
                        pass
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id.isupper():
                try:
                    val = ast.unparse(node.value) if node.value else "..."
                    ann = ast.unparse(node.annotation)
                    sections.append(f"CONSTANT: {node.target.id}: {ann} = {val}")
                except Exception:
                    pass

    # Classes and their methods
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
            class_header = f"class {node.name}" + (f"({bases})" if bases else "") + ":"
            class_section = [f"--- Class: {class_header} ---"]
            if class_doc:
                class_section.append(f"  \"\"\"{class_doc.strip()}\"\"\"")

            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                    sig = f"  {prefix} {item.name}({_arg_str(item.args)}){_return_str(item)}"
                    fn_doc = ast.get_docstring(item)
                    if fn_doc:
                        class_section.append(f"{sig}:\n    \"\"\"{fn_doc.strip()}\"\"\"")
                    else:
                        class_section.append(sig)

            sections.append("\n".join(class_section))

    # Module-level functions (not inside a class)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            sig = f"{prefix} {node.name}({_arg_str(node.args)}){_return_str(node)}"
            fn_doc = ast.get_docstring(node)
            if fn_doc:
                sections.append(f"--- Function: {sig} ---\n\"\"\"{fn_doc.strip()}\"\"\"")
            else:
                sections.append(f"--- Function: {sig} ---")

    # Inline comments (still useful for inline logic notes)
    comments = _inline_comments(source)
    if comments:
        sections.append("--- Inline Comments ---\n" + "\n".join(comments))

    return "\n\n".join(sections)


def main():
    if os.path.exists(DOCS_DIR):
        try:
            shutil.rmtree(DOCS_DIR)
        except Exception as e:
            print(f"Could not clear documents directory: {e}")
    os.makedirs(DOCS_DIR, exist_ok=True)

    for folder_name, project_title in TARGET_PROJECTS.items():
        project_path = os.path.join(PROJECTS_DIR, folder_name)
        if not os.path.isdir(project_path):
            print(f"Directory {project_path} not found. Skipping...")
            continue

        print(f"Processing project: {project_title}...")

        readme_path = os.path.join(project_path, "README.md")
        if os.path.exists(readme_path):
            target_readme = os.path.join(DOCS_DIR, f"{folder_name}_README.md")
            shutil.copy2(readme_path, target_readme)
            print(f"  Copied README to {target_readme}")
        else:
            print(f"  Warning: README.md not found in {project_path}")

        project_sections: list[str] = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, project_path)
                extracted = extract_rich_context(full_path)
                if extracted.strip():
                    project_sections.append(f"=== File: {rel_path} ===\n{extracted}\n")

        if project_sections:
            out_path = os.path.join(DOCS_DIR, f"{folder_name}_code_context.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# Code Context: {project_title}\n\n")
                f.write("\n".join(project_sections))
            print(f"  Extracted code context to {out_path}")


if __name__ == "__main__":
    main()
