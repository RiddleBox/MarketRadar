"""M12数据迁移脚本 - 备份旧数据并创建新目录结构"""
import shutil
from pathlib import Path
from datetime import datetime

def migrate_m12_data():
    """备份旧数据并创建新目录结构"""
    print("=" * 60)
    print("M12 数据迁移脚本")
    print("=" * 60)

    # 1. 备份旧数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"data/backups/m12_migration_{timestamp}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[BACKUP] 备份旧数据到: {backup_dir}")

    old_files = [
        "data/m12_scan_results.json",
        "data/retro_opportunities",
    ]

    for old_path in old_files:
        old_path = Path(old_path)
        if old_path.exists():
            if old_path.is_file():
                shutil.copy2(old_path, backup_dir / old_path.name)
            else:
                shutil.copytree(old_path, backup_dir / old_path.name, dirs_exist_ok=True)
            print(f"[OK] 已备份: {old_path}")
        else:
            print(f"[WARN] 不存在: {old_path}")

    # 2. 创建新目录结构
    new_base = Path("data/m12_scans")
    (new_base / "intraday").mkdir(parents=True, exist_ok=True)
    (new_base / "premarket").mkdir(parents=True, exist_ok=True)
    (new_base / "postmarket").mkdir(parents=True, exist_ok=True)
    print(f"\n[OK] 已创建新目录: {new_base}")
    print(f"  - {new_base / 'intraday'}")
    print(f"  - {new_base / 'premarket'}")
    print(f"  - {new_base / 'postmarket'}")

    # 3. 迁移历史数据（可选，如果需要保留历史记录）
    # 这里可以添加迁移逻辑，将旧格式转换为新格式

    print("\n" + "=" * 60)
    print("[SUCCESS] 数据迁移完成！")
    print("=" * 60)
    print(f"  - 备份位置: {backup_dir}")
    print(f"  - 新数据位置: {new_base}")
    print("\n[WARN] 注意: 旧数据已备份，但未删除原文件")
    print("  - 验证新系统正常运行后，可手动删除旧文件")

if __name__ == "__main__":
    migrate_m12_data()
