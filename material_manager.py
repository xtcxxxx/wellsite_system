import sqlite3
from typing import Dict, List, Optional

from database import Database

_UNSET = object()


class MaterialManager:
    """
    物料管理器
    管理 materials + material_models
    """

    def __init__(self, db: Database):
        self.db = db

    def add_category(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("类别名称不能为空")
        try:
            self.db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            return int(self.db.last_insert_id())
        except sqlite3.IntegrityError:
            raise ValueError(f"类别「{name}」已存在")

    def list_categories(self) -> List[Dict]:
        rows = self.db.fetchall("SELECT id, name FROM categories ORDER BY name")
        return [dict(row) for row in rows]

    def delete_category(self, category_id: int) -> bool:
        """
        删除类别：将该类别下的物料改为未分类（category_id 置空），再删除类别行。
        """
        row = self.db.fetchone("SELECT id, name FROM categories WHERE id = ?", (category_id,))
        if not row:
            raise ValueError("类别不存在或已被删除")
        self.db.execute(
            "UPDATE materials SET category_id = NULL WHERE category_id = ?",
            (category_id,),
        )
        self.db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        return True

    def find_model_id(self, material_id: int, model_text: str) -> Optional[int]:
        text = (model_text or "").strip()
        if not text:
            return None
        row = self.db.fetchone(
            "SELECT id FROM material_models WHERE material_id = ? AND model = ?",
            (material_id, text),
        )
        return int(row["id"]) if row else None

    # ==================== 添加物料 ====================
    def add_material(
        self,
        name: str,
        unit: str,
        model: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> int:
        """
        添加新物料
        如果提供 model，存入 material_models 表
        返回新物料 ID
        """
        name = name.strip()
        unit = unit.strip()
        if not name:
            raise ValueError("物料名称不能为空")
        if not unit:
            raise ValueError("物料单位不能为空")

        try:
            # 插入物料
            self.db.execute(
                "INSERT INTO materials (name, unit, category_id) VALUES (?, ?, ?)",
                (name, unit, category_id),
            )
            material_id = self.db.last_insert_id()

            # 如果提供型号，插入 material_models
            if model:
                for m in model.split(","):
                    m = m.strip()
                    if m:
                        self.db.execute(
                            "INSERT INTO material_models (material_id, model) VALUES (?, ?)",
                            (material_id, m)
                        )
            return material_id
        except sqlite3.IntegrityError:
            raise ValueError(f"物料名称 '{name}' 已存在，请使用其他名称")
        except Exception as e:
            raise RuntimeError(f"添加物料失败: {e}") from e

    # ==================== 查询物料 ====================
    def list_materials(self) -> List[Dict]:
        """
        获取所有物料列表（按ID排序）
        model 会显示所有型号，逗号分隔
        """
        rows = self.db.fetchall("""
            SELECT m.id, m.name, m.unit, m.category_id, c.name AS category, group_concat(mm.model) AS model
            FROM materials m
            LEFT JOIN categories c ON m.category_id = c.id
            LEFT JOIN material_models mm ON mm.material_id = m.id
            GROUP BY m.id
            ORDER BY m.id
        """)
        return [dict(row) for row in rows]

    def get_material(self, material_id: int) -> Optional[Dict]:
        """根据 ID 获取单个物料及型号"""
        row = self.db.fetchone("""
            SELECT m.id, m.name, m.unit, m.category_id, c.name AS category, group_concat(mm.model) AS model
            FROM materials m
            LEFT JOIN categories c ON m.category_id = c.id
            LEFT JOIN material_models mm ON mm.material_id = m.id
            WHERE m.id = ?
            GROUP BY m.id
        """, (material_id,))
        return dict(row) if row else None

    def get_material_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取物料及型号"""
        row = self.db.fetchone("""
            SELECT m.id, m.name, m.unit, m.category_id, c.name AS category, group_concat(mm.model) AS model
            FROM materials m
            LEFT JOIN categories c ON m.category_id = c.id
            LEFT JOIN material_models mm ON mm.material_id = m.id
            WHERE m.name = ?
            GROUP BY m.id
        """, (name.strip(),))
        return dict(row) if row else None

    # ==================== 更新物料 ====================
    def update_material(
        self,
        material_id: int,
        name: Optional[str] = None,
        unit: Optional[str] = None,
        model: Optional[str] = None,
        category_id: object = _UNSET,
    ) -> bool:
        """
        更新物料信息（支持部分更新）
        model 字符串格式：逗号分隔多个型号；传空字符串可清空全部型号
        category_id：不传则不改类别；传 int 或 None（未分类）则更新
        """
        updates = []
        params = []

        if category_id is not _UNSET:
            updates.append("category_id = ?")
            params.append(category_id)

        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("物料名称不能为空")
            updates.append("name = ?")
            params.append(name)

        if unit is not None:
            unit = unit.strip()
            if not unit:
                raise ValueError("物料单位不能为空")
            updates.append("unit = ?")
            params.append(unit)

        if updates:
            query = f"UPDATE materials SET {', '.join(updates)} WHERE id = ?"
            params.append(material_id)
            try:
                self.db.execute(query, params)
            except sqlite3.IntegrityError:
                if name is not None:
                    raise ValueError(f"物料名称「{name}」已存在，请换一个名称")
                raise ValueError("更新失败：与已有数据冲突（例如名称重复）")
            except Exception as e:
                raise RuntimeError(f"更新物料失败: {e}") from e

        # 更新型号
        if model is not None:
            old_rows = self.db.fetchall(
                "SELECT model FROM material_models WHERE material_id = ? ORDER BY id",
                (material_id,),
            )
            old_texts = [(row["model"] or "").strip() for row in old_rows]

            # 调度明细可能仍引用 material_models.id，直接删型号会触发外键失败
            self.db.execute(
                """
                UPDATE dispatch_items
                SET model_label = COALESCE(
                        NULLIF(TRIM(COALESCE(model_label, '')), ''),
                        (SELECT mm.model FROM material_models mm WHERE mm.id = dispatch_items.model_id)
                    ),
                    model_id = NULL
                WHERE model_id IN (SELECT id FROM material_models WHERE material_id = ?)
                """,
                (material_id,),
            )
            self.db.execute("DELETE FROM material_models WHERE material_id = ?", (material_id,))

            new_models: List[str] = []
            for m in model.split(","):
                m = m.strip()
                if m:
                    new_models.append(m)
                    self.db.execute(
                        "INSERT INTO material_models (material_id, model) VALUES (?, ?)",
                        (material_id, m),
                    )

            # 历史调度明细里 model_label 仍是旧文案（如 50），列表无法显示新型号（Ø50）
            # 在「旧型号条数 == 新型号条数」时按顺序一一替换；编辑时尽量保持型号顺序与原来一致
            if len(old_texts) == len(new_models) and old_texts:
                for old_t, new_t in zip(old_texts, new_models):
                    if old_t == new_t:
                        continue
                    self.db.execute(
                        """
                        UPDATE dispatch_items
                        SET model_label = ?
                        WHERE material_id = ? AND TRIM(COALESCE(model_label, '')) = ?
                        """,
                        (new_t, material_id, old_t),
                    )

            # 旧型号只有 1 条（如 50）、新型号有多条时 zip 不跑：若新型号里唯一「包含」旧串的一条（如 Ø50），则升级历史 label
            if len(old_texts) == 1 and old_texts[0]:
                old_t = old_texts[0]
                cands = [nt for nt in new_models if old_t != nt and old_t in nt]
                if len(cands) == 1:
                    self.db.execute(
                        """
                        UPDATE dispatch_items
                        SET model_label = ?
                        WHERE material_id = ? AND TRIM(COALESCE(model_label, '')) = ?
                        """,
                        (cands[0], material_id, old_t),
                    )

            # 把已与新型号表一致的明细重新挂上 model_id，列表/详情可走 JOIN 显示完整字符串
            seen_new: set[str] = set()
            for new_t in new_models:
                if new_t in seen_new:
                    continue
                seen_new.add(new_t)
                mid = self.find_model_id(material_id, new_t)
                if mid is None:
                    continue
                self.db.execute(
                    """
                    UPDATE dispatch_items
                    SET model_id = ?, model_label = NULL
                    WHERE material_id = ?
                      AND TRIM(COALESCE(model_label, '')) = ?
                      AND model_id IS NULL
                    """,
                    (mid, material_id, new_t),
                )

        return True

    # ==================== 删除物料 ====================
    def delete_material(self, material_id: int) -> bool:
        """
        删除物料
        - 若存在调度明细引用则禁止删除
        - 先删除 inventory 中该物料的库存，再删型号与物料主表
        """
        # 检查是否被调度记录使用
        count_row = self.db.fetchone(
            "SELECT COUNT(*) as count FROM dispatch_items WHERE material_id = ?",
            (material_id,)
        )
        used_count = count_row['count'] if count_row else 0
        if used_count > 0:
            raise ValueError(
                f"无法删除物料：该物料已被用于 {used_count} 条调度明细，请先删除相关调度记录"
            )

        # 库存表引用 materials，需先删，否则外键约束失败
        self.db.execute("DELETE FROM inventory WHERE material_id = ?", (material_id,))
        self.db.execute("DELETE FROM material_models WHERE material_id = ?", (material_id,))
        self.db.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        return True