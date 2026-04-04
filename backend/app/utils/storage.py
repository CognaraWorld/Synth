"""Safe storage path helpers for uploaded files."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4


_FILENAME_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving the extension."""
    raw_name = Path(filename or "").name.strip()
    if not raw_name:
        raise ValueError("Filename is required.")

    suffix = Path(raw_name).suffix.lower()
    stem = Path(raw_name).stem
    safe_stem = _FILENAME_SANITIZER.sub("_", stem).strip("._")
    if not safe_stem:
        safe_stem = "document"

    safe_suffix = _FILENAME_SANITIZER.sub("", suffix)
    return f"{safe_stem}{safe_suffix}"


def ensure_path_within_root(root: Path, candidate: Path) -> Path:
    """Resolve *candidate* and ensure it stays within *root*."""
    resolved_root = root.expanduser().resolve()
    resolved_candidate = candidate.expanduser().resolve()
    resolved_candidate.relative_to(resolved_root)
    return resolved_candidate


def build_agent_upload_path(upload_root: Path, agent_id: str, filename: str) -> tuple[str, Path]:
    """Create a safe upload path for an agent-owned file."""
    safe_filename = sanitize_filename(filename)
    # Strip both POSIX and Windows path separators for cross-platform safety
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    display_name = basename or safe_filename

    root = upload_root.expanduser().resolve()
    agent_dir = ensure_path_within_root(root, root / agent_id)
    agent_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}_{safe_filename}"
    file_path = ensure_path_within_root(root, agent_dir / stored_name)

    return display_name, file_path


def is_managed_path(upload_root: Path, file_path: str | Path) -> bool:
    """Return True when *file_path* lives under *upload_root*."""
    try:
        ensure_path_within_root(upload_root, Path(file_path))
    except ValueError:
        return False
    return True
