# 孟加拉石油公司国际招标标讯追踪工具 v3.1

自动化抓取 Petrobangla/BAPEX/SGFL/BGFCL 官方网站国际招标信息，生成标准格式 PDF 报告。

## 目录结构

```
tender_report/
├── main.py                      # 主程序入口（CLI + PDF生成 + 邮件）
├── config.py                    # 配置中心（URL数据库、回退数据）
├── src/                         # 源代码包
│   ├── __init__.py
│   ├── models.py                # 数据模型（Tender, ScrapedEntry 等）
│   ├── cli.py                   # 命令行参数解析
│   ├── pdf_generator.py         # PDF 报告生成器
│   ├── email_sender.py          # 邮件推送模块
│   ├── scraper.py               # 网页爬虫（链接校验 + 列表页爬取）
│   ├── data_manager.py          # 数据合并与排序
│   ├── storage.py               # 历史数据持久化
│   └── utils.py                 # 通用工具函数
├── tests/                       # 测试目录
├── reports/                     # 报告输出目录
├── data/                        # 历史数据目录
├── logs/                        # 日志目录
├── requirements.txt             # 生产依赖
├── requirements-dev.txt         # 开发依赖
├── pyproject.toml               # 项目配置与工具链
├── run.sh                       # 一键运行脚本
└── README.md                    # 说明文档
```

## 功能特性

- **模块化架构**：8 个独立模块，职责清晰
- **类型安全**：全代码类型注解，mypy 静态检查通过
- **标准化输出**：统一字体、统一格式、统一排版
- **自动换行**：表格内容自适应，永不溢出
- **大字阅读**：11-18 号字体，阅读轻松
- **时效性**：行业动态自动更新
- **发布日期排序**：标讯按发布日期倒序排列（最新在前）
- **完整字段**：包含保证金、标书价格、联系方式等所有关键信息
- **官方链接**：每个标讯附带可点击的官方详情页 + PDF 下载链接
- **链接校验**：所有链接生成前实时验证，确保可访问
- **新标讯检测**：自动检测并标记新增标讯
- **SSL 安全降级**：对已知证书问题站点显式配置，安全可控
- **重试机制**：指数退避重试，提高爬取稳定性

## 使用方法

### 环境准备

```bash
# 1. 进入项目目录
cd tender_report

# 2. 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 快速开始

```bash
# 一键运行（生成 PDF + 发送邮件）
bash run.sh

# 或直接使用 Python
python main.py
```

### 命令行选项

```bash
# 仅生成 PDF，不发送邮件
python main.py --no-email

# 生成报告前校验所有链接
python main.py --validate

# 仅校验链接，不生成报告
python main.py --validate-only

# 尝试爬取最新标讯
python main.py --scrape

# 指定输出文件名
python main.py --output 自定义文件名.pdf

# 指定输出目录
python main.py --output-dir ./reports

# 显示详细日志
python main.py --verbose
```

### 邮件配置

设置环境变量以启用邮件推送：

```bash
export EMAIL_SMTP_SERVER=smtp.qq.com
export EMAIL_SMTP_PORT=587
export EMAIL_SENDER=your@email.com
export EMAIL_PASSWORD=your_auth_code
export EMAIL_RECIPIENT=recipient@email.com
```

## 报告结构

1. **标讯汇总** - 标讯数量统计、按公司分类
2. **BAPEX 国际招标** - 孟加拉石油勘探开发公司
3. **BGFCL 国际招标** - 孟加拉气田公司
4. **SGFL 国际招标** - 锡尔赫特气田公司
5. **行业动态与市场观察** - 国际局势 + 孟加拉国内新闻

## 开发

### 代码质量工具

```bash
# 类型检查
mypy src/ config.py main.py

# 代码风格检查
flake8 src/ config.py main.py

# 代码格式化
black src/ config.py main.py

# 运行测试
pytest

# 带覆盖率运行测试
pytest --cov=src --cov-report=html
```

### 项目监控的网站

| 公司 | 网址 |
|------|------|
| Petrobangla | https://petrobangla.org.bd/pages/tenders |
| BAPEX | https://bapex.com.bd/pages/tenders |
| SGFL | https://sgfl.gov.bd/pages/tenders |
| BGFCL | https://bgfcl.portal.gov.bd/pages/tenders |

## 版本历史

- **v3.1 (2026-05-14)**：全面重构，模块化架构，类型注解，代码质量工具链
- **v3.0 (2026-05-06)**：新增 CLI 参数、链接校验、网页爬取、新标讯检测
- **v2.1 (2026-05-04)**：增加官方链接字段，所有链接实时校验
- **v2.0 (2026-05-04)**：正式封装版，大字阅读优化，自动换行
- **v1.0 (2026-04-30)**：初始版本
