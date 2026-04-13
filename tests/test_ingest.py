"""
tests/test_ingest.py — ingestion 模块测试

测试文本分块逻辑和文件收集逻辑（不需要 LLM 和文件系统，纯逻辑测试）。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pipeline.ingest import (
    split_text_into_chunks,
    collect_files,
    infer_source_type,
    MAX_CHUNK_CHARS,
    MIN_PARAGRAPH_CHARS,
)


class TestSplitTextIntoChunks:
    def test_short_text_no_split(self):
        text = "这是一段短文本。" * 10
        chunks = split_text_into_chunks(text, max_chars=5000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_exact_limit_no_split(self):
        text = "a" * MAX_CHUNK_CHARS
        chunks = split_text_into_chunks(text, max_chars=MAX_CHUNK_CHARS)
        assert len(chunks) == 1

    def test_long_text_splits_into_multiple(self):
        # 生成超过限制的文本：多个段落
        paragraph = "这是一个段落，包含一些市场相关信息，央行降息，北向资金流入。" * 5
        text = "\n\n".join([paragraph] * 20)  # 20 个段落
        chunks = split_text_into_chunks(text, max_chars=500)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 500 + 100  # 允许小幅超限（句子粒度）

    def test_chunks_cover_all_content(self):
        """所有文本内容都应出现在某个 chunk 中"""
        paragraphs = [f"这是第{i}段内容，包含重要市场信号。" for i in range(1, 21)]
        text = "\n\n".join(paragraphs)
        chunks = split_text_into_chunks(text, max_chars=200)

        # 合并所有 chunks 后应包含所有段落的关键词
        combined = " ".join(chunks)
        for i in range(1, 21):
            assert f"第{i}段" in combined

    def test_single_huge_paragraph_split_by_sentence(self):
        """单个超长段落（无换行）应按句子分割"""
        # 构造一个超长段落，每句以句号结尾
        sentences = [f"央行公告第{i}条内容如下，具体实施细节待定。" for i in range(1, 30)]
        text = "".join(sentences)  # 无段落分隔
        assert len(text) > MAX_CHUNK_CHARS

        chunks = split_text_into_chunks(text, max_chars=200)
        assert len(chunks) > 1
        # 每个 chunk 应该在 200+50 个字符内（句子粒度有浮动）
        for chunk in chunks:
            assert len(chunk) < 400

    def test_empty_text(self):
        chunks = split_text_into_chunks("", max_chars=1000)
        assert chunks == [] or chunks == [""]

    def test_short_paragraphs_merged(self):
        """短段落应被合并到同一个 chunk"""
        # 每个段落很短，应该被合并
        paragraphs = ["短段落。"] * 10
        text = "\n\n".join(paragraphs)
        chunks = split_text_into_chunks(text, max_chars=500)
        # 10 个"短段落。"总共约 80 字符，应该在一个 chunk 内
        assert len(chunks) == 1

    def test_mixed_length_paragraphs(self):
        """长短混合段落的分块结果合理"""
        short_paras = ["短。"] * 5
        long_para = "很长的段落内容。" * 50  # ~400 字符
        text = "\n\n".join(short_paras + [long_para] + short_paras)
        chunks = split_text_into_chunks(text, max_chars=300)
        assert len(chunks) >= 2

    def test_chunk_with_custom_max_chars(self):
        text = "内容。" * 100  # 300 字符
        chunks_small = split_text_into_chunks(text, max_chars=50)
        chunks_large = split_text_into_chunks(text, max_chars=1000)
        assert len(chunks_small) >= len(chunks_large)


class TestCollectFiles:
    def test_collect_txt_files(self, tmp_path):
        (tmp_path / "sample_001.txt").write_text("news content 1", encoding="utf-8")
        (tmp_path / "sample_002.txt").write_text("news content 2", encoding="utf-8")
        (tmp_path / "report_001.md").write_text("report content", encoding="utf-8")
        (tmp_path / "ignore.csv").write_text("csv data", encoding="utf-8")  # 不支持

        files = collect_files(tmp_path)
        names = {f.name for f in files}
        assert "sample_001.txt" in names
        assert "sample_002.txt" in names
        assert "report_001.md" in names
        assert "ignore.csv" not in names  # CSV 不被收集

    def test_collect_recursive(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.txt").write_text("root", encoding="utf-8")
        (subdir / "sub.txt").write_text("sub", encoding="utf-8")

        files_flat = collect_files(tmp_path, recursive=False)
        files_recursive = collect_files(tmp_path, recursive=True)

        assert len(files_flat) == 1
        assert len(files_recursive) == 2

    def test_empty_directory(self, tmp_path):
        files = collect_files(tmp_path)
        assert files == []

    def test_files_sorted(self, tmp_path):
        for name in ["c.txt", "a.txt", "b.txt"]:
            (tmp_path / name).write_text("content", encoding="utf-8")
        files = collect_files(tmp_path)
        names = [f.name for f in files]
        assert names == sorted(names)


class TestInferSourceType:
    def test_report_prefix(self):
        assert infer_source_type(Path("report_q1_2024.txt")) == "report"

    def test_announcement_suffix(self):
        assert infer_source_type(Path("company_announcement_001.txt")) == "announcement"

    def test_default_is_news(self):
        assert infer_source_type(Path("some_random_file.txt")) == "news"

    def test_data_keyword(self):
        assert infer_source_type(Path("data_macro_march.txt")) == "data"

    def test_custom_default(self):
        result = infer_source_type(Path("unknown.txt"), default="report")
        assert result == "report"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
