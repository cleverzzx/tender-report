# -*- coding: utf-8 -*-
"""data_manager 模块测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.data_manager import (
    _normalize_scraped_entry,
    _merge_tenders,
    _sort_by_publish_date,
)
from src.models import ScrapedEntry, Tender, TenderField


def _make_tender(title: str, company: str = "BAPEX", date_str: str = "2026-01-01") -> Tender:
    """工厂函数：创建测试用 Tender"""
    return Tender(
        title=title,
        key=f"key:{title}",
        special="test",
        fields=[
            TenderField("招标编号", f"NO-{title[:8]}"),
            TenderField("发布日期", date_str),
            TenderField("采购内容", title),
        ],
    )


def _make_scraped(title: str, url: str = "", date_text: str = "") -> ScrapedEntry:
    """工厂函数：创建测试用 ScrapedEntry"""
    return ScrapedEntry(title=title, url=url, date_text=date_text)


class TestNormalizeScrapedEntry:
    """爬取条目标准化测试"""

    def test_basic_conversion(self):
        entry = _make_scraped("BAPEX Drilling Rig Tender", "https://bapex.com.bd/t/1", "2026-04-01")
        tender = _normalize_scraped_entry(entry, "BAPEX")
        assert tender.title == "BAPEX Drilling Rig Tender"
        assert tender._source == "scraped"
        assert tender._url == "https://bapex.com.bd/t/1"
        assert len(tender.fields) >= 4

    def test_company_inference_from_title(self):
        entry = _make_scraped("SGFL Gas Compressor Procurement")
        tender = _normalize_scraped_entry(entry)
        # Company is inferred by _merge_tenders calling with company param
        # _normalize_scraped_entry doesn't auto-infer — that's done in _merge_tenders
        assert tender.title == "SGFL Gas Compressor Procurement"


class TestMergeTenders:
    """标讯合并测试"""

    def test_no_scraped_data_returns_fallback_only(self):
        fallback = {
            "BAPEX": [_make_tender("BAPEX Tender A")],
            "BGFCL": [],
            "SGFL": [],
        }
        scraped = {}
        result = _merge_tenders(fallback, scraped)
        assert len(result["BAPEX"]) == 1
        assert result["BAPEX"][0].title == "BAPEX Tender A"

    def test_scraped_with_no_duplicates_added(self):
        fallback = {
            "BAPEX": [_make_tender("BAPEX Tender A")],
            "BGFCL": [],
            "SGFL": [],
        }
        scraped = {
            "BAPEX": [_make_scraped("New BAPEX Procurement", "https://bapex.com.bd/new")],
        }
        result = _merge_tenders(fallback, scraped)
        assert len(result["BAPEX"]) == 2

    def test_duplicate_detected_by_similarity(self):
        fallback = {
            "BAPEX": [_make_tender("2000 HP AC-AC VFD Land Drilling Rig 交钥匙工程")],
            "BGFCL": [],
            "SGFL": [],
        }
        # Very similar title — should be detected as duplicate
        scraped = {
            "BAPEX": [_make_scraped("2000 HP AC-AC VFD Land Drilling Rig Turnkey Project")],
        }
        result = _merge_tenders(fallback, scraped)
        # Similarity > 0.70, so should be filtered
        assert len(result["BAPEX"]) == 1

    def test_dissimilar_title_not_deduped(self):
        fallback = {
            "BAPEX": [_make_tender("Drilling Rig Procurement")],
            "BGFCL": [],
            "SGFL": [],
        }
        scraped = {
            "BAPEX": [_make_scraped("Office Supply Purchase")],
        }
        result = _merge_tenders(fallback, scraped)
        assert len(result["BAPEX"]) == 2

    def test_short_title_filtered_out(self):
        fallback = {"BAPEX": [], "BGFCL": [], "SGFL": []}
        scraped = {
            "BAPEX": [_make_scraped("ab")],  # < 10 chars, should be filtered
        }
        result = _merge_tenders(fallback, scraped)
        assert len(result["BAPEX"]) == 0

    def test_all_three_companies_handled(self):
        """三个公司的爬取数据正确合并（使用来源名作为 key）"""
        fallback = {
            "BAPEX": [_make_tender("Drilling Rig Turnkey Project Phase 1")],
            "BGFCL": [_make_tender("Generator Engine Mechanical Spare Parts")],
            "SGFL": [_make_tender("Soft Starter and VFD Procurement")],
        }
        scraped = {
            "BAPEX": [_make_scraped("New Seismic Survey Equipment")],
            "BGFCL_portal": [_make_scraped("New Fire Tube Boiler Replacement")],
            "SGFL": [_make_scraped("New Gas Compressor Maintenance")],
        }
        result = _merge_tenders(fallback, scraped)
        assert len(result["BAPEX"]) == 2
        assert len(result["BGFCL"]) == 2
        assert len(result["SGFL"]) == 2

    def test_petrobangla_source_mapped_by_inference(self):
        """Petrobangla 来源按标题+URL 推断公司归属"""
        fallback = {"BAPEX": [], "BGFCL": [], "SGFL": []}
        scraped = {
            "Petrobangla": [
                _make_scraped("SGFL Gas Compressor Tender", "https://sgfl.gov.bd/t/1"),
                _make_scraped("BAPEX Drilling Equipment", "https://bapex.com.bd/t/2"),
                _make_scraped("BGFCL Generator Parts", "https://bgfcl.portal.gov.bd/t/3"),
            ],
        }
        result = _merge_tenders(fallback, scraped)
        assert len(result["SGFL"]) == 1
        assert len(result["BAPEX"]) == 1
        assert len(result["BGFCL"]) == 1


class TestSortByPublishDate:
    """日期排序测试"""

    def test_sort_descending(self):
        tenders = {
            "BAPEX": [
                _make_tender("Old", date_str="2025-01-01"),
                _make_tender("New", date_str="2026-01-01"),
                _make_tender("Middle", date_str="2025-06-15"),
            ],
        }
        sorted_result = _sort_by_publish_date(tenders)
        dates = [t.get_field_value("发布日期") for t in sorted_result["BAPEX"]]
        assert dates == ["2026-01-01", "2025-06-15", "2025-01-01"]

    def test_missing_date_handled(self):
        """没有日期字段的标讯应该排在最后"""
        tender_no_date = Tender(
            title="No Date Tender",
            key="key",
            special="",
            fields=[TenderField("采购内容", "test")],
        )
        tender_with_date = _make_tender("With Date", date_str="2026-01-01")
        tenders = {"BAPEX": [tender_no_date, tender_with_date]}
        sorted_result = _sort_by_publish_date(tenders)
        # 有日期的应该在前
        assert sorted_result["BAPEX"][0].title == "With Date"

    def test_all_three_companies_sorted(self):
        tenders = {
            "BAPEX": [_make_tender("B1", date_str="2026-01-01"), _make_tender("B2", date_str="2025-01-01")],
            "BGFCL": [_make_tender("G1", date_str="2026-03-01")],
            "SGFL": [_make_tender("S1", date_str="2025-12-01"), _make_tender("S2", date_str="2026-05-01")],
        }
        result = _sort_by_publish_date(tenders)
        # 每个公司内按日期降序
        assert result["BAPEX"][0].title == "B1"
        assert result["SGFL"][0].title == "S2"
        assert result["SGFL"][1].title == "S1"
