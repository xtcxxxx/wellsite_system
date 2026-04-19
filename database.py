import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple, Union


class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "wellsite.db")
        self.db_path = db_path
        print("数据库路径：", os.path.abspath(self.db_path))

        self.local = threading.local()

        # ⚡ 如果数据库不存在，则创建新文件
        if not os.path.exists(self.db_path):
            print("数据库不存在，创建新数据库...")
        else:
            print("数据库已存在，使用现有数据库")

        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（懒加载）"""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,   # 允许跨线程使用，但我们用 local 控制
                timeout=10.0               # 连接超时
            )
            self.local.conn.row_factory = sqlite3.Row
            # 启用外键约束
            self.local.conn.execute("PRAGMA foreign_keys = ON")
            # 设置忙等待超时（防止长时间锁死）
            self.local.conn.execute("PRAGMA busy_timeout = 5000")
        return self.local.conn

    @contextmanager
    def get_cursor(self):
        """推荐的使用方式：上下文管理器"""
        cursor = self.conn.cursor()
        try:
            yield cursor
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"数据库操作失败: {e}") from e
        finally:
            cursor.close()

    def create_tables(self):
        with self.get_cursor() as cursor:

            # 仓库
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
            )
            """)
            # 类别
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """)

            # 物品
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER,
                unit TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
            """)

            # 型号
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                FOREIGN KEY(material_id) REFERENCES materials(id)
            )
            """)

            # 调度记录
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dispatch_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_warehouse_id INTEGER NOT NULL,
                to_warehouse_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                executor TEXT,
                remarks TEXT
            )
            """)

            # 调度明细（关键升级）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dispatch_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                model_id INTEGER,
                quantity REAL NOT NULL,
                FOREIGN KEY(record_id) REFERENCES dispatch_records(id) ON DELETE CASCADE,
                FOREIGN KEY(material_id) REFERENCES materials(id),
                FOREIGN KEY(model_id) REFERENCES material_models(id)
            )
            """)
            # ==================== ⭐库存表（新增）====================
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                model TEXT DEFAULT '',
                quantity REAL DEFAULT 0,

                UNIQUE(warehouse_id, material_id, model),

                FOREIGN KEY(warehouse_id) REFERENCES warehouses(id),
                FOREIGN KEY(material_id) REFERENCES materials(id)
            )
           """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
            """)

            self._migrate_schema(cursor)
            self.conn.commit()

    def _migrate_schema(self, cursor: sqlite3.Cursor) -> None:
        """为已有数据库补齐新列（CREATE IF NOT EXISTS 不会更新旧表结构）"""
        cursor.execute("PRAGMA table_info(dispatch_records)")
        cols = {row[1] for row in cursor.fetchall()}
        if "image_path" not in cols:
            cursor.execute("ALTER TABLE dispatch_records ADD COLUMN image_path TEXT")

        cursor.execute("PRAGMA table_info(dispatch_items)")
        cols_di = {row[1] for row in cursor.fetchall()}
        if "model_label" not in cols_di:
            cursor.execute("ALTER TABLE dispatch_items ADD COLUMN model_label TEXT")

    # ==================== 基础 CRUD 方法 ====================

    def execute(self, query: str, params: Union[Tuple, List, None] = None) -> sqlite3.Cursor:
        """执行写操作（INSERT / UPDATE / DELETE）"""
        params = params or ()
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            self.conn.commit()
            return cursor

    def fetchall(self, query: str, params: Union[Tuple, List, None] = None) -> List[sqlite3.Row]:
        """查询多条记录"""
        params = params or ()
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def fetchone(self, query: str, params: Union[Tuple, List, None] = None) -> Optional[sqlite3.Row]:
        """查询单条记录"""
        params = params or ()
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_scalar(self, query: str, params: Union[Tuple, List, None] = None) -> Any:
        """查询单个值（如 COUNT、MAX 等）"""
        row = self.fetchone(query, params)
        return row[0] if row else None

    def last_insert_id(self) -> int:
        """获取最后插入的行ID"""
        return self.fetch_scalar("SELECT last_insert_rowid()")

    def close(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self.local, "conn"):
            self.local.conn.close()
            del self.local.conn

    def close_all(self):
        """强制关闭所有连接（程序退出时使用）"""
        # 通常在主线程调用
        if hasattr(self.local, "conn"):
            self.close()

class InventoryManager:
    def __init__(self, db: Database):
        self.db = db

    # ------------------ 查询库存 ------------------
    def get_quantity(self, warehouse_id: int, material_id: int, model: str = "") -> float:
        row = self.db.fetchone("""
            SELECT quantity FROM inventory
            WHERE warehouse_id = ? AND material_id = ? AND model = ?
        """, (warehouse_id, material_id, model))
        return row["quantity"] if row else 0.0

    def list_inventory(self, warehouse_id: Optional[int] = None) -> list:
        """返回仓库库存列表"""
        sql = "SELECT * FROM inventory"
        params = ()
        if warehouse_id is not None:
            sql += " WHERE warehouse_id = ?"
            params = (warehouse_id,)
        return self.db.fetchall(sql, params)

    # ------------------ 修改库存 ------------------
    def add_stock(self, warehouse_id: int, material_id: int, model: str, quantity: float):
        """增加库存（支持新增记录）"""
        self.db.execute("""
            INSERT INTO inventory (warehouse_id, material_id, model, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(warehouse_id, material_id, model) DO UPDATE SET
                quantity = quantity + excluded.quantity
        """, (warehouse_id, material_id, model, quantity))

    def remove_stock(self, warehouse_id: int, material_id: int, model: str, quantity: float):
        """减少库存，如果库存不足则抛出异常"""
        current_qty = self.get_quantity(warehouse_id, material_id, model)
        if current_qty < quantity:
            raise ValueError(f"库存不足：当前 {current_qty}, 尝试减少 {quantity}")
        self.db.execute("""
            UPDATE inventory SET quantity = quantity - ?
            WHERE warehouse_id = ? AND material_id = ? AND model = ?
        """, (quantity, warehouse_id, material_id, model))

    # ------------------ 批量库存变动 ------------------
    def batch_update(self, updates: list[dict]):
        """
        批量更新库存
        updates: [
            {"warehouse_id":1, "material_id":2, "model":"A", "delta":10},
            {"warehouse_id":1, "material_id":3, "model":"", "delta":-5},
        ]
        delta>0 增加库存, delta<0 减少库存
        """
        for item in updates:
            wid = item["warehouse_id"]
            mid = item["material_id"]
            model = item.get("model", "")
            delta = item["delta"]
            if delta >= 0:
                self.add_stock(wid, mid, model, delta)
            else:
                self.remove_stock(wid, mid, model, -delta)
