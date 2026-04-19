"""
用「整库文件」恢复 wellsite.db（SQLite 完整拷贝）。

请先完全退出本程序（含打包后的 exe），否则 Windows 可能因文件被占用而无法覆盖。

用法示例：
  .venv\\Scripts\\python scripts\\restore_wellsite_db.py "D:\\备份\\wellsite.db"
  .venv\\Scripts\\python scripts\\restore_wellsite_db.py "D:\\备份\\wellsite.db" -t "dist\\仓库物资调度\\wellsite.db"

说明：界面里「立即备份」导出的 backup.json 只有仓库/物料/调度摘要，不能还原库存与调度明细；
      要完整恢复数据，必须使用当时复制下来的 wellsite.db（或整盘备份里的该文件）。
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = ROOT / "wellsite.db"


def _is_sqlite3(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(15) == b"SQLite format 3"
    except OSError:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="用备份的 wellsite.db 覆盖当前数据库")
    ap.add_argument("source", help="备份数据库文件路径（.db）")
    ap.add_argument(
        "-t",
        "--target",
        default=str(DEFAULT_TARGET),
        help=f"要写入的目标路径（默认：{DEFAULT_TARGET}）",
    )
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    tgt = Path(args.target).expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"源文件不存在：{src}")
    if not _is_sqlite3(src):
        raise SystemExit(f"不是有效的 SQLite 3 文件：{src}")

    tgt.parent.mkdir(parents=True, exist_ok=True)
    if tgt.exists():
        bak = tgt.with_name(f"{tgt.stem}.bak_{int(time.time())}{tgt.suffix}")
        shutil.copy2(tgt, bak)
        print("已将当前数据库备份为：", bak)
    shutil.copy2(src, tgt)
    print("已恢复数据库到：", tgt)


if __name__ == "__main__":
    main()
