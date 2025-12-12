# SQLite缓存功能实现说明

## 功能概述

为上位机的电量数据页面和几何量数据页面添加了SQLite缓存功能，实现以下特性：

1. **历史记录持久化**：所有数据记录保存到SQLite数据库
2. **离线缓存**：窗口隐藏/关闭时，新数据直接存入缓存
3. **自动恢复**：打开页面时自动加载最新缓存数据作为实时记录
4. **历史查询**：支持按设备、日期筛选历史记录

## 实现架构

### 1. 缓存管理器 (`cache_manager.py`)

位置：`Module/service/cache_manager.py`

#### 数据库结构

**电量数据表** (`excel_records`)：
```sql
CREATE TABLE excel_records (
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
    extra_data TEXT,  -- JSON格式的额外数据
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

**几何量数据表** (`image_records`)：
```sql
CREATE TABLE image_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    recognized_path TEXT,
    timestamp TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    extra_data TEXT,  -- JSON格式的额外数据
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

#### 核心方法

**电量数据操作**：
- `save_excel_record(record)` - 保存记录
- `get_latest_excel_record(device_id)` - 获取最新记录
- `get_excel_records(device_id, start_date, end_date, limit)` - 查询记录列表
- `get_excel_devices()` - 获取所有设备ID

**几何量数据操作**：
- `save_image_record(record)` - 保存记录
- `get_latest_image_records(device_id, limit)` - 获取最新N条记录
- `get_image_records(device_id, start_date, end_date, limit)` - 查询记录列表
- `get_image_devices()` - 获取所有设备ID

**通用操作**：
- `clear_old_records(days)` - 清理旧记录
- `get_statistics()` - 获取统计信息

### 2. 电量数据页面改动

文件：`Module/excel_data_viewer/index/excel_viewer_window.py`

#### 主要改动

1. **导入缓存管理器**

```python
from public.function.Cache.cache_manager import cache_manager
```

2. **添加窗口状态标志**
```python
self.is_visible = False  # 窗口是否可见
```

3. **窗口显示/隐藏事件处理**
```python
def showEvent(self, event):
    """窗口显示时加载最新缓存"""
    self.is_visible = True
    self.load_latest_from_cache()

def hideEvent(self, event):
    """窗口隐藏时标记状态"""
    self.is_visible = False
```

4. **新数据接收逻辑修改**
```python
def on_new_data_received(self, data: dict):
    # 窗口不可见时，直接保存到缓存
    if not self.is_visible or not self.isVisible():
        cache_record = {
            'device_id': device_id,
            'file_path': '',
            'file_name': file_name,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'extra_data': {
                'file_id': file_id,
                'pending_download': True
            }
        }
        cache_manager.save_excel_record(cache_record)
        return
    
    # 窗口可见时，正常下载并显示
    # ...
```

5. **保存历史到缓存**
```python
def save_history(self, file_path: str, device_id: str):
    # 保存到内存
    self.history_data.append(record)
    
    # 保存到缓存数据库
    cache_record = {
        'device_id': device_id,
        'file_path': file_path,
        'file_name': Path(file_path).name,
        'timestamp': record['timestamp'],
        'sheet_count': len(sheet_data_dict),
        'rated_voltage': first_sheet.rated_voltage,
        # ...
    }
    cache_manager.save_excel_record(cache_record)
```

6. **从缓存加载历史记录**
```python
def load_history_from_cache(self):
    """初始化时从缓存加载所有历史记录"""
    records = cache_manager.get_excel_records(limit=100)
    for record in records:
        if Path(record['file_path']).exists():
            self.history_data.append(history_item)
```

7. **从缓存加载最新数据**
```python
def load_latest_from_cache(self):
    """窗口显示时从缓存加载最新记录"""
    devices = cache_manager.get_excel_devices()
    for device_id in devices:
        latest_record = cache_manager.get_latest_excel_record(device_id)
        if latest_record and Path(latest_record['file_path']).exists():
            # 解析并显示数据
            sheet_data_dict = self.parse_excel_all_sheets(file_path)
            self.create_or_update_device_tab(device_id, sheet_data_dict)
```

### 3. 几何量数据页面改动

文件：`Module/image_data_viewer/index/image_viewer_window.py`

#### 主要改动

与电量数据页面类似，包括：

1. **导入缓存管理器**
2. **添加窗口状态标志**
3. **窗口显示/隐藏事件处理**
4. **新数据接收逻辑修改**（窗口不可见时保存到缓存）
5. **保存历史到缓存**
6. **从缓存加载历史记录**
7. **从缓存加载最新图片**（每个设备最多加载20张）

特殊之处：
```python
def load_latest_from_cache(self):
    """加载每个设备最新的20张图片"""
    for device_id in devices:
        latest_records = cache_manager.get_latest_image_records(
            device_id, 
            limit=self.max_widget_count  # 20
        )
        
        for record in reversed(latest_records):  # 从旧到新加载
            target_widget = self.get_next_widget_for_device(device_tab)
            target_widget.load_original_image(Path(original_path))
```

## 使用场景

### 场景1：正常使用（窗口可见）

1. 用户打开电量/几何量数据页面
2. 下位机发送新数据到服务器
3. 上位机收到通知，下载文件并显示
4. 数据保存到缓存数据库

**数据流向**：
```
下位机 → 服务器 → 上位机(下载) → 显示 → 缓存数据库
```

### 场景2：窗口隐藏/关闭时收到数据

1. 用户隐藏或关闭数据页面
2. 下位机发送新数据到服务器
3. 上位机收到通知，**直接保存到缓存数据库**（不下载文件）
4. 记录标记为 `pending_download: true`

**数据流向**：
```
下位机 → 服务器 → 上位机(通知) → 缓存数据库（待下载标记）
```

### 场景3：打开页面时恢复数据

1. 用户打开数据页面
2. 页面自动从缓存加载最新数据
3. 电量数据：加载每个设备的最新记录
4. 几何量数据：加载每个设备的最新20张图片

**数据流向**：
```
缓存数据库 → 读取 → 解析/加载 → 显示
```

### 场景4：查看历史记录

1. 用户切换到"历史数据"选项卡
2. 从缓存数据库查询历史记录
3. 支持按设备、日期筛选

**数据流向**：
```
缓存数据库 → 查询(device_id, date_range) → 列表显示 → 点击查看详情
```

## 缓存文件位置

```
NQI_Project/
├── cache/
│   ├── excel_data_cache.db    # 电量数据缓存
│   └── image_data_cache.db    # 几何量数据缓存
```

## 优势

1. **数据持久化**：重启程序后历史数据不丢失
2. **性能优化**：窗口不可见时不下载文件，减少网络流量
3. **离线支持**：即使服务器断开，历史数据仍可查看
4. **快速恢复**：打开页面时立即显示最新数据
5. **结构化存储**：SQLite支持复杂查询和索引

## 维护建议

### 定期清理旧数据

```python
# 清理30天前的记录
cache_manager.clear_old_records(days=30)
```

建议在程序启动时或定时执行。

### 查看缓存统计

```python
stats = cache_manager.get_statistics()
print(f"电量数据记录数: {stats['excel_count']}")
print(f"电量数据设备数: {stats['excel_devices']}")
print(f"图片数据记录数: {stats['image_count']}")
print(f"图片数据设备数: {stats['image_devices']}")
```

### 数据库备份

定期备份缓存数据库文件：
```bash
cp cache/excel_data_cache.db cache/excel_data_cache.db.backup
cp cache/image_data_cache.db cache/image_data_cache.db.backup
```

## 注意事项

1. **文件存在性检查**：从缓存加载时会检查文件是否存在，不存在则跳过
2. **线程安全**：缓存管理器使用SQLite，天然支持并发读写
3. **extra_data字段**：可以存储JSON格式的扩展信息
4. **pending_download标记**：窗口不可见时接收的数据标记为待下载，后续可以实现补下载功能

## 未来扩展

1. **补下载功能**：窗口打开时，检查 `pending_download` 标记，下载缺失的文件
2. **导出功能**：将缓存数据导出为Excel或CSV
3. **云同步**：将缓存数据同步到云端
4. **数据统计**：基于缓存数据生成统计报表

## 修改日期

2025-12-12

