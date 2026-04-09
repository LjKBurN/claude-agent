#!/usr/bin/env python3
"""代码复杂度分析脚本。"""

import argparse
import json
from pathlib import Path


def analyze_file(file_path: Path) -> dict:
    """分析单个文件的复杂度。"""
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    return {
        "file": str(file_path),
        "total_lines": len(lines),
        "code_lines": sum(1 for line in lines if line.strip() and not line.strip().startswith("#")),
        "blank_lines": sum(1 for line in lines if not line.strip()),
        "comment_lines": sum(1 for line in lines if line.strip().startswith("#")),
    }


def analyze_directory(directory: Path) -> list[dict]:
    """分析目录下所有 Python 文件。"""
    results = []
    for py_file in directory.rglob("*.py"):
        results.append(analyze_file(py_file))
    return results


def main():
    parser = argparse.ArgumentParser(description="Analyze code complexity")
    parser.add_argument("path", help="Directory or file to analyze")
    parser.add_argument("--output", "-o", default="json", choices=["json", "text"])
    args = parser.parse_args()

    path = Path(args.path)
    if path.is_file():
        results = [analyze_file(path)]
    else:
        results = analyze_directory(path)

    if args.output == "json":
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['file']}: {r['code_lines']} code lines")


if __name__ == "__main__":
    main()
