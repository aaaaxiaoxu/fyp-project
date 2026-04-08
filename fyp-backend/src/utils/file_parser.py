from __future__ import annotations

from pathlib import Path


def _read_text_with_fallback(file_path: str) -> str:
    data = Path(file_path).read_bytes()

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    encoding: str | None = None

    try:
        from charset_normalizer import from_bytes

        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass

    if not encoding:
        try:
            import chardet

            detected = chardet.detect(data)
            encoding = detected.get("encoding") if detected else None
        except Exception:
            pass

    return data.decode(encoding or "utf-8", errors="replace")


class FileParser:
    SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {suffix}")

        if suffix == ".pdf":
            return cls._extract_from_pdf(file_path)
        if suffix in {".md", ".markdown"}:
            return cls._extract_from_markdown(file_path)
        if suffix == ".txt":
            return cls._extract_from_text(file_path)

        raise ValueError(f"无法处理的文件格式: {suffix}")

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("需要安装 PyMuPDF 才能解析 PDF") from exc

        text_parts: list[str] = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_from_markdown(file_path: str) -> str:
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_text(file_path: str) -> str:
        return _read_text_with_fallback(file_path)

    @classmethod
    def extract_from_multiple(cls, file_paths: list[str]) -> str:
        all_texts: list[str] = []
        for index, file_path in enumerate(file_paths, start=1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 文档 {index}: {filename} ===\n{text}")
            except Exception as exc:
                all_texts.append(f"=== 文档 {index}: {file_path} (提取失败: {exc}) ===")
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            for separator in ["。", "！", "？", ".\n", "!\n", "?\n", "\n\n", ". ", "! ", "? "]:
                last_separator = text[start:end].rfind(separator)
                if last_separator != -1 and last_separator > chunk_size * 0.3:
                    end = start + last_separator + len(separator)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)

    return chunks
