"""
数据缓存管理器 - 使用SQLite存储历史记录
支持电量数据和几何量数据的缓存
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from loguru import logger


class DataCacheManager:
    """数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache"):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 电量数据数据库
        self.excel_db_path = self.cache_dir / "excel_data_cache.db"
        # 几何量数据数据库
        self.image_db_path = self.cache_dir / "image_data_cache.db"
        
        # 初始化数据库
        self._init_excel_database()
        self._init_image_database()
        
        logger.info(f"缓存管理器初始化完成，目录: {self.cache_dir}")
    
    def _init_excel_database(self):
        """初始化电量数据数据库"""
        conn = sqlite3.connect(str(self.excel_db_path))
        cursor = conn.cursor()
        
        # 创建电量数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS excel_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sheet_count INTEGER DEFAULT 0,
                rated_voltage REAL DEFAULT 0,
                rated_voltage_unit TEXT DEFAULT '',
                rated_frequency REAL DEFAULT 0,
                rated_frequency_unit TEXT DEFAULT '',
                extra_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_timestamp 
            ON excel_records(device_id, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.info("电量数据数据库初始化完成")
    
    def _init_image_database(self):
        """初始化几何量数据数据库"""
        conn = sqlite3.connect(str(self.image_db_path))
        cursor = conn.cursor()
        
        # 创建几何量数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                recognized_path TEXT,
                timestamp TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                extra_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_image_device_timestamp 
            ON image_records(device_id, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.info("几何量数据数据库初始化完成")
    
    # ==================== 电量数据相关操作 ====================
    
    def save_excel_record(self, record: Dict[str, Any]) -> bool:
        """
        保存电量数据记录
        
        Args:
            record: 记录字典，包含以下字段：
                - device_id: 设备ID
                - file_path: 文件路径
                - file_name: 文件名
                - timestamp: 时间戳
                - sheet_count: Sheet数量（可选）
                - rated_voltage: 额定电压（可选）
                - rated_voltage_unit: 额定电压单位（可选）
                - rated_frequency: 额定频率（可选）
                - rated_frequency_unit: 额定频率单位（可选）
                - extra_data: 额外数据（dict，可选）
        
        Returns:
            bool: 是否保存成功
        """
        try:
            conn = sqlite3.connect(str(self.excel_db_path))
            cursor = conn.cursor()
            
            extra_data = record.get('extra_data')
            if extra_data and isinstance(extra_data, dict):
                extra_data = json.dumps(extra_data, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO excel_records 
                (device_id, file_path, file_name, timestamp, sheet_count, 
                 rated_voltage, rated_voltage_unit, rated_frequency, rated_frequency_unit, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get('device_id', 'unknown'),
                record.get('file_path', ''),
                record.get('file_name', ''),
                record.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                record.get('sheet_count', 0),
                record.get('rated_voltage', 0),
                record.get('rated_voltage_unit', ''),
                record.get('rated_frequency', 0),
                record.get('rated_frequency_unit', ''),
                extra_data
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"保存电量数据记录成功: {record.get('file_name')}")
            return True
            
        except Exception as e:
            logger.error(f"保存电量数据记录失败: {e}")
            return False
    
    def get_latest_excel_record(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取最新的电量数据记录
        
        Args:
            device_id: 设备ID，如果为None则获取所有设备的最新记录
        
        Returns:
            Dict: 记录字典，如果没有记录则返回None
        """
        try:
            conn = sqlite3.connect(str(self.excel_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if device_id:
                cursor.execute("""
                    SELECT * FROM excel_records 
                    WHERE device_id = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1
                """, (device_id,))
            else:
                cursor.execute("""
                    SELECT * FROM excel_records 
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1
                """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                record = dict(row)
                if record.get('extra_data'):
                    try:
                        record['extra_data'] = json.loads(record['extra_data'])
                    except:
                        pass
                return record
            
            return None
            
        except Exception as e:
            logger.error(f"获取最新电量数据记录失败: {e}")
            return None
    
    def get_excel_records(self, device_id: Optional[str] = None, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取电量数据记录列表
        
        Args:
            device_id: 设备ID筛选
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回记录数量限制
        
        Returns:
            List[Dict]: 记录列表
        """
        try:
            conn = sqlite3.connect(str(self.excel_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM excel_records WHERE 1=1"
            params = []
            
            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date + " 23:59:59")
            
            query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            records = []
            for row in rows:
                record = dict(row)
                if record.get('extra_data'):
                    try:
                        record['extra_data'] = json.loads(record['extra_data'])
                    except:
                        pass
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"获取电量数据记录列表失败: {e}")
            return []
    
    def get_excel_devices(self) -> List[str]:
        """获取所有电量数据设备ID列表"""
        try:
            conn = sqlite3.connect(str(self.excel_db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT device_id FROM excel_records 
                ORDER BY device_id
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
            
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []
    
    # ==================== 几何量数据相关操作 ====================
    
    def save_image_record(self, record: Dict[str, Any]) -> bool:
        """
        保存几何量数据记录
        
        Args:
            record: 记录字典，包含以下字段：
                - device_id: 设备ID
                - file_path: 文件路径
                - file_name: 文件名
                - original_path: 原图路径
                - recognized_path: 识别图路径（可选）
                - timestamp: 时间戳
                - file_size: 文件大小（可选）
                - extra_data: 额外数据（dict，可选）
        
        Returns:
            bool: 是否保存成功
        """
        try:
            conn = sqlite3.connect(str(self.image_db_path))
            cursor = conn.cursor()
            
            extra_data = record.get('extra_data')
            if extra_data and isinstance(extra_data, dict):
                extra_data = json.dumps(extra_data, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO image_records 
                (device_id, file_path, file_name, original_path, recognized_path, 
                 timestamp, file_size, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get('device_id', 'unknown'),
                record.get('file_path', ''),
                record.get('file_name', ''),
                record.get('original_path', ''),
                record.get('recognized_path', ''),
                record.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                record.get('file_size', 0),
                extra_data
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"保存几何量数据记录成功: {record.get('file_name')}")
            return True
            
        except Exception as e:
            logger.error(f"保存几何量数据记录失败: {e}")
            return False
    
    def get_latest_image_records(self, device_id: Optional[str] = None, 
                                limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最新的几何量数据记录列表
        
        Args:
            device_id: 设备ID，如果为None则获取所有设备
            limit: 返回记录数量限制
        
        Returns:
            List[Dict]: 记录列表
        """
        try:
            conn = sqlite3.connect(str(self.image_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if device_id:
                cursor.execute("""
                    SELECT * FROM image_records 
                    WHERE device_id = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                """, (device_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM image_records 
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            records = []
            for row in rows:
                record = dict(row)
                if record.get('extra_data'):
                    try:
                        record['extra_data'] = json.loads(record['extra_data'])
                    except:
                        pass
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"获取最新几何量数据记录失败: {e}")
            return []
    
    def get_image_records(self, device_id: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取几何量数据记录列表
        
        Args:
            device_id: 设备ID筛选
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回记录数量限制
        
        Returns:
            List[Dict]: 记录列表
        """
        try:
            conn = sqlite3.connect(str(self.image_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM image_records WHERE 1=1"
            params = []
            
            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date + " 23:59:59")
            
            query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            records = []
            for row in rows:
                record = dict(row)
                if record.get('extra_data'):
                    try:
                        record['extra_data'] = json.loads(record['extra_data'])
                    except:
                        pass
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"获取几何量数据记录列表失败: {e}")
            return []
    
    def get_image_devices(self) -> List[str]:
        """获取所有几何量数据设备ID列表"""
        try:
            conn = sqlite3.connect(str(self.image_db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT device_id FROM image_records 
                ORDER BY device_id
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
            
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []
    
    # ==================== 通用操作 ====================
    
    def clear_old_records(self, days: int = 30):
        """
        清理旧记录
        
        Args:
            days: 保留最近多少天的记录
        """
        try:
            from datetime import timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # 清理电量数据
            conn = sqlite3.connect(str(self.excel_db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM excel_records WHERE timestamp < ?", (cutoff_date,))
            excel_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            # 清理几何量数据
            conn = sqlite3.connect(str(self.image_db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_records WHERE timestamp < ?", (cutoff_date,))
            image_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"清理旧记录完成: 电量数据{excel_deleted}条, 几何量数据{image_deleted}条")
            
        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            stats = {}
            
            # 电量数据统计
            conn = sqlite3.connect(str(self.excel_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM excel_records")
            stats['excel_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT device_id) FROM excel_records")
            stats['excel_devices'] = cursor.fetchone()[0]
            conn.close()
            
            # 几何量数据统计
            conn = sqlite3.connect(str(self.image_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM image_records")
            stats['image_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT device_id) FROM image_records")
            stats['image_devices'] = cursor.fetchone()[0]
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


# 全局缓存管理器实例
cache_manager = DataCacheManager()

