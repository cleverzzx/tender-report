# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

孟加拉石油公司国际招标标讯追踪工具 (Bangladesh Petroleum Tender Tracker) — A Python tool that scrapes international tender notices from Bangladesh petroleum companies (BAPEX, BGFCL, SGFL) and generates standardized PDF reports.

## Common Commands

### Setup
```bash
pip install -r requirements.txt
```

### Generate Report
```bash
# Default: generate PDF + send email (if configured)
python generate_tender_report.py

# Skip email delivery
python generate_tender_report.py --no-email

# Validate all links before generating
python generate_tender_report.py --validate

# Specify custom output
python generate_tender_report.py --output-dir ./reports --output custom.pdf

# Only validate links (no report generation)
python generate_tender_report.py --validate-only

# Quick run via shell script
bash run.sh
```

### Virtual Environment
The project uses a virtual environment at `.venv/` or `venv/`. Activate before running:
```bash
source venv/bin/activate  # or .venv/bin/activate
```

## Architecture

### Module Structure

```
generate_tender_report.py  # Main entry point - CLI, PDF generation, email
generate_tender_report.py::generate_pdf()  # Primary API for programmatic use
├── config.py              # Configuration, fallback data, URLs database
├── scraper.py             # Web scraping and link validation
└── requirements.txt       # reportlab, requests, beautifulsoup4, lxml
```

### Key Components

**PDF Generation** (`generate_tender_report.py`)
- Uses ReportLab for PDF generation with A4 page size
- Chinese font registration via `register_chinese_fonts()` — searches common system paths (PingFang, STHeiti, wqy-microhei, NotoSansCJK)
- Font fallback to Helvetica if no Chinese font found
- Styles defined in `create_styles()` with configurable sizes via `CONFIG["font_size"]`

**Data Flow**
1. `get_tender_data()` in main module calls `get_fallback_tenders()` from config
2. Data sorted by publish date descending (newest first) via `_get_publish_date()`
3. `generate_pdf()` renders sections: Summary → BAPEX → BGFCL → SGFL → Industry News

**Web Scraping** (`scraper.py`)
- `scrape_all_listings()` — Scrapes tender list pages from multiple sources
- `validate_all_links()` — Validates URLs in `OFFICIAL_URLS` with SSL downgrade handling
- Three scraping strategies: table rows, link lists, card blocks
- SSL certificate issues common with government sites — handled via `verify=False` retry

**Configuration** (`config.py`)
- `OFFICIAL_URLS` — Database of official tender detail pages and PDF download links
- `LISTING_URLS` — URLs for scraping tender listings
- `get_fallback_tenders()` — Hardcoded tender data used when scraping fails
- `CONFIG` dict loaded from environment variables for email and output settings

### Email Configuration
Set environment variables to enable email delivery:
```bash
export EMAIL_SMTP_SERVER=smtp.qq.com
export EMAIL_SMTP_PORT=587
export EMAIL_SENDER=your@email.com
export EMAIL_PASSWORD=your_auth_code
export EMAIL_RECIPIENT=recipient@email.com
```

### Output
PDFs are written to `reports/` directory by default (configurable via `TENDER_OUTPUT_DIR` env var or `--output-dir`). Default filename: `孟加拉标讯报告_YYYYMMDD_HHMMSS.pdf`

### Font Handling
The tool requires Chinese fonts for PDF generation. On macOS it auto-detects PingFang or STHeiti. On Linux, install: `apt install fonts-wqy-microhei` or `fonts-noto-cjk`.

### Testing Link Validation
To quickly check if all official tender links are accessible without generating a report:
```bash
python generate_tender_report.py --validate-only
```
