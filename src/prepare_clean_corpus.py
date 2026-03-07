#!/usr/bin/env python3
"""
将原始文档目录清洗为标准化文本语料，保留目录结构。
"""
import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from document_cleaner_enhanced import EnhancedDocumentCleaner


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".htm"}


@dataclass
class FileReport:
    source: str
    output: str
    source_size: int
    cleaned_size: int
    paragraph_count: int
    status: str
    reason: str = ""


def normalize_block(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def dedup_paragraphs(text: str) -> str:
    blocks = re.split(r"\n{2,}", text)
    seen = set()
    kept = []
    for block in blocks:
        normalized = normalize_block(block)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        kept.append(block.strip())
    return "\n\n".join(kept)


def collect_files(input_dir: Path) -> List[Path]:
    files = []
    for path in input_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    files.sort(key=lambda p: str(p.resolve()))
    return files


def main():
    parser = argparse.ArgumentParser(description="清洗文档并输出标准化语料")
    parser.add_argument("--input", required=True, help="原始文档目录，例如 documents/")
    parser.add_argument("--output", required=True, help="清洗后输出目录，例如 data/clean_documents/")
    parser.add_argument("--report", required=True, help="清洗报告 JSON 输出路径")
    parser.add_argument("--min-chars", type=int, default=200, help="清洗后最小字符数")
    parser.add_argument("--max-chars-per-file", type=int, default=300000, help="单文件最多保留字符数")
    parser.add_argument("--max-files", type=int, default=0, help="最多处理文件数（0 表示不限制）")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"invalid input directory: {input_dir}")

    output_dir = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaner = EnhancedDocumentCleaner({"remove_patterns": [], "min_line_length": 10})
    files = collect_files(input_dir)
    if args.max_files > 0:
        files = files[: args.max_files]

    reports: List[FileReport] = []
    kept_count = 0

    for source_path in files:
        rel = source_path.relative_to(input_dir)
        output_path = (output_dir / rel).with_suffix(".txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            raw = cleaner.load_file_with_encoding(str(source_path))
            cleaned = cleaner.clean_text(raw, source_path.suffix.lower().lstrip("."))
            cleaned = dedup_paragraphs(cleaned)

            if len(cleaned) > args.max_chars_per_file:
                cleaned = cleaned[: args.max_chars_per_file]

            paragraph_count = len([b for b in re.split(r"\n{2,}", cleaned) if b.strip()])
            if len(cleaned) < args.min_chars:
                reports.append(
                    FileReport(
                        source=str(source_path),
                        output=str(output_path),
                        source_size=len(raw),
                        cleaned_size=len(cleaned),
                        paragraph_count=paragraph_count,
                        status="skipped",
                        reason=f"cleaned text too short (< {args.min_chars})",
                    )
                )
                continue

            output_path.write_text(cleaned, encoding="utf-8")
            kept_count += 1
            reports.append(
                FileReport(
                    source=str(source_path),
                    output=str(output_path),
                    source_size=len(raw),
                    cleaned_size=len(cleaned),
                    paragraph_count=paragraph_count,
                    status="kept",
                )
            )
        except Exception as e:
            reports.append(
                FileReport(
                    source=str(source_path),
                    output=str(output_path),
                    source_size=0,
                    cleaned_size=0,
                    paragraph_count=0,
                    status="failed",
                    reason=str(e),
                )
            )

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_files": len(files),
        "kept_files": kept_count,
        "skipped_or_failed_files": len(files) - kept_count,
        "files": [asdict(r) for r in reports],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 清洗完成: kept={kept_count}/{len(files)}")
    print(f"📄 报告路径: {report_path}")


if __name__ == "__main__":
    main()
