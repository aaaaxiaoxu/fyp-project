from __future__ import annotations

import re

from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """Text extraction and preprocessing helpers migrated from MiroFish."""

    @staticmethod
    def extract_from_files(file_paths: list[str]) -> str:
        return FileParser.extract_from_multiple(file_paths)

    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[str]:
        return split_text_into_chunks(text, chunk_size, overlap)

    @staticmethod
    def preprocess_text(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        lines = [line.strip() for line in normalized.split("\n")]
        return "\n".join(lines).strip()

    @staticmethod
    def get_text_stats(text: str) -> dict[str, int]:
        return {
            "total_chars": len(text),
            "total_lines": text.count("\n") + 1 if text else 0,
            "total_words": len(text.split()),
        }
