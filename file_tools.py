"""
A hard-sandboxed file capability for agents. This is the safe, scoped version of
"agents can edit files for the client": every path is resolved and checked against
a single allowed workspace folder, and writing to disk NEVER happens as a side effect
of an agent generating a proposal — it only happens via apply_file_edit(), which
web_ui.py's /publish route calls, and only after a human has both approved AND
published the task. Proposing and executing are deliberately different functions
so no code path can accidentally skip the human gate.
"""
import os

ALLOWED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_workspace")
os.makedirs(ALLOWED_DIR, exist_ok=True)


def _safe_path(relative_path: str) -> str:
    """Resolves a relative path against ALLOWED_DIR and hard-blocks any attempt to
    escape it (e.g. via '../../' traversal). Raises PermissionError rather than
    silently clamping, so a blocked attempt is loud and visible in logs."""
    target = os.path.abspath(os.path.join(ALLOWED_DIR, relative_path))
    if not (target == os.path.abspath(ALLOWED_DIR) or target.startswith(os.path.abspath(ALLOWED_DIR) + os.sep)):
        raise PermissionError(
            f"Blocked: '{relative_path}' resolves outside the permitted client_workspace folder."
        )
    return target


def read_file(relative_path: str) -> str:
    """Reads a file from the sandboxed workspace. Returns '' if it doesn't exist yet
    (treated as a new file), rather than raising, since 'create this file' is a valid
    request."""
    path = _safe_path(relative_path)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def propose_file_edit(relative_path: str, new_content: str) -> dict:
    """Builds a preview of a file change WITHOUT writing anything to disk. This is
    what an agent calls when drafting a proposal — the actual write only happens
    later, via apply_file_edit, after human approval."""
    current = read_file(relative_path)
    return {
        "path": relative_path,
        "current_content": current,
        "proposed_content": new_content,
        "is_new_file": current == "",
    }


def apply_file_edit(relative_path: str, new_content: str) -> str:
    """Actually writes to disk. Only ever call this from the publish step in
    web_ui.py, after a human has explicitly approved AND published the task —
    never directly from agent-generation code."""
    path = _safe_path(relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return path
