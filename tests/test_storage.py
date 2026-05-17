# -*- coding: utf-8 -*-
"""storage 模块测试"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from freezegun import freeze_time

from src.models import Tender, TenderField
from src.storage import HistoryManager


def _make_tender(title: str, tender_no: str = "") -> Tender:
    """工厂函数：创建测试用 Tender"""
    fields = [TenderField("采购内容", title)]
    if tender_no:
        fields.insert(0, TenderField("招标编号", tender_no))
    return Tender(
        title=title,
        key=f"key:{title}",
        special="test",
        fields=fields,
    )


class TestHistoryManager:
    """历史管理器测试"""

    @pytest.fixture
    def tmp_history(self, tmp_path):
        """创建临时历史管理器"""
        data_dir = tmp_path / "data"
        history_file = data_dir / "test_history.json"
        return HistoryManager(data_dir=data_dir, history_file=history_file)

    def test_load_empty_history(self, tmp_history):
        history = tmp_history.load_history()
        assert history["version"] == 1
        assert history["tenders"] == {}

    def test_save_and_load_history(self, tmp_history):
        history = {"version": 1, "last_run": None, "tenders": {}}
        tmp_history.save_history(history)
        loaded = tmp_history.load_history()
        assert loaded["last_run"] is not None
        assert "version" in loaded

    def test_ensure_data_dir_created(self, tmp_history):
        tmp_history._ensure_data_dir()
        assert tmp_history.data_dir.exists()

    def test_generate_tender_hash_consistent(self, tmp_history):
        tender = _make_tender("Test Tender", "NO-001")
        h1 = tmp_history._generate_tender_hash(tender)
        h2 = tmp_history._generate_tender_hash(tender)
        assert h1 == h2
        assert len(h1) == 12

    def test_generate_tender_hash_different_for_different_titles(self, tmp_history):
        t1 = _make_tender("Tender A")
        t2 = _make_tender("Tender B")
        assert tmp_history._generate_tender_hash(t1) != tmp_history._generate_tender_hash(t2)

    @freeze_time("2026-05-17")
    def test_detect_new_tenders_first_run(self, tmp_history):
        """首次运行，所有标讯都是新的"""
        tenders = {
            "BAPEX": [_make_tender("BAPEX Tender A", "NO-001")],
            "BGFCL": [_make_tender("BGFCL Tender A", "NO-002")],
            "SGFL": [_make_tender("SGFL Tender A", "NO-003")],
        }
        merged, new_count, stats = tmp_history.detect_new_tenders(tenders)

        assert new_count == 3
        assert stats.total == 3
        assert stats.new == 3
        for company in ["BAPEX", "BGFCL", "SGFL"]:
            assert stats.by_company[company]["new"] == 1
        # 所有标讯应标记为新
        for company_tenders in merged.values():
            for t in company_tenders:
                assert t._is_new is True

    @freeze_time("2026-05-17")
    def test_detect_no_new_tenders_second_run(self, tmp_history):
        """第二次运行，没有新标讯"""
        tenders = {
            "BAPEX": [_make_tender("Tender A", "NO-001")],
        }
        # 第一次运行
        tmp_history.detect_new_tenders(tenders)
        # 第二次运行
        merged, new_count, stats = tmp_history.detect_new_tenders(tenders)

        assert new_count == 0
        assert stats.new == 0
        assert merged["BAPEX"][0]._is_new is False

    @freeze_time("2026-05-17")
    def test_detect_partial_new_tenders(self, tmp_history):
        """部分标讯是新的"""
        # 第一次：只有 A
        tmp_history.detect_new_tenders({
            "BAPEX": [_make_tender("Tender A", "NO-001")],
        })
        # 第二次：A + 新增 B
        merged, new_count, stats = tmp_history.detect_new_tenders({
            "BAPEX": [
                _make_tender("Tender A", "NO-001"),
                _make_tender("Tender B", "NO-002"),
            ],
        })

        assert new_count == 1
        assert merged["BAPEX"][0]._is_new is False  # Tender A
        assert merged["BAPEX"][1]._is_new is True   # Tender B

    def test_get_last_run_time(self, tmp_history):
        assert tmp_history.get_last_run_time() is None
        tmp_history.save_history({"version": 1, "last_run": None, "tenders": {}})
        last = tmp_history.get_last_run_time()
        assert last is not None
        assert isinstance(last, datetime)

    def test_clear_history(self, tmp_history):
        tmp_history.save_history({"version": 1, "last_run": None, "tenders": {}})
        assert tmp_history.history_file.exists()
        tmp_history.clear_history()
        assert not tmp_history.history_file.exists()

    def test_corrupted_history_file(self, tmp_history):
        """损坏的历史文件应被优雅处理"""
        tmp_history._ensure_data_dir()
        tmp_history.history_file.write_text("not valid json {{{")
        history = tmp_history.load_history()
        assert history["version"] == 1
        assert history["tenders"] == {}


class TestModuleLevelApi:
    """模块级 API 兼容性测试"""

    def test_detect_new_tenders_exists(self):
        from src.storage import detect_new_tenders
        assert callable(detect_new_tenders)

    def test_get_last_run_time_exists(self):
        from src.storage import get_last_run_time
        assert callable(get_last_run_time)

    def test_clear_history_exists(self):
        from src.storage import clear_history
        assert callable(clear_history)
