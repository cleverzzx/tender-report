# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

孟加拉石油公司国际招标标讯追踪工具 (Bangladesh Petroleum Tender Tracker) v3.1 — A Python tool that scrapes international tender notices from Bangladesh petroleum companies (BAPEX, BGFCL, SGFL) and generates standardized PDF reports.

## Common Commands

### Setup
```bash
pip install -r requirements.txt
```

### Generate Report
```bash
# Default: generate PDF + send email (if configured)
python main.py

# Skip email delivery
python main.py --no-email

# Validate all links before generating
python main.py --validate

# Scrape latest tenders from websites
python main.py --scrape

# Specify custom output
python main.py --output-dir ./reports --output custom.pdf

# Only validate links (no report generation)
python main.py --validate-only

# Quick run via shell script
bash run.sh
```

### Code Quality
```bash
# Type checking
mypy src/ config.py main.py

# Linting
flake8 src/ config.py main.py

# Formatting
black src/ config.py main.py

# Tests
pytest
```

### Virtual Environment
The project uses a virtual environment at `.venv/`. Activate before running:
```bash
source .venv/bin/activate
```

## Architecture

### Module Structure (v3.1)

```
main.py                    # Main entry point - CLI orchestration
├── config.py              # Configuration, fallback data, URLs database
└── src/                   # Source package
    ├── models.py          # Data models (Tender, ScrapedEntry, etc.)
    ├── cli.py             # Command-line argument parsing
    ├── pdf_generator.py   # PDF report generation
    ├── email_sender.py    # Email delivery
    ├── scraper.py         # Web scraping and link validation
    ├── data_manager.py    # Data merging and sorting
    ├── storage.py         # History persistence and new tender detection
    └── utils.py           # Common utilities (font registration, logging)
```

### Key Components

**PDF Generation** (`src/pdf_generator.py`)
- Uses ReportLab for PDF generation with A4 page size
- Chinese font registration via `register_chinese_fonts()` in utils.py
- Font fallback to Helvetica if no Chinese font found
- Styles defined in `PDFGenerator._create_styles()` with configurable sizes

**Data Flow**
1. `main.py` parses CLI arguments via `src/cli.py`
2. `get_tender_data()` in `src/data_manager.py` calls `get_fallback_tenders()` from config
3. If `--scrape` flag is set, also scrapes latest tenders via `scrape_all_listings()`
4. Data merged and deduplicated, then sorted by publish date descending
5. `detect_new_tenders()` in `src/storage.py` marks new tenders and updates history
6. `PDFGenerator.generate()` renders sections: Summary → BAPEX → BGFCL → SGFL → Industry News

**Web Scraping** (`src/scraper.py`)
- `scrape_all_listings()` — Scrapes tender list pages from multiple sources concurrently
- `validate_all_links()` — Validates URLs with SSL downgrade handling
- Three scraping strategies: table rows, link lists, card blocks
- SSL certificate issues common with government sites — handled via known issues whitelist
- Retry decorator with exponential backoff for transient failures

**Configuration** (`config.py`)
- `OFFICIAL_URLS` — Database of official tender detail pages and PDF download links
- `LISTING_URLS` — URLs for scraping tender listings
- `get_fallback_tenders()` — Hardcoded tender data used when scraping fails
- `AppConfig` dataclass with `get()` method for dict-like access

### Type Annotations
All modules use type annotations. Run `mypy src/ config.py main.py` to verify.

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
PDFs are written to `reports/` directory by default (configurable via `--output-dir`). Default filename: `孟加拉标讯报告_YYYYMMDD_HHMMSS.pdf`

### Font Handling
The tool requires Chinese fonts for PDF generation. On macOS it auto-detects PingFang or STHeiti. On Linux, install: `apt install fonts-wqy-microhei` or `fonts-noto-cjk`.

### Testing Link Validation
To quickly check if all official tender links are accessible without generating a report:
```bash
python main.py --validate-only
```

## Development Guidelines

- Follow PEP 8 style guide (enforced by flake8)
- Use type annotations for all public functions
- Run `black` before committing
- Keep modules focused and single-responsibility
