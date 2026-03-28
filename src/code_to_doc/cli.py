from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

from pathspec import PathSpec


SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".lua",
    ".m",
    ".php",
    ".pl",
    ".py",
    ".r",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "out",
    "__pycache__",
}

SKIP_SUFFIXES = {
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".jar",
    ".lock",
    ".log",
    ".min.js",
    ".o",
    ".obj",
    ".pyc",
    ".pyd",
    ".pyo",
    ".so",
    ".tmp",
}

SKIP_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}


def guess_language(path: Path) -> str:
    mapping = {
        ".c": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".css": "css",
        ".go": "go",
        ".h": "c",
        ".hpp": "cpp",
        ".html": "html",
        ".java": "java",
        ".js": "javascript",
        ".json": "json",
        ".jsx": "jsx",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".lua": "lua",
        ".m": "objectivec",
        ".md": "markdown",
        ".php": "php",
        ".pl": "perl",
        ".py": "python",
        ".r": "r",
        ".rb": "ruby",
        ".rs": "rust",
        ".scala": "scala",
        ".sh": "bash",
        ".sql": "sql",
        ".swift": "swift",
        ".toml": "toml",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".txt": "text",
        ".vue": "vue",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    return mapping.get(path.suffix.lower(), "text")


def is_binary_file(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return True

    if not data:
        return False

    if b"\x00" in data:
        return True

    sample = data[:4096]
    non_text = sum(byte < 9 or (13 < byte < 32) for byte in sample)
    return (non_text / len(sample)) > 0.30


def should_skip(path: Path) -> bool:
    name = path.name
    lowered = name.lower()

    if name in SKIP_FILE_NAMES:
        return True

    if lowered.endswith("~"):
        return True

    for suffix in SKIP_SUFFIXES:
        if lowered.endswith(suffix):
            return True

    return False


def parse_extensions(values: list[str] | None) -> set[str]:
    if not values:
        return set()

    result: set[str] = set()
    for value in values:
        for token in value.split(","):
            token = token.strip().lower()
            if not token:
                continue
            if not token.startswith("."):
                token = f".{token}"
            result.add(token)
    return result


def parse_size_to_bytes(value: str | None) -> int | None:
    if value is None:
        return None

    token = value.strip().lower().replace(" ", "")
    units = {
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
    }

    for unit in ("gb", "mb", "kb", "g", "m", "k", "b"):
        if token.endswith(unit):
            number = token[: -len(unit)]
            if not number:
                raise ValueError(f"invalid size value: {value}")
            return int(float(number) * units[unit])

    return int(token)


def is_ignored(ignore_spec: PathSpec | None, rel_path: str, is_dir: bool = False) -> bool:
    if ignore_spec is None:
        return False

    if ignore_spec.match_file(rel_path):
        return True

    return is_dir and ignore_spec.match_file(f"{rel_path}/")


def load_ignore_spec(source_dir: Path, ignore_file_arg: Path | None) -> PathSpec | None:
    ignore_file: Path | None
    if ignore_file_arg is None:
        candidate = source_dir / ".gitignore"
        ignore_file = candidate if candidate.exists() else None
    else:
        ignore_file = ignore_file_arg if ignore_file_arg.is_absolute() else source_dir / ignore_file_arg
        if not ignore_file.exists() or not ignore_file.is_file():
            raise FileNotFoundError(f"ignore file does not exist: {ignore_file}")

    if ignore_file is None:
        return None

    lines = ignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
    patterns = [line for line in lines if line.strip() and not line.strip().startswith("#")]
    if not patterns:
        return None

    return PathSpec.from_lines("gitwildmatch", patterns)


def collect_source_files(
    root: Path,
    included_exts: set[str],
    excluded_exts: set[str],
    excluded_paths: set[Path] | None = None,
    ignore_spec: PathSpec | None = None,
    max_file_size: int | None = None,
    follow_symlinks: bool = False,
) -> tuple[list[Path], Counter[str]]:
    excluded_paths = excluded_paths or set()
    files: list[Path] = []
    stats: Counter[str] = Counter()
    visited_real_dirs: set[Path] = set()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=follow_symlinks):
        current_dir = Path(dirpath)

        if follow_symlinks:
            try:
                real_dir = current_dir.resolve()
            except OSError:
                dirnames[:] = []
                continue

            if real_dir in visited_real_dirs:
                dirnames[:] = []
                continue
            visited_real_dirs.add(real_dir)

        kept_dirs: list[str] = []
        for dirname in sorted(dirnames, key=str.lower):
            if dirname in SKIP_DIRS:
                continue

            candidate = current_dir / dirname
            rel_dir = candidate.relative_to(root).as_posix()
            if is_ignored(ignore_spec, rel_dir, is_dir=True):
                continue

            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames, key=str.lower):
            path = current_dir / filename
            stats["files_scanned"] += 1

            if path in excluded_paths:
                stats["skipped_output_file"] += 1
                continue

            rel = path.relative_to(root).as_posix()
            if is_ignored(ignore_spec, rel):
                stats["skipped_by_ignore_rule"] += 1
                continue

            if should_skip(path):
                stats["skipped_temp_or_artifact"] += 1
                continue

            suffix = path.suffix.lower()
            if suffix not in included_exts:
                stats["skipped_non_source_extension"] += 1
                continue

            if suffix in excluded_exts:
                stats["skipped_by_excluded_extension"] += 1
                continue

            if max_file_size is not None:
                try:
                    size = path.stat().st_size
                except OSError:
                    stats["skipped_unreadable"] += 1
                    continue
                if size > max_file_size:
                    stats["skipped_too_large"] += 1
                    continue

            if is_binary_file(path):
                stats["skipped_binary"] += 1
                continue

            files.append(path)
            stats["exported"] += 1

    files.sort(key=lambda p: str(p).lower())
    return files, stats


def print_stats(stats: Counter[str], output_file: Path) -> None:
    print(f"Output: {output_file}")
    print(f"Scanned files: {stats.get('files_scanned', 0)}")
    print(f"Exported source files: {stats.get('exported', 0)}")
    print(f"Exported source lines: {stats.get('exported_lines', 0)}")

    skipped_total = stats.get("files_scanned", 0) - stats.get("exported", 0)
    print(f"Skipped files: {skipped_total}")

    ordered_reasons = [
        "skipped_output_file",
        "skipped_by_ignore_rule",
        "skipped_temp_or_artifact",
        "skipped_non_source_extension",
        "skipped_by_excluded_extension",
        "skipped_too_large",
        "skipped_binary",
        "skipped_unreadable",
    ]
    for reason in ordered_reasons:
        count = stats.get(reason, 0)
        if count:
            print(f"  - {reason}: {count}")


def count_exported_lines(content: str) -> int:
    return len(content.splitlines())


def render_markdown(root: Path, files: list[Path]) -> tuple[str, int]:
    blocks: list[str] = []
    exported_lines = 0

    for file_path in files:
        rel = file_path.relative_to(root).as_posix()
        lang = guess_language(file_path)
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8", errors="replace")

        exported_lines += count_exported_lines(content)

        if content and not content.endswith("\n"):
            content += "\n"

        block = f"<{rel}>\n```{lang}\n{content}```"
        blocks.append(block)

    markdown = "\n\n".join(blocks) + ("\n" if blocks else "")
    return markdown, exported_lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export all source files in a directory tree into one markdown file."
    )
    parser.add_argument("source_dir", type=Path, help="Directory to scan")
    parser.add_argument("output_file", type=Path, help="Markdown output file path")
    parser.add_argument(
        "--include-ext",
        action="append",
        default=None,
        metavar="EXT",
        help="Extensions to include, repeatable or comma-separated (example: --include-ext .py,.ts)",
    )
    parser.add_argument(
        "--exclude-ext",
        action="append",
        default=None,
        metavar="EXT",
        help="Extensions to exclude, repeatable or comma-separated (example: --exclude-ext .json)",
    )
    parser.add_argument(
        "--ignore-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Ignore rules file in gitignore syntax. Defaults to source_dir/.gitignore if present.",
    )
    parser.add_argument(
        "--max-file-size",
        default=None,
        metavar="SIZE",
        help="Maximum file size to export, e.g. 200KB, 2MB, 1048576.",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symbolic links while walking directories.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output_file = args.output_file.resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        parser.error(f"source_dir is not a valid directory: {source_dir}")

    included_exts = parse_extensions(args.include_ext)
    if not included_exts:
        included_exts = set(SOURCE_EXTENSIONS)

    excluded_exts = parse_extensions(args.exclude_ext)

    try:
        ignore_spec = load_ignore_spec(source_dir, args.ignore_file)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    try:
        max_file_size = parse_size_to_bytes(args.max_file_size)
    except ValueError as exc:
        parser.error(str(exc))

    excluded = {output_file} if output_file.is_relative_to(source_dir) else set()
    files, stats = collect_source_files(
        source_dir,
        included_exts=included_exts,
        excluded_exts=excluded_exts,
        excluded_paths=excluded,
        ignore_spec=ignore_spec,
        max_file_size=max_file_size,
        follow_symlinks=args.follow_symlinks,
    )
    markdown, exported_lines = render_markdown(source_dir, files)
    stats["exported_lines"] = exported_lines

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8")

    print_stats(stats, output_file)


if __name__ == "__main__":
    main()
