import sqlite3
from typing import Dict, List, Optional

from database import Database, InventoryManager


class WarehouseManager:
    """
    仓库管理器
    负责仓库的增、删、改、查操作
    """

    def __init__(self, db: Database):
        self.db = db

    def add_warehouse(self, name: str) -> int:
        """
        添加新仓库
        返回：新仓库的 ID
        """
        name = name.strip()
        if not name:
            raise ValueError("仓库名称不能为空")

        try:
            self.db.execute(
                "INSERT INTO warehouses (name) VALUES (?)",
                (name,)
            )
            return self.db.last_insert_id()
        except sqlite3.IntegrityError:
            raise ValueError(f"仓库名称 '{name}' 已存在，请使用其他名称")
        except Exception as e:
            raise RuntimeError(f"添加仓库失败: {e}") from e

    def list_warehouses(self) -> List[Dict]:
        """获取所有仓库列表（按ID排序）"""
        rows = self.db.fetchall(
            "SELECT id, name, created_at FROM warehouses ORDER BY id"
        )
        return [dict(row) for row in rows]

    def get_warehouse(self, warehouse_id: int) -> Optional[Dict]:
        """根据ID获取单个仓库"""
        row = self.db.fetchone(
            "SELECT id, name, created_at FROM warehouses WHERE id = ?",
            (warehouse_id,)
        )
        return dict(row) if row else None

    def update_warehouse(self, warehouse_id: int, new_name: str) -> bool:
        """
        修改仓库名称
        返回：是否修改成功
        """
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("仓库名称不能为空")

        try:
            self.db.execute(
                "UPDATE warehouses SET name = ? WHERE id = ?",
                (new_name, warehouse_id)
            )
            return self.db.conn.total_changes > 0   # 判断是否有记录被更新
        except sqlite3.IntegrityError:
            raise ValueError(f"仓库名称 '{new_name}' 已存在")
        except Exception as e:
            raise RuntimeError(f"修改仓库失败: {e}") from e

    def delete_warehouse(self, warehouse_id: int) -> bool:
        """
        删除仓库
        - 先检查是否有调度记录
        - 有调度记录则不允许删除
        """
        # 检查是否存在关联的调度记录
        count_row = self.db.fetchone(
            """
            SELECT COUNT(*) as count 
            FROM dispatch_records 
            WHERE from_warehouse_id = ? OR to_warehouse_id = ?
            """,
            (warehouse_id, warehouse_id)
        )

        dispatch_count = count_row['count'] if count_row else 0

        if dispatch_count > 0:
            raise ValueError(
                f"无法删除仓库：该仓库已被用于 {dispatch_count} 条调度记录，请先删除相关调度记录"
            )

        # 执行删除
        self.db.execute("DELETE FROM warehouses WHERE id = ?", (warehouse_id,))
        return True

    def get_warehouse_by_name(self, name: str) -> Optional[Dict]:
        """根据名称查找仓库（辅助方法）"""
        row = self.db.fetchone(
            "SELECT id, name, created_at FROM warehouses WHERE name = ?",
            (name.strip(),)
        )
        return dict(row) if row else None
    
    def list_warehouse_items(self, warehouse_id: int) -> List[Dict]:
        """返回该仓库在库存表中的物料（名称 + 型号 + 数量）"""
        rows = self.db.fetchall(
            """
            SELECT m.id AS material_id, m.name, i.model, i.quantity
            FROM inventory i
            JOIN materials m ON i.material_id = m.id
            WHERE i.warehouse_id = ? AND i.quantity > 0
            ORDER BY m.name, i.model
            """,
            (warehouse_id,),
        )
        return [dict(row) for row in rows]

    def search_material(self, keyword: str) -> List[Dict]:
        """按物料名称或库存型号模糊搜索"""
        param = f"%{keyword.strip()}%"
        rows = self.db.fetchall(
            """
            SELECT w.name AS warehouse, m.name, i.quantity
            FROM inventory i
            JOIN warehouses w ON i.warehouse_id = w.id
            JOIN materials m ON i.material_id = m.id
            WHERE m.name LIKE ? OR i.model LIKE ?
            ORDER BY w.name, m.name
            """,
            (param, param),
        )
        return [dict(row) for row in rows]

    def add_stock(
        self,
        warehouse_id: int,
        material_id: int,
        model: str,
        quantity: float,
    ) -> None:
        """入库（写入 inventory 表）"""
        inv = InventoryManager(self.db)
        inv.add_stock(warehouse_id, material_id, (model or "").strip(), float(quantity))

