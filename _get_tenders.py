"""Extract current tender data for summary."""
import sys
sys.path.insert(0, '.')

from config import get_fallback_tenders
from src.data_manager import get_tender_data
from src.storage import HISTORY_FILE
import json

# Get active tender data
data = get_tender_data(scrape=True)

# Print tenders
for tender in data:
    print(f"---")
    print(f"来源: {tender.source}")
    print(f"标题: {tender.title}")
    print(f"采购内容: {tender.description[:200] if tender.description else 'N/A'}")
    print(f"截止日期: {tender.deadline}")
    print(f"发布日: {tender.publish_date}")
    print(f"类型: {tender.tender_type}")
    print(f"新标: {tender.is_new}")
    print()
