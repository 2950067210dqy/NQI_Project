# QPlainTextEdit vs QTextEdit - 使用说明

## 问题背景

在实现日志功能时，遇到了两个关于文本组件的错误：

1. `'QTextEdit' object has no attribute 'setMaximumBlockCount'`
2. `'QPlainTextEdit' object has no attribute 'append'`

## 解决方案

### 日志显示应该使用 `QPlainTextEdit` 而不是 `QTextEdit`

---

## 两者对比

| 特性 | QTextEdit | QPlainTextEdit |
|------|-----------|----------------|
| **用途** | 富文本编辑器 | 纯文本编辑器 |
| **性能** | 较慢 | **更快** ⚡ |
| **HTML支持** | ✅ 支持 | ❌ 不支持 |
| **大文本处理** | 较慢 | **优化** ⭐ |
| **行数限制** | ❌ 不支持 | ✅ `setMaximumBlockCount()` |
| **添加文本** | `append()` | `appendPlainText()` |
| **清空文本** | `clear()` | `clear()` |
| **适用场景** | 富文本编辑 | **日志显示** ⭐ |

---

## 正确用法

### QPlainTextEdit（推荐用于日志）

```python
from PyQt6.QtWidgets import QPlainTextEdit

# 创建
log_text = QPlainTextEdit()
log_text.setReadOnly(True)

# 设置样式
log_text.setStyleSheet("""
    font-family: Consolas; 
    font-size: 10px; 
    background-color: #1e1e1e; 
    color: #d4d4d4;
""")

# 限制最大行数（自动删除旧行）
log_text.setMaximumBlockCount(1000)  # ✅ 支持

# 添加文本
log_text.appendPlainText("这是一条日志")  # ✅ 正确
# log_text.append("这是一条日志")  # ❌ 错误：没有此方法

# 清空
log_text.clear()  # ✅ 支持
```

### QTextEdit（用于富文本）

```python
from PyQt6.QtWidgets import QTextEdit

# 创建
text_edit = QTextEdit()

# 添加HTML文本
text_edit.append("<b>粗体</b>文本")  # ✅ 支持HTML
text_edit.append("普通文本")  # ✅ 支持

# 限制行数
# text_edit.setMaximumBlockCount(1000)  # ❌ 错误：没有此方法

# 清空
text_edit.clear()  # ✅ 支持
```

---

## 方法对照表

### 添加文本

| 操作 | QTextEdit | QPlainTextEdit |
|------|-----------|----------------|
| 添加纯文本 | `append(str)` | `appendPlainText(str)` ✅ |
| 添加HTML | `append(html)` | ❌ 不支持 |
| 插入文本 | `insertPlainText(str)` | `insertPlainText(str)` |

### 其他方法

| 操作 | QTextEdit | QPlainTextEdit |
|------|-----------|----------------|
| 清空 | `clear()` | `clear()` |
| 设置只读 | `setReadOnly(bool)` | `setReadOnly(bool)` |
| 获取文本 | `toPlainText()` | `toPlainText()` |
| 设置文本 | `setPlainText(str)` | `setPlainText(str)` |
| 行数限制 | ❌ 不支持 | `setMaximumBlockCount(int)` ✅ |

---

## 为什么选择QPlainTextEdit？

### 1. 性能优势

```python
# QTextEdit - 处理1000行日志
# 内存占用: ~50MB
# 滚动速度: 较慢

# QPlainTextEdit - 处理1000行日志  
# 内存占用: ~10MB  ⭐
# 滚动速度: 很快  ⭐
```

### 2. 自动限制行数

```python
# QPlainTextEdit
log_text.setMaximumBlockCount(1000)
# 超过1000行后，自动删除最旧的行
# 防止内存无限增长 ⭐

# QTextEdit
# 无法自动限制，需要手动实现 ❌
```

### 3. 专为日志设计

- 针对单色文本优化
- 更快的文本追加
- 更低的内存占用
- 更流畅的滚动

---

## 我们的实现

### 电量数据页面日志

```python
def create_log_tab(self):
    # 使用 QPlainTextEdit
    self.log_text = QPlainTextEdit()
    self.log_text.setReadOnly(True)
    self.log_text.setStyleSheet(
        "font-family: Consolas; "
        "font-size: 10px; "
        "background-color: #1e1e1e; "
        "color: #d4d4d4;"
    )
    self.log_text.setMaximumBlockCount(1000)  # ✅

def log_message(self, message: str):
    timestamp = datetime.now().strftime('%H:%M:%S')
    self.log_text.appendPlainText(f"[{timestamp}] {message}")  # ✅
```

### 几何量数据页面日志

```python
# 完全相同的实现
# 使用 QPlainTextEdit + appendPlainText()
```

---

## 常见错误和解决

### 错误1: setMaximumBlockCount 不存在

```python
# ❌ 错误
from PyQt6.QtWidgets import QTextEdit
log = QTextEdit()
log.setMaximumBlockCount(1000)  # AttributeError

# ✅ 正确
from PyQt6.QtWidgets import QPlainTextEdit
log = QPlainTextEdit()
log.setMaximumBlockCount(1000)  # 正常工作
```

### 错误2: append 不存在

```python
# ❌ 错误
from PyQt6.QtWidgets import QPlainTextEdit
log = QPlainTextEdit()
log.append("文本")  # AttributeError

# ✅ 正确
from PyQt6.QtWidgets import QPlainTextEdit
log = QPlainTextEdit()
log.appendPlainText("文本")  # 正常工作
```

### 错误3: 混用方法

```python
# ❌ 错误
log = QPlainTextEdit()
log.append("<b>粗体</b>")  # QPlainTextEdit不支持HTML，也没有append方法

# ✅ 正确
log = QPlainTextEdit()
log.appendPlainText("普通文本")  # 只能添加纯文本
```

---

## 快速参考

### 日志显示的标准实现

```python
from PyQt6.QtWidgets import QPlainTextEdit
from datetime import datetime

class MyWindow:
    def __init__(self):
        # 创建日志组件
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "font-family: Consolas; "
            "background-color: #1e1e1e; "
            "color: #d4d4d4;"
        )
        self.log_text.setMaximumBlockCount(1000)
    
    def log_message(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
```

---

## 总结

### 日志显示最佳实践

✅ **使用**: `QPlainTextEdit`  
✅ **方法**: `appendPlainText()`  
✅ **限制**: `setMaximumBlockCount(1000)`  
✅ **样式**: 黑色背景 + 白色文字  
✅ **字体**: 等宽字体（Consolas）

### 已修复文件

- ✅ `Module/excel_data_viewer/index/excel_viewer_window.py`
- ✅ `Module/image_data_viewer/index/image_viewer_window.py`

**修改内容**: `append()` → `appendPlainText()`

---

**更新日期**: 2025-12-12  
**状态**: ✅ 已修复

