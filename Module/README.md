# 上位机数据查看器模块说明

本文档说明如何使用新创建的两个数据查看器模块。

## 📋 模块列表

### 1. 电量数据查看器 (excel_data_viewer)
用于查看和分析从下位机上传的电量数据 Excel 文件。

**功能特性：**
- ✅ 实时接收服务端推送的电量数据通知
- ✅ 自动解析 Excel 文件（支持多 sheet，每个 sheet 代表不同设备）
- ✅ 以表格形式展示三相电压、电流等数据
- ✅ 生成条形统计图（电压、电流对比）
- ✅ 历史数据查询（折线图和条形图）
- ✅ 设备筛选和日期范围筛选

**选项卡：**
1. **实时数据** - 显示最新收到的数据和条形图
2. **历史数据** - 查看历史趋势（折线图/条形图切换）

### 2. 几何量图片查看器 (image_data_viewer)
用于查看和识别从下位机上传的几何量图片数据。

**功能特性：**
- ✅ 实时接收服务端推送的图片数据通知
- ✅ 2列4行共8个显示区域
- ✅ 每个区域显示原图和识别图（左右对比）
- ✅ 预留图片识别算法接口
- ✅ 单张识别和批量识别功能
- ✅ 历史识别记录查询
- ✅ 历史图片详情查看

**选项卡：**
1. **实时识别** - 显示最新收到的图片并进行识别
2. **历史识别** - 查看所有历史识别记录

## 🔧 模块集成方法

### 方法1：自动加载（推荐）

如果项目有自动扫描 `Module` 文件夹的机制，模块会自动加载到主界面菜单中。

### 方法2：手动注册

在主程序中手动注册模块：

```python
# 在主程序初始化处
from Module.excel_data_viewer.main import ExcelDataViewerModule
from Module.image_data_viewer.main import ImageDataViewerModule

# 注册模块
modules = [
    ExcelDataViewerModule(),
    ImageDataViewerModule(),
]

# 添加到菜单
for module in modules:
    menu_info = module.get_menu_name()
    # 根据 menu_info['id'] 添加到对应菜单
    # 例如: menu_info = {"id": 1, "text": "数据监控"}
```

## 🔌 WebSocket 通知集成

### 连接 WebSocket 通知

修改 `Service/connect_server_service/index/Client_server.py` 中的 `on_ws_notification` 方法：

```python
def on_ws_notification(self, data: dict):
    """WebSocket 通知回调"""
    notification_type = data.get("type", "")
    
    if notification_type == "excel_upload":
        # 转发到电量数据查看器
        excel_viewer = self.get_excel_viewer_window()  # 获取窗口实例
        if excel_viewer:
            excel_viewer.update_data_signal.emit(data)
    
    elif notification_type == "image_upload":
        # 转发到图片数据查看器
        image_viewer = self.get_image_viewer_window()  # 获取窗口实例
        if image_viewer:
            image_viewer.update_data_signal.emit(data)
```

### 通知数据格式

**电量数据通知：**
```json
{
    "type": "excel_upload",
    "device_id": "123",
    "file_name": "20251211_094711_TA3310三相表数据.xlsx",
    "file_size": 12345,
    "timestamp": "2025-12-11T09:47:11"
}
```

**几何量图片通知：**
```json
{
    "type": "image_upload",
    "device_id": "123",
    "file_name": "20251211_100723_brightness_0.5.png",
    "file_size": 234567,
    "original_size": 300000,
    "compression_ratio": 22.1,
    "timestamp": "2025-12-11T10:07:23"
}
```

## 📝 使用流程

### 电量数据查看器使用流程

1. **启动程序** - 打开上位机主界面
2. **连接服务器** - 确保 WebSocket 连接正常
3. **打开查看器** - 从菜单选择"数据监控 -> 电量数据查看器"
4. **实时监控** - 当下位机上传数据时，查看器会自动收到通知
5. **查看数据** - 在"实时数据"选项卡查看最新数据和图表
6. **历史分析** - 在"历史数据"选项卡筛选日期查看趋势

### 几何量图片查看器使用流程

1. **启动程序** - 打开上位机主界面
2. **连接服务器** - 确保 WebSocket 连接正常
3. **打开查看器** - 从菜单选择"数据监控 -> 几何量图片查看器"
4. **实时监控** - 当下位机上传图片时，查看器会自动收到通知
5. **查看图片** - 图片会自动加载到8个显示区域
6. **执行识别** - 点击"批量识别"按钮对所有图片进行识别
7. **查看历史** - 在"历史识别"选项卡查看所有识别记录

## 🎨 图片识别算法接口

图片识别功能预留了接口，位于 `Module/image_data_viewer/service/image_recognition.py`。

### 当前实现（占位）

```python
def recognize_image(self, image_path: Path) -> Optional[Path]:
    """
    图片识别接口
    
    Args:
        image_path: 原始图片路径
        
    Returns:
        识别后的图片路径
    """
    # TODO: 实现实际的识别算法
    return image_path  # 暂时返回原图
```

### 集成识别算法

未来可以在此接口中集成实际的识别算法：

```python
def recognize_image(self, image_path: Path) -> Optional[Path]:
    """图片识别接口"""
    try:
        # 1. 读取图片
        image = cv2.imread(str(image_path))
        
        # 2. 预处理
        processed = self.preprocess_image(image)
        
        # 3. 执行识别（例如：表盘指针识别、数字识别等）
        result = self.detect_features(processed)
        
        # 4. 在图片上标注结果
        annotated = self.annotate_image(image, result)
        
        # 5. 保存识别后的图片
        output_path = image_path.parent / f"{image_path.stem}_recognized{image_path.suffix}"
        cv2.imwrite(str(output_path), annotated)
        
        return output_path
        
    except Exception as e:
        logger.error(f"识别失败: {e}")
        return None
```

## 📊 数据解析说明

### Excel 数据格式

电量数据 Excel 文件应遵循以下格式：
- 每个 Sheet 代表一个设备的数据
- 数据位置示例（可在代码中调整）：
  - A相电压: 第2行第2列
  - B相电压: 第3行第2列
  - C相电压: 第4行第2列
  - A相电流: 第5行第2列
  - B相电流: 第6行第2列
  - C相电流: 第7行第2列
  - 功率因数: 第8行第2列
  - 总电能: 第9行第2列

### 修改解析逻辑

如果实际 Excel 格式不同，可修改 `excel_viewer_window.py` 中的 `parse_sheet_data` 方法：

```python
def parse_sheet_data(self, sheet) -> dict:
    """解析 sheet 数据"""
    data = {}
    
    # 根据实际格式调整单元格位置
    data['voltage_a'] = sheet.cell(row=2, column=2).value or 0
    data['voltage_b'] = sheet.cell(row=3, column=2).value or 0
    # ... 其他字段
    
    return data
```

## 🔍 调试和测试

### 模拟数据测试

在开发阶段，可以使用模拟数据测试窗口功能：

```python
# 测试电量数据查看器
excel_viewer = ExcelDataViewerWindow()
excel_viewer.show()

# 模拟接收通知
test_data = {
    'type': 'excel_upload',
    'device_id': 'test_device',
    'file_name': 'test.xlsx',
    'timestamp': datetime.now().isoformat()
}
excel_viewer.update_data_signal.emit(test_data)
```

```python
# 测试几何量图片查看器
image_viewer = ImageDataViewerWindow()
image_viewer.show()

# 加载测试图片
test_images = [
    Path('test_images/img1.png'),
    Path('test_images/img2.png'),
    # ... 最多8张
]
image_viewer.load_images_batch(test_images, 'test_device')
```

## 📦 依赖项

确保已安装以下依赖（已包含在 requirements.txt 中）：

```txt
PyQt6>=6.6.0
matplotlib>=3.7.0
openpyxl>=3.1.0
Pillow>=10.0.0
loguru>=0.7.0
websockets>=10.0
```

## 🚀 后续优化建议

1. **从服务端下载文件** - 实现从服务端自动下载 Excel 和图片文件
2. **数据持久化** - 将历史数据保存到本地数据库
3. **导出功能** - 支持导出报表和图表
4. **实时更新** - 数据更新时自动刷新图表
5. **多设备对比** - 支持多个设备数据的横向对比
6. **告警功能** - 数据异常时自动告警
7. **图片缓存** - 优化图片加载性能
8. **识别算法** - 集成实际的图像识别算法

## 📞 技术支持

如有问题或建议，请联系开发团队。

