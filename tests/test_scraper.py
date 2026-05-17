# -*- coding: utf-8 -*-
"""scraper 模块测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.scraper import (
    _normalize_url,
    _should_skip_ssl_verification,
    _parse_date,
    RetryableError,
    retry_on_failure,
)
from src.models import ScrapedEntry


class TestNormalizeUrl:
    """URL 规范化测试"""

    def test_absolute_url_unchanged(self):
        assert _normalize_url("https://example.com/page", "https://base.com") == "https://example.com/page"

    def test_relative_url_resolved(self):
        assert _normalize_url("/pages/tenders", "https://bapex.com.bd") == "https://bapex.com.bd/pages/tenders"

    def test_protocol_relative_url(self):
        assert _normalize_url("//cdn.example.com/file.pdf", "https://base.com") == "https://cdn.example.com/file.pdf"

    def test_empty_url(self):
        assert _normalize_url("", "https://base.com") == ""


class TestSslSkip:
    """SSL 跳过判断测试"""

    def test_known_ssl_issue_domains(self):
        assert _should_skip_ssl_verification("https://bgfcl.portal.gov.bd/pages/tenders") is True
        assert _should_skip_ssl_verification("https://sgfl.gov.bd/pages/tenders") is True

    def test_normal_domain_no_skip(self):
        assert _should_skip_ssl_verification("https://bapex.com.bd/pages/tenders") is False
        assert _should_skip_ssl_verification("https://petrobangla.org.bd/pages/tenders") is False


class TestParseDate:
    """日期解析测试"""

    def test_iso_date(self):
        result = _parse_date("2026-04-05")
        assert result is not None
        assert result.month == 4
        assert result.day == 5

    def test_us_date(self):
        result = _parse_date("04/05/2026")
        assert result is not None
        assert result.month == 4
        assert result.day == 5

    def test_text_with_date(self):
        result = _parse_date("Published on Jan 15, 2026")
        assert result is not None
        assert result.month == 1
        assert result.day == 15

    def test_invalid_text(self):
        assert _parse_date("") is None
        assert _parse_date("no date here") is None


class TestRetryDecorator:
    """重试装饰器测试"""

    def test_success_first_try(self):
        call_count = [0]

        @retry_on_failure(max_retries=3, delay=0)
        def func():
            call_count[0] += 1
            return "ok"

        assert func() == "ok"
        assert call_count[0] == 1

    def test_retry_on_retryable_error(self):
        call_count = [0]

        @retry_on_failure(max_retries=3, delay=0)
        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RetryableError("transient")
            return "ok"

        assert func() == "ok"
        assert call_count[0] == 3

    def test_max_retries_exceeded(self):
        call_count = [0]

        @retry_on_failure(max_retries=2, delay=0)
        def func():
            call_count[0] += 1
            raise RetryableError("always fail")

        with pytest.raises(RetryableError):
            func()
        assert call_count[0] == 3  # 1 original + 2 retries

    def test_non_retryable_error_not_caught(self):
        @retry_on_failure(max_retries=3, delay=0)
        def func():
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            func()


class TestScrapedEntry:
    """爬取条目模型测试"""

    def test_basic_entry(self):
        entry = ScrapedEntry(
            title="Test Tender",
            url="https://example.com/tender/1",
            date_text="2026-04-01",
            company="BAPEX",
        )
        assert entry.title == "Test Tender"
        assert entry.url == "https://example.com/tender/1"

    def test_normalize_to_tender(self):
        entry = ScrapedEntry(
            title="BAPEX Drilling Rig Tender",
            url="https://bapex.com.bd/tender/1",
            date_text="2026-04-01",
        )
        tender = entry.normalize()
        assert tender.title == "BAPEX Drilling Rig Tender"
        assert tender._source == "scraped"
        assert tender._url == "https://bapex.com.bd/tender/1"
