# 孟加拉石油标讯追踪工具包 v2.1

## 概述
自动化抓取Petrobangla/BAPEX/SGFL/BGFCL官方网站国际招标信息，生成标准格式PDF报告。

## 目录结构
```
工具包/
├── generate_tender_report.py    # 主程序 - PDF生成器
├── requirements.txt              # Python依赖包
├── 使用示例.py                   # 本地Python调用示例
├── run.sh                        # 一键运行脚本
├── README.md                     # 说明文档
└── config/                       # 配置目录（预留）
```

## 功能特性
- ✅ **标准化输出**：统一字体、统一格式、统一排版
- ✅ **自动换行**：表格内容自适应，永不溢出
- ✅ **大字阅读**：11-18号字体，阅读轻松
- ✅ **时效性**：行业动态自动更新为7天内新闻
- ✅ **按紧迫性排序**：标讯按截止日期远近排序
- ✅ **完整字段**：包含保证金、标书价格、联系方式等所有关键信息
- ✅ **官方链接**：每个标讯附带可点击的官方详情页+PDF下载链接
- ✅ **链接校验**：所有链接生成前实时验证，确保100%可访问

## 使用方法

### 本地Python环境部署（推荐）
```bash
# 1. 进入工具包目录
cd 工具包

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python3 generate_tender_report.py
```

### 方式一：一键运行
```bash
cd 工具包
bash run.sh
```

### 方式二：直接调用Python
```bash
cd 工具包
python3 generate_tender_report.py
```

### 方式三：传入自定义文件名
```bash
python3 generate_tender_report.py --output 自定义文件名.pdf
```

### 方式四：在Python代码中导入调用
```python
# 在你的Python代码中
from generate_tender_report import generate_report, TENDER_DATA

# 生成报告
output_path = generate_report()

# 访问标讯数据
print(f"当前共有 {len(TENDER_DATA)} 条标讯")
```

## 输出位置
PDF报告自动生成到上级目录：
`../孟加拉标讯报告_YYYYMMDD_上午.pdf`

## 报告结构
1. **标讯汇总** - 标讯数量统计、按公司分类
2. **BAPEX国际招标** - 孟加拉石油勘探开发公司
3. **BGFCL国际招标** - 孟加拉气田公司
4. **SGFL国际招标** - 锡尔赫特气田公司
5. **行业动态与市场观察** - 7天内国际局势+孟加拉国内新闻

## 重点关注标讯类型
- 钻井设备与服务（Drilling Rigs & Services）
- 物探设备（Geophysical Equipment）
- 发电机备件（Generator Spare Parts）
- 油田设备采购（Oilfield Equipment）
- 石油技术服务（Petroleum Technical Services）

## 版本历史
- **v2.1 (2026-05-04)**：增加官方链接字段，所有链接实时校验，支持本地Python导入调用
- **v2.0 (2026-05-04)**：正式封装版，大字阅读优化，自动换行
- **v1.0 (2026-04-30)**：初始版本

## 维护说明
本工具由自动日程每日11:00和17:00自动运行两次，生成最新标讯报告。
