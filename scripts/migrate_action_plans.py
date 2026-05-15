#!/usr/bin/env python3
"""
scripts/migrate_action_plans.py — 存量 ActionPlan 迁移工具

将 data/action_plans/ 中所有旧版计划（缺少结构化 entry_conditions）批量更新，
通过正则解析 text trigger_condition 提取机器可评估的 EntryCondition。

用法:
  python scripts/migrate_action_plans.py              # 执行迁移（自动备份）
  python scripts/migrate_action_plans.py --dry-run    # 仅预览，不写文件
  python scripts/migrate_action_plans.py --no-backup  # 执行迁移，不备份
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from m4_action.action_designer import ActionDesigner

PLANS_DIR = PROJECT_ROOT / "data" / "action_plans"
BACKUP_DIR = PROJECT_ROOT / "data" / "action_plans_backup"


def backup_plans() -> Path:
    """创建存量计划的全量备份。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / timestamp
    shutil.copytree(PLANS_DIR, backup_path)
    print(f"[Migrate] 备份完成: {backup_path} ({len(list(backup_path.glob('*.json')))} 文件)")
    return backup_path


def migrate_all_plans(dry_run: bool = False, no_backup: bool = False) -> dict:
    """批量迁移存量计划。

    Args:
        dry_run: 仅预览，不写文件
        no_backup: 不创建备份

    Returns:
        {"total": int, "extracted": int, "failed": int, "details": list[dict]}
    """
    if not PLANS_DIR.exists():
        print(f"[Migrate] 计划目录不存在: {PLANS_DIR}")
        return {"total": 0, "extracted": 0, "failed": 0, "details": []}

    if not dry_run and not no_backup:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_plans()

    stats = {"total": 0, "extracted": 0, "failed": 0, "details": []}

    for plan_file in sorted(PLANS_DIR.glob("*.json")):
        stats["total"] += 1
        try:
            data = json.loads(plan_file.read_text(encoding="utf-8"))
        except Exception as e:
            stats["details"].append({"file": plan_file.name, "status": "error", "error": str(e)})
            continue

        modified = False
        phases = data.get("phases", [])
        phase_extracted = 0

        for phase in phases:
            # 跳过已有结构化条件的 phase
            if phase.get("entry_conditions"):
                continue

            text = phase.get("trigger_condition") or ""
            conditions = ActionDesigner._extract_conditions_from_text(text)
            if conditions:
                phase["entry_conditions"] = conditions
                modified = True
                phase_extracted += len(conditions)

        # 补 entry_condition_summary（如果用 plan_summary）
        if not data.get("entry_condition_summary") and data.get("plan_summary"):
            data["entry_condition_summary"] = data["plan_summary"]
            modified = True

        if modified and not dry_run:
            plan_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

        detail = {
            "file": plan_file.name,
            "modified": modified,
            "extracted_count": phase_extracted,
            "phases": len(phases),
        }
        if phase_extracted > 0:
            stats["extracted"] += 1
            detail["status"] = "extracted"
        elif modified:
            stats["failed"] += 1
            detail["status"] = "summary_only"
        else:
            stats["failed"] += 1
            detail["status"] = "no_extractable"
            # 显示前 60 字符 trigger_condition 供参考
            tc = phases[0].get("trigger_condition", "")[:60] if phases else ""
            detail["trigger_condition_preview"] = tc

        stats["details"].append(detail)

    return stats


def print_report(stats: dict):
    """打印迁移报告。"""
    summary_only = sum(1 for d in stats["details"] if d["status"] == "summary_only")
    no_extractable = sum(1 for d in stats["details"] if d["status"] == "no_extractable")

    print(f"\n{'='*50}")
    print(f"  迁移报告")
    print(f"{'='*50}")
    print(f"  总计:              {stats['total']} 个计划")
    print(f"  已提取条件:         {stats['extracted']} 个")
    print(f"  仅补全摘要:         {summary_only} 个")
    print(f"  无法解析:           {no_extractable} 个")
    print()

    if no_extractable > 0 and stats["details"]:
        print("  无法解析的计划（trigger_condition 文本预览）:")
        for d in stats["details"]:
            if d["status"] == "no_extractable":
                tc = d.get("trigger_condition_preview", "")
                print(f"    - {d['file'][:30]:30s} | {tc}")
        print()


def main():
    parser = argparse.ArgumentParser(description="存量 ActionPlan 迁移工具")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写文件")
    parser.add_argument("--no-backup", action="store_true", help="执行迁移但不创建备份")
    parser.add_argument("--show-extracted", action="store_true", help="显示提取的条件详情")
    args = parser.parse_args()

    if args.dry_run:
        print("[Migrate] DRY RUN 模式 — 不会修改任何文件\n")

    stats = migrate_all_plans(dry_run=args.dry_run, no_backup=args.no_backup)
    print_report(stats)

    if args.show_extracted and stats["details"]:
        print("  提取条件的计划详情:")
        for d in stats["details"]:
            if d["status"] == "extracted":
                print(f"    {d['file'][:30]:30s} | {d['extracted_count']} conditions")
        print()

    if args.dry_run:
        print("[Migrate] DRY RUN 完成，未修改任何文件")
    else:
        print(f"[Migrate] 迁移完成 ({stats['extracted']} 成功, {stats['failed']} 跳过)")


if __name__ == "__main__":
    main()
