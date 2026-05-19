# -*- coding: utf-8 -*-
"""数据持久化模块 —— 历史标讯存储与新标讯检测 v3.1"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models import DetectionStats, Tender

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "tender_history.json"


class HistoryManager:
    """历史记录管理器"""

    def __init__(self, data_dir: Path = DATA_DIR, history_file: Path = HISTORY_FILE) -> None:
        self.data_dir = data_dir
        self.history_file = history_file

    def _ensure_data_dir(self) -> None:
        """确保数据目录存在。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _generate_tender_hash(self, tender: Tender) -> str:
        """生成标讯的唯一标识哈希。

        Args:
            tender: 标讯对象

        Returns:
            12 字符的 MD5 哈希值
        """
        # 使用标题和招标编号作为唯一标识
        tender_id = f"{tender.title}"
        # 尝试获取招标编号
        for field in tender.fields:
            if field.name in ["招标编号", "Tender No", "Tender Number"]:
                tender_id += f"|{field.value}"
                break

        return hashlib.md5(tender_id.encode()).hexdigest()[:12]

    def load_history(self) -> Dict[str, Any]:
        """加载历史标讯数据。

        Returns:
            历史数据字典
        """
        self._ensure_data_dir()

        if not self.history_file.exists():
            return {"version": 1, "last_run": None, "tenders": {}}

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"历史文件读取失败: {e}，使用空历史")
            return {"version": 1, "last_run": None, "tenders": {}}

    def save_history(self, history: Dict[str, Any]) -> None:
        """保存历史标讯数据。

        Args:
            history: 历史数据字典
        """
        self._ensure_data_dir()
        history["last_run"] = datetime.now().isoformat()
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"历史文件保存失败: {e}")

    def detect_new_tenders(
        self, current_tenders: Dict[str, List[Tender]]
    ) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
        """检测新增标讯（已禁用历史标记，所有标讯均不标记为 NEW）。

        Args:
            current_tenders: 当前获取的标讯字典 {"BAPEX": [...], "BGFCL": [...], ...}

        Returns:
            (合并后的标讯, 新增数量, 统计信息)
        """
        merged: Dict[str, List[Tender]] = {}
        stats = DetectionStats(total=0, new=0, by_company={})

        for company, tenders in current_tenders.items():
            merged[company] = []
            for tender in tenders:
                tender._is_new = False
                merged[company].append(tender)
                stats.total += 1

            stats.by_company[company] = {
                "total": len(tenders),
                "new": 0,
            }

        return merged, 0, stats

    def get_last_run_time(self) -> Optional[datetime]:
        """获取上次运行时间。

        Returns:
            datetime 对象或 None
        """
        history = self.load_history()
        last_run = history.get("last_run")
        if last_run:
            try:
                return datetime.fromisoformat(last_run)
            except ValueError:
                logger.warning(f"上次运行时间格式错误: {last_run}")
        return None

    def clear_history(self) -> None:
        """清空历史数据。"""
        if self.history_file.exists():
            try:
                self.history_file.unlink()
                logger.info("历史数据已清空")
            except IOError as e:
                logger.error(f"清空历史数据失败: {e}")


# 兼容旧版 API 的函数
_history_manager = HistoryManager()


def detect_new_tenders(
    current_tenders: Dict[str, List[Tender]],
) -> Tuple[Dict[str, List[Tender]], int, DetectionStats]:
    """检测新增标讯（兼容旧版 API）"""
    return _history_manager.detect_new_tenders(current_tenders)


def get_last_run_time() -> Optional[datetime]:
    """获取上次运行时间（兼容旧版 API）"""
    return _history_manager.get_last_run_time()


def clear_history() -> None:
    """清空历史数据（兼容旧版 API）"""
    _history_manager.clear_history()
