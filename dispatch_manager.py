import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from database import Database


class DispatchManager:
    """
    调度记录管理器
    负责调度记录的增、删、查、导出及仓库流向统计
    """

    def __init__(self, db: Database):
        self.db = db

    _DISPATCH_ITEMS_FROM = """
            FROM dispatch_items di
            JOIN materials m ON di.material_id = m.id
            LEFT JOIN material_models mm ON di.model_id = mm.id
            LEFT JOIN material_models mm_label
                ON mm_label.material_id = di.material_id
                AND di.model_id IS NULL
                AND TRIM(COALESCE(di.model_label, '')) != ''
                AND mm_label.model = TRIM(COALESCE(di.model_label, ''))
    """

    @staticmethod
    def format_items_summary(items: List[Dict]) -> str:
        """将调度明细列表拼成与列表页一致的「所含物品」字符串（含型号、数量、单位）。"""
        if not items:
            return ""
        parts: List[str] = []
        for it in items:
            name = it.get("material_name") or ""
            mod = (it.get("model_name") or "").strip()
            label = f"{name}({mod})" if mod else name
            q = it.get("quantity")
            try:
                qf = float(q)
                qs = str(int(qf)) if qf == int(qf) else str(qf).rstrip("0").rstrip(".")
            except (TypeError, ValueError):
                qs = str(q)
            unit = (it.get("unit") or "").strip()
            seg = f"{label} x{qs}"
            if unit:
                seg += f" {unit}"
            parts.append(seg)
        # 每个物品单独一行，便于调度表里阅读
        return "\n".join(parts)

    @staticmethod
    def _resolve_model_str(cursor: sqlite3.Cursor, item: Dict[str, Any]) -> str:
        lab = item.get("model_label")
        if lab is not None and str(lab).strip():
            return str(lab).strip()
        mid = item.get("model_id")
        if mid:
            cursor.execute(
                "SELECT model FROM material_models WHERE id = ?",
                (mid,),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        return ""

    def add_dispatch(
        self,
        from_warehouse_id: int,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        image_path: Optional[str] = None,
        executor: Optional[str] = None,
        remarks: Optional[str] = None,
        dispatch_time: Optional[str] = None,
    ) -> int:
        """
        添加一条调度记录（同一事务内扣减调出仓、增加调入仓库存）
        items 示例: [{"material_id": 1, "quantity": 5.0, "model_id": 可选, "model_label": 可选}, ...]
        返回: 新调度记录的 ID
        """
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("调出仓库和调入仓库不能相同")

        if not items or len(items) == 0:
            raise ValueError("调度记录必须至少包含一种物料")

        for item in items:
            if not item.get("material_id") or item.get("quantity") is None or item.get("quantity") <= 0:
                raise ValueError("物料ID和数量必须有效且数量大于0")

        conn = self.db.conn
        cursor = conn.cursor()
        if not dispatch_time:
            dispatch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                """
                INSERT INTO dispatch_records
                (from_warehouse_id, to_warehouse_id, timestamp, image_path, executor, remarks)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    from_warehouse_id,
                    to_warehouse_id,
                    dispatch_time,
                    image_path,
                    (executor or "").strip() or None,
                    remarks,
                ),
            )
            record_id = int(cursor.lastrowid)

            for item in items:
                model_str = self._resolve_model_str(cursor, item)
                qty = float(item["quantity"])
                mid = int(item["material_id"])

                cursor.execute(
                    """
                    SELECT quantity FROM inventory
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (from_warehouse_id, mid, model_str),
                )
                row = cursor.fetchone()
                current = float(row[0]) if row else 0.0

                # 调出仓无库存时：只生成调度记录，不做库存联动
                if current <= 0:
                    cursor.execute(
                        """
                        INSERT INTO dispatch_items
                        (record_id, material_id, model_id, quantity, model_label)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            mid,
                            item.get("model_id"),
                            qty,
                            item.get("model_label"),
                        ),
                    )
                    continue

                if current < qty:
                    raise ValueError(
                        f"库存不足：需要 {qty}，调出仓库当前 {current}（物料 ID {mid}，型号「{model_str or '默认'}」）"
                    )
                cursor.execute(
                    """
                    UPDATE inventory SET quantity = quantity - ?
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (qty, from_warehouse_id, mid, model_str),
                )

                cursor.execute(
                    """
                    INSERT INTO inventory (warehouse_id, material_id, model, quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, material_id, model) DO UPDATE SET
                        quantity = quantity + excluded.quantity
                    """,
                    (to_warehouse_id, mid, model_str, qty),
                )

                cursor.execute(
                    """
                    INSERT INTO dispatch_items
                    (record_id, material_id, model_id, quantity, model_label)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        mid,
                        item.get("model_id"),
                        qty,
                        item.get("model_label"),
                    ),
                )

            conn.commit()
            return record_id

        except ValueError:
            conn.rollback()
            raise
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f"添加调度失败：仓库或物料不存在 - {e}") from e
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"添加调度记录失败: {e}") from e

    def update_dispatch(
        self,
        record_id: int,
        from_warehouse_id: int,
        to_warehouse_id: int,
        items: List[Dict[str, Any]],
        image_path: Optional[str] = None,
        executor: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> None:
        """
        修改已有调度：先按原明细尽量撤销库存（仅当调入仓仍有足够数量时视为当时做过库存联动），
        再更新主表、替换明细并按新内容重新做库存联动（与 add_dispatch 规则一致）。
        """
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("调出仓库和调入仓库不能相同")
        if not items:
            raise ValueError("调度记录必须至少包含一种物料")
        for item in items:
            if not item.get("material_id") or item.get("quantity") is None or item.get("quantity") <= 0:
                raise ValueError("物料ID和数量必须有效且数量大于0")

        old = self.get_dispatch_detail(record_id)
        if not old:
            raise ValueError("调度记录不存在")

        old_from = int(old["from_warehouse_id"])
        old_to = int(old["to_warehouse_id"])
        old_items = old.get("items") or []

        conn = self.db.conn
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")

            for it in old_items:
                model_str = (it.get("model_name") or "").strip()
                mid = int(it["material_id"])
                qty = float(it["quantity"])

                cursor.execute(
                    """
                    SELECT quantity FROM inventory
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (old_to, mid, model_str),
                )
                row = cursor.fetchone()
                to_q = float(row[0]) if row else 0.0

                if to_q < qty:
                    continue

                cursor.execute(
                    """
                    UPDATE inventory SET quantity = quantity - ?
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (qty, old_to, mid, model_str),
                )
                cursor.execute(
                    """
                    INSERT INTO inventory (warehouse_id, material_id, model, quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, material_id, model) DO UPDATE SET
                        quantity = quantity + excluded.quantity
                    """,
                    (old_from, mid, model_str, qty),
                )

            cursor.execute("DELETE FROM dispatch_items WHERE record_id = ?", (record_id,))
            cursor.execute(
                """
                UPDATE dispatch_records
                SET from_warehouse_id = ?, to_warehouse_id = ?, image_path = ?, executor = ?, remarks = ?
                WHERE id = ?
                """,
                (
                    from_warehouse_id,
                    to_warehouse_id,
                    image_path,
                    (executor or "").strip() or None,
                    remarks,
                    record_id,
                ),
            )

            for item in items:
                model_str = self._resolve_model_str(cursor, item)
                qty = float(item["quantity"])
                mid = int(item["material_id"])

                cursor.execute(
                    """
                    SELECT quantity FROM inventory
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (from_warehouse_id, mid, model_str),
                )
                row = cursor.fetchone()
                current = float(row[0]) if row else 0.0

                if current <= 0:
                    cursor.execute(
                        """
                        INSERT INTO dispatch_items
                        (record_id, material_id, model_id, quantity, model_label)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            mid,
                            item.get("model_id"),
                            qty,
                            item.get("model_label"),
                        ),
                    )
                    continue

                if current < qty:
                    raise ValueError(
                        f"库存不足：需要 {qty}，调出仓库当前 {current}（物料 ID {mid}，型号「{model_str or '默认'}」）"
                    )
                cursor.execute(
                    """
                    UPDATE inventory SET quantity = quantity - ?
                    WHERE warehouse_id = ? AND material_id = ? AND model = ?
                    """,
                    (qty, from_warehouse_id, mid, model_str),
                )
                cursor.execute(
                    """
                    INSERT INTO inventory (warehouse_id, material_id, model, quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, material_id, model) DO UPDATE SET
                        quantity = quantity + excluded.quantity
                    """,
                    (to_warehouse_id, mid, model_str, qty),
                )
                cursor.execute(
                    """
                    INSERT INTO dispatch_items
                    (record_id, material_id, model_id, quantity, model_label)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        mid,
                        item.get("model_id"),
                        qty,
                        item.get("model_label"),
                    ),
                )

            conn.commit()
        except ValueError:
            conn.rollback()
            raise
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f"更新调度失败：仓库或物料不存在 - {e}") from e
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"更新调度记录失败: {e}") from e

    def list_dispatches(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict]:
        """查询调度记录列表（支持时间范围过滤）"""
        query = """
            SELECT 
                dr.id, 
                dr.from_warehouse_id, 
                dr.to_warehouse_id, 
                dr.timestamp, 
                dr.image_path, 
                dr.executor,
                dr.remarks,
                fw.name AS from_name, 
                tw.name AS to_name 
            FROM dispatch_records dr 
            JOIN warehouses fw ON dr.from_warehouse_id = fw.id 
            JOIN warehouses tw ON dr.to_warehouse_id = tw.id 
            WHERE 1=1
        """
        params: List[Any] = []

        if start_time:
            query += " AND dr.timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND dr.timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY dr.timestamp DESC"

        rows = self.db.fetchall(query, params)
        return [dict(row) for row in rows]

    def list_records(self) -> List[Dict]:
        """供 UI 导出/备份使用（扁平字段名）"""
        rows = self.list_dispatches()
        out: List[Dict] = []
        for r in rows:
            items = self.get_dispatch_items(r["id"])
            all_mat = DispatchManager.format_items_summary(items) if items else ""
            out.append(
                {
                    "id": r["id"],
                    "executor": r.get("executor"),
                    "from_warehouse": r.get("from_name"),
                    "to_warehouse": r.get("to_name"),
                    "timestamp": r["timestamp"],
                    "all_materials": all_mat,
                    "image_path": r.get("image_path"),
                    "remarks": r.get("remarks"),
                }
            )
        return out

    def get_dispatch_items(self, record_id: int) -> List[Dict]:
        """获取某条调度记录的物料明细"""
        rows = self.db.fetchall(
            f"""
            SELECT
                di.id,
                di.record_id,
                di.material_id,
                di.model_id,
                di.quantity,
                di.model_label AS dispatch_model_label,
                m.name AS material_name,
                m.unit,
                COALESCE(
                    mm.model,
                    mm_label.model,
                    NULLIF(TRIM(COALESCE(di.model_label, '')), ''),
                    ''
                ) AS model_name
            {self._DISPATCH_ITEMS_FROM}
            WHERE di.record_id = ?
            ORDER BY di.id
            """,
            (record_id,),
        )
        return [dict(row) for row in rows]

    def list_dispatch_items_for_records(self, record_ids: Sequence[int]) -> Dict[int, List[Dict]]:
        """一次查询多条调度单的明细，key 为 record_id。"""
        if not record_ids:
            return {}
        ids = sorted({int(x) for x in record_ids})
        ph = ",".join("?" * len(ids))
        rows = self.db.fetchall(
            f"""
            SELECT
                di.id,
                di.record_id,
                di.material_id,
                di.model_id,
                di.quantity,
                di.model_label AS dispatch_model_label,
                m.name AS material_name,
                m.unit,
                COALESCE(
                    mm.model,
                    mm_label.model,
                    NULLIF(TRIM(COALESCE(di.model_label, '')), ''),
                    ''
                ) AS model_name
            {self._DISPATCH_ITEMS_FROM}
            WHERE di.record_id IN ({ph})
            ORDER BY di.record_id, di.id
            """,
            ids,
        )
        out: Dict[int, List[Dict]] = {}
        for row in rows:
            d = dict(row)
            rid = int(d["record_id"])
            out.setdefault(rid, []).append(d)
        return out

    def get_dispatch_detail(self, record_id: int) -> Optional[Dict]:
        """获取单条调度记录的完整信息（主记录 + 明细）"""
        record = self.db.fetchone(
            """
            SELECT 
                dr.*, 
                fw.name AS from_name, 
                tw.name AS to_name 
            FROM dispatch_records dr 
            JOIN warehouses fw ON dr.from_warehouse_id = fw.id 
            JOIN warehouses tw ON dr.to_warehouse_id = tw.id 
            WHERE dr.id = ?
            """,
            (record_id,),
        )
        if not record:
            return None

        data = dict(record)
        data['items'] = self.get_dispatch_items(record_id)
        return data

    def export_to_excel(self, filename: str, dispatches: List[Dict]):
        """将调度记录导出为 Excel 文件"""
        if not dispatches:
            raise ValueError("没有可导出的调度记录")

        try:
            rows = []
            for dispatch in dispatches:
                items = self.get_dispatch_items(dispatch['id'])
                for item in items:
                    mname = item["material_name"]
                    mod = (item.get("model_name") or "").strip()
                    if mod:
                        mname = f"{mname}({mod})"
                    rows.append({
                        '记录ID': dispatch['id'],
                        '调出仓库': dispatch.get('from_name', ''),
                        '调入仓库': dispatch.get('to_name', ''),
                        '调度时间': dispatch['timestamp'],
                        '执行人': dispatch.get('executor') or '',
                        '备注': dispatch.get('remarks') or '',
                        '物料名称': mname,
                        '单位': item['unit'],
                        '数量': item['quantity'],
                        '图片路径': dispatch.get('image_path') or '',
                    })

            df = pd.DataFrame(rows)
            df.to_excel(filename, index=False, engine='openpyxl')
            return True
        except Exception as e:
            raise RuntimeError(f"导出 Excel 失败: {e}") from e

    def get_warehouse_flow(self, warehouse_id: int) -> Dict[str, List[Dict]]:
        """获取指定仓库的流入和流出记录"""
        # 流入记录
        inflow = self.db.fetchall(
            """
            SELECT 
                dr.id, dr.timestamp, fw.name AS from_name, 
                tw.name AS to_name, dr.image_path, dr.executor, dr.remarks
            FROM dispatch_records dr 
            JOIN warehouses fw ON dr.from_warehouse_id = fw.id 
            JOIN warehouses tw ON dr.to_warehouse_id = tw.id 
            WHERE dr.to_warehouse_id = ? 
            ORDER BY dr.timestamp DESC
            """,
            (warehouse_id,),
        )

        # 流出记录
        outflow = self.db.fetchall(
            """
            SELECT 
                dr.id, dr.timestamp, fw.name AS from_name, 
                tw.name AS to_name, dr.image_path, dr.executor, dr.remarks
            FROM dispatch_records dr 
            JOIN warehouses fw ON dr.from_warehouse_id = fw.id 
            JOIN warehouses tw ON dr.to_warehouse_id = tw.id 
            WHERE dr.from_warehouse_id = ? 
            ORDER BY dr.timestamp DESC
            """,
            (warehouse_id,),
        )

        return {
            'inflow': [dict(row) for row in inflow],
            'outflow': [dict(row) for row in outflow],
        }

    def delete_dispatch(self, record_id: int) -> bool:
        """删除一条调度记录（同时删除其明细）"""
        try:
            # 由于设置了 ON DELETE CASCADE，删除主记录即可
            self.db.execute("DELETE FROM dispatch_records WHERE id = ?", (record_id,))
            return True
        except Exception as e:
            raise RuntimeError(f"删除调度记录失败: {e}") from e