# Excel 和图片窗口修复总结

## 🎯 修复内容

### 1. **几何量图片窗口修复** ✅

#### 1.1 图片数量显示问题

**问题：** 窗口上的图片比收到的数量少

**原因分析：**
- 图片下载完成后没有保存到历史记录
- 历史记录选项卡无法显示图片

**修复方案：**

```python
def on_image_download_finished(self, file_path: str, device_id: str):
    """图片下载完成回调"""
    # ... 显示图片 ...
    
    # ✅ 保存到历史记录
    record = {
        'device_id': device_id,
        'file_name': Path(file_path).name,
        'original_path': file_path,
        'recognized_path': file_path,  # 识别后会更新
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    self.history_records.append(record)
    self.update_history_list()
```

**效果：**
- ✅ 每次收到新图片都会保存到历史记录
- ✅ 历史记录列表自动更新
- ✅ 可以追踪所有接收的图片

#### 1.2 历史记录选项卡图片显示

**问题：** 历史记录选项卡显示不了图片

**原因：** 字段名不匹配（代码使用 `file_path`，但保存的是 `original_path`）

**修复：**

```python
def on_history_item_clicked(self, item: QListWidgetItem):
    """历史记录项点击"""
    record = item.data(Qt.ItemDataRole.UserRole)
    
    # ✅ 使用正确的字段名
    original_path = record.get('original_path')
    recognized_path = record.get('recognized_path')
    
    # 加载原图
    if original_path and Path(original_path).exists():
        pixmap = QPixmap(str(original_path))
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.history_original_label.setPixmap(scaled_pixmap)
    
    # 加载识别图（当前使用原图）
    if recognized_path and Path(recognized_path).exists():
        # ... 加载识别图 ...
    else:
        # 识别图使用原图
        self.history_recognized_label.setPixmap(scaled_pixmap)
```

**效果：**
- ✅ 历史记录点击后能正确显示图片
- ✅ 同时显示原图和识别图
- ✅ 显示详细信息（设备、文件名、时间、路径）

---

### 2. **电量 Excel 数据窗口修复** ✅

#### 2.1 重写 Excel 解析逻辑

**需求：** 根据 `test/get_test.py` 中的逻辑解析 Excel 数据

**实现：**

##### 数据结构定义

```python
@dataclass
class xlsx_datas_device_item:
    """设备数据项"""
    name: str = ""
    data: list = field(default_factory=list)

@dataclass
class xlsx_datas_phase_item:
    """相位数据项（A相、B相、C相）"""
    name: str = ""
    data: list = field(default_factory=list)  # [xlsx_datas_device_item]

@dataclass
class xlsx_datas_item_x:
    """X轴数据"""
    name: list = field(default_factory=list)  # x轴数据项描述
    data: list = field(default_factory=list)  # x轴数据 [[相角, 电流], ...]

@dataclass
class xlsx_datas_item:
    """数据项"""
    x: xlsx_datas_item_x = field(default_factory=xlsx_datas_item_x)
    y: list = field(default_factory=list)  # [xlsx_datas_phase_item]

@dataclass
class xlsx_datas_type_item:
    """数据类型项（功率、电压、电流、相角）"""
    name: str = ""
    data: xlsx_datas_item = field(default_factory=xlsx_datas_item)

@dataclass
class xlsx_data:
    """Excel数据"""
    rated_voltage: float = 0
    rated_voltage_unit: str = ''
    rated_frequency: float = 0
    rated_frequency_unit: str = ''
    name: str = ""
    data: list = field(default_factory=list)  # [xlsx_datas_type_item]
```

##### 解析逻辑

```python
def parse_sheet_data_new(self, sheet) -> xlsx_data:
    """解析 sheet 数据（完全按照 test/get_test.py 的逻辑）"""
    
    # 1. 转换为 DataFrame
    data = pd.DataFrame(data_rows)
    data_clean = data.dropna()
    
    # 2. 提取额定电压和频率
    return_data.rated_frequency = float("".join(re.findall(r'[0-9.]+', str(...))))
    return_data.rated_voltage = float("".join(re.findall(r'[0-9.]+', str(...))))
    
    # 3. 解析四种数据类型（功率W、电压、电流、相角）
    data_each_counts = 36  # 每36行一个数据类型
    
    for row in range(data_clean.shape[0]):
        temp = row / data_each_counts
        index = math.floor(temp)
        
        # 根据 index 创建对应的数据类型
        if temp == 0:  # 功率W
            xlsx_datas_type_item_obj = xlsx_datas_type_item()
            xlsx_datas_type_item_obj.name = "功率W"
            # ... 收集X轴数据
        elif temp == 1:  # 电压
            # ...
        elif temp == 2:  # 电流
            # ...
        elif temp == 3:  # 相角
            # ...
    
    # 4. 设置Y轴数据（A相、B相、C相，每相多个设备）
    df_rows_2_4_unique = data.iloc[2, 4:].dropna()  # 相位列
    df_rows_3_4 = data.iloc[3, 4:]  # 设备列
    
    for row in range(data_clean.shape[0]):
        # 为每个数据类型的每个相位添加设备数据
        for j in range(df_rows_2_4_unique.shape[0]):
            xlsx_datas_phase_item_obj = xlsx_datas_phase_item()
            xlsx_datas_phase_item_obj.name = df_rows_2_4_unique.iloc[j]
            
            # 添加设备
            device_series = df_rows_3_4.drop_duplicates()[:-2]
            for device_row in range(device_series.shape[0]):
                xlsx_datas_device_item_obj = xlsx_datas_device_item()
                xlsx_datas_device_item_obj.name = device_series.iloc[device_row]
                xlsx_datas_phase_item_obj.data.append(xlsx_datas_device_item_obj)
    
    # 5. 设置Y的具体值
    for row in range(data_clean.shape[0]):
        # 填充每个设备的数据
        return_data.data[index].data.y[j].data[device_row].data.append(value)
    
    return return_data
```

**效果：**
- ✅ 提取额定电压和频率
- ✅ 解析四种数据类型（功率W、电压、电流、相角）
- ✅ 每种数据类型包含 A、B、C 三相数据
- ✅ 每相包含多个设备的数据
- ✅ X轴数据包含相角和电流

#### 2.2 重新实现条形图（类似 1.png 效果）

**需求：** 创建分组柱状图，显示多设备三相数据

**实现：**

```python
def draw_realtime_chart(self, excel_data_obj: xlsx_data):
    """绘制实时数据条形图（分组柱状图，类似 1.png）"""
    
    # 1. 获取当前数据类型（功率W、电压、电流、相角）
    data_type_item = excel_data_obj.data[data_type_index]
    
    # 2. 生成 X 轴标签（相角,电流）
    x_labels = [f"{x[0]},{x[1]}" for x in x_data]
    x_pos = np.arange(len(x_labels))
    
    # 3. 准备颜色（6种颜色对应6个柱子）
    colors = ['#4A90E2', '#7CB342', '#FF9800', '#E53935', '#9C27B0', '#00BCD4']
    
    # 4. 计算柱子数量和宽度
    num_bars = sum(len(phase.data) for phase in y_data_phases)
    bar_width = 0.8 / num_bars
    
    # 5. 绘制每个柱子
    bar_index = 0
    for phase_item in y_data_phases:
        for device_item in phase_item.data:
            # 计算柱子位置
            offset = (bar_index - num_bars / 2 + 0.5) * bar_width
            bar_positions = x_pos + offset
            
            # 绘制柱子
            ax.bar(bar_positions, values, bar_width, 
                  color=colors[bar_index % len(colors)],
                  label=f"{phase_name}{device_name}")
            
            bar_index += 1
    
    # 6. 设置图表
    ax.set_xlabel('相角/°,电流/A')
    ax.set_ylabel(data_type_item.name)
    ax.set_title(data_type_item.name)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=45)
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    
    # 7. 显示额定参数（左侧）
    info_text = f"电量数据:\n\n-电量配置-\n"
    info_text += f"额定电压\n{excel_data_obj.rated_voltage}{excel_data_obj.rated_voltage_unit}\n"
    info_text += f"额定功率\n{excel_data_obj.rated_frequency}{excel_data_obj.rated_frequency_unit}"
    ax.text(-0.15, 0.95, info_text, transform=ax.transAxes, ...)
    
    # 8. 显示数据类型标签页（顶部）
    data_types_text = "  ".join([f"{'【' if i == data_type_index else ''}{item.name}{'】'}"
                                 for i, item in enumerate(excel_data_obj.data)])
    ax.text(0.5, 1.05, data_types_text, transform=ax.transAxes, ...)
```

**图表效果：**

```
┌─────────────────────────────────────────────────────────────┐
│  电量数据:          功率W    【电压】   电流    相角      ← 标签页
│                                                             │
│  -电量配置-         ┌────────────────────────────────┐    │
│  额定电压           │         电压                     │    │
│  220.0V            │  ▌▌▌▌▌▌                        │    │
│  额定功率           │  ▌▌▌▌▌▌      ▌▌▌▌▌▌        │    │ ← 分组柱状图
│  53.0Hz            │  ▌▌▌▌▌▌      ▌▌▌▌▌▌        │    │
│                    │  ▌▌▌▌▌▌      ▌▌▌▌▌▌        │    │
│                    └────────────────────────────────┘    │
│                     0,0.5   60,0.5  300,0.5  ...          │
│                         相角/°,电流/A                      │
│                                                             │
│  图例: ■A相TK3330  ■A相TD3310R  ■B相TK3330  ...          │
└─────────────────────────────────────────────────────────────┘
```

**特点：**
- ✅ 左侧显示额定参数
- ✅ 顶部显示数据类型标签页
- ✅ X轴显示 "相角/°,电流/A"
- ✅ 每个X轴点有6个柱子（A相设备1、A相设备2、B相设备1、B相设备2、C相设备1、C相设备2）
- ✅ 不同柱子用不同颜色
- ✅ 图例显示所有设备
- ✅ 网格线辅助阅读

#### 2.3 历史记录数据同步

**问题：** 历史记录选项卡都是假数据

**修复：**

```python
def load_excel_file(self, file_path: str, device_id: str = ""):
    """加载 Excel 文件"""
    try:
        # ... 解析和显示 ...
        
        # ✅ 保存到历史记录
        self.save_to_history(file_path, device_id)
        
        logger.info(f"成功加载 Excel 文件: {file_path}")
    except Exception as e:
        logger.error(f"加载 Excel 文件失败: {e}")

def save_to_history(self, file_path: str, device_id: str):
    """保存到历史记录"""
    try:
        record = {
            'file_path': file_path,
            'device_id': device_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'file_name': Path(file_path).name
        }
        self.history_data.append(record)
        logger.info(f"已添加历史记录: {file_path}")
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")
```

**效果：**
- ✅ 每次加载 Excel 文件都会保存到历史记录
- ✅ 历史记录包含文件路径、设备ID、时间戳、文件名
- ✅ 历史记录选项卡可以查看和筛选历史数据

---

## 📊 数据流程

### 几何量图片窗口

```
1. 下位机上传图片
   ↓
2. 服务器发送 WebSocket 通知（包含 file_id）
   ↓
3. 上位机收到通知
   ├─ on_new_image_received(data)
   ├─ 创建下载线程
   └─ 下载图片到 data/image/{device_id}/
   ↓
4. 下载完成回调
   ├─ on_image_download_finished(file_path, device_id)
   ├─ 显示图片到窗口（自动识别）
   ├─ 保存到历史记录
   └─ 更新历史列表
   ↓
5. 用户可以在历史记录选项卡查看
```

### 电量 Excel 窗口

```
1. 下位机上传 Excel 文件
   ↓
2. 服务器发送 WebSocket 通知（包含 file_id）
   ↓
3. 上位机收到通知
   ├─ on_new_data_received(data)
   ├─ 创建下载线程
   └─ 下载文件到 data/excel/{device_id}/
   ↓
4. 下载完成回调
   ├─ on_download_finished(file_path, device_id)
   ├─ 解析 Excel 文件（parse_sheet_data_new）
   │  ├─ 提取额定参数
   │  ├─ 解析四种数据类型
   │  ├─ 提取 X 轴数据（相角、电流）
   │  ├─ 提取 Y 轴数据（A、B、C相，多设备）
   │  └─ 返回 xlsx_data 对象
   ├─ 绘制分组柱状图
   ├─ 保存到历史记录
   └─ 更新历史列表
   ↓
5. 用户可以在历史记录选项卡查看
```

---

## 🔍 数据结构对比

### 之前（简化结构）

```python
{
    'rated_voltage': 220.0,
    'data': {
        '电压': {'A相': [220.5, ...], 'B相': [221.0, ...], 'C相': [219.5, ...]}
    }
}
```

### 之后（完整结构）

```python
xlsx_data(
    rated_voltage=220.0,
    rated_voltage_unit='V',
    rated_frequency=50.0,
    rated_frequency_unit='Hz',
    data=[
        xlsx_datas_type_item(
            name="功率W",
            data=xlsx_datas_item(
                x=xlsx_datas_item_x(
                    name=["相角/°", "电流/A"],
                    data=[[0, 0.5], [60, 0.5], [300, 0.5], ...]
                ),
                y=[
                    xlsx_datas_phase_item(
                        name="A相",
                        data=[
                            xlsx_datas_device_item(name="TK3330", data=[150.2, 148.5, ...]),
                            xlsx_datas_device_item(name="TD3310R", data=[152.1, 149.8, ...])
                        ]
                    ),
                    xlsx_datas_phase_item(
                        name="B相",
                        data=[
                            xlsx_datas_device_item(name="TK3330", data=[151.0, ...]),
                            xlsx_datas_device_item(name="TD3310R", data=[153.2, ...])
                        ]
                    ),
                    # ... C相
                ]
            )
        ),
        # ... 电压、电流、相角
    ]
)
```

---

## ✅ 功能清单

### 几何量图片窗口

- ✅ 自动下载并显示图片
- ✅ 自动识别（当前返回原图）
- ✅ 显示文件名
- ✅ 动态扩展显示区域（>8张图片时）
- ✅ 保存到历史记录
- ✅ 历史记录选项卡正确显示图片
- ✅ 历史记录包含原图和识别图
- ✅ 详细的信息显示

### 电量 Excel 窗口

- ✅ 自动下载并解析 Excel 文件
- ✅ 提取额定电压和频率
- ✅ 解析四种数据类型（功率W、电压、电流、相角）
- ✅ 解析 A、B、C 三相数据
- ✅ 解析多设备数据
- ✅ 绘制分组柱状图（类似 1.png）
- ✅ 显示额定参数（左侧）
- ✅ 显示数据类型标签页（顶部）
- ✅ X 轴显示相角和电流
- ✅ 每个X轴点显示多个柱子
- ✅ 不同柱子用不同颜色
- ✅ 图例显示所有设备
- ✅ 保存到历史记录
- ✅ 历史记录选项卡可查看历史数据

---

## 🧪 测试建议

### 几何量图片窗口测试

1. **单张图片上传**
   - 上传 1 张图片
   - 检查窗口显示
   - 检查历史记录

2. **多张图片上传**
   - 上传 5 张图片
   - 检查窗口显示（8个区域）
   - 上传 12 张图片
   - 检查动态扩展（12个区域）
   - 清空后检查收缩（8个区域）

3. **历史记录测试**
   - 上传多张图片
   - 打开历史记录选项卡
   - 点击记录查看图片
   - 检查原图和识别图显示

### 电量 Excel 窗口测试

1. **Excel 文件上传**
   - 上传符合格式的 Excel 文件
   - 检查解析是否成功
   - 检查额定参数显示

2. **条形图显示**
   - 检查分组柱状图是否正确
   - 检查 X 轴标签（相角,电流）
   - 检查柱子数量（A相设备1、A相设备2、B相设备1、B相设备2、C相设备1、C相设备2）
   - 检查颜色区分
   - 检查图例

3. **数据类型切换**
   - 查看功率W数据
   - 查看电压数据
   - 查看电流数据
   - 查看相角数据

4. **历史记录测试**
   - 上传多个 Excel 文件
   - 打开历史记录选项卡
   - 查看历史记录列表
   - 选择历史记录查看数据

---

## ⚠️ 注意事项

### Excel 文件格式要求

1. **文件名格式：** `20251211_111324_TA3310三相表数据.xlsx`

2. **数据格式：**
   - 第1行：额定电压和电流（如：`220V, 5A`）
   - 第2行：额定频率（如：`50Hz`）
   - 第3行：列标题（相角/°、电流/A、A相、B相、C相）
   - 第4行：设备名称
   - 第5行开始：数据（每36行一个数据类型）

3. **数据类型顺序：**
   - 第1-36行：功率W数据
   - 第37-72行：电压数据
   - 第73-108行：电流数据
   - 第109-144行：相角数据

### 图片文件格式

- 支持：PNG、JPG、JPEG
- 文件名应包含描述信息（如：`brightness_0.5.png`）

---

## 🚀 后续优化建议

### 1. 数据类型切换

当前只显示第一个数据类型（功率W），可以添加按钮或下拉框切换：

```python
# 添加数据类型选择器
self.data_type_combo = QComboBox()
self.data_type_combo.addItems(["功率W", "电压", "电流", "相角"])
self.data_type_combo.currentIndexChanged.connect(self.on_data_type_changed)

def on_data_type_changed(self, index):
    self.current_data_type_index = index
    # 重新绘制图表
    self.draw_realtime_chart(self.current_excel_data)
```

### 2. 图表交互

添加鼠标悬停显示具体数值：

```python
from matplotlib.widgets import Cursor
# 添加十字光标
cursor = Cursor(ax, useblit=True, color='red', linewidth=1)
```

### 3. 数据导出

添加导出功能，将图表导出为图片：

```python
def export_chart(self):
    file_path, _ = QFileDialog.getSaveFileName(self, "保存图表", "", "PNG (*.png);;PDF (*.pdf)")
    if file_path:
        self.realtime_figure.savefig(file_path, dpi=300, bbox_inches='tight')
```

### 4. 历史数据对比

在历史记录选项卡中添加对比功能：

```python
# 选择多个历史记录进行对比
def compare_history_data(self, record_ids):
    # 在同一图表中显示多条数据
    pass
```

---

✅ 所有修复和优化已完成！

