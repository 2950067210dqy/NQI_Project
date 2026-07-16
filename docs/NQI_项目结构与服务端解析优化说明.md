# NQI 项目结构与服务端解析优化说明

## 1. 本轮工作范围
- 只在以下三个项目目录内进行了读取与修改：
  - `D:\WorkSpace\NQI_Project_Server`
  - `D:\WorkSpace\NQI_Project`
  - `D:\WorkSpace\NQI_Project_lower_client`
- 未对 `D:\WorkSpace` 下其他项目目录做读写、构建或测试操作。

## 2. 三个项目的结构与职责

### 2.1 服务端 `NQI_Project_Server`
- `main.py`
  - FastAPI 入口。
  - 负责设备注册/认证、文件上传、数据查询、下载、通知、故障与统计接口。
- `app/`
  - `database.py`：数据库模型、会话、初始化。
  - `feature_routes.py`：扩展接口路由。
  - `feature_services.py`：搜索索引、故障同步、预警规则计算、通知入库等业务逻辑。
  - `server_processing_runtime.py`：服务端后台解析运行时。
    - 维护两个后台线程：Excel 解析线程、图片分析线程。
    - 轮询 `processing_status = pending` 的记录。
    - 解析后写入解析结果表/分析结果表，并同步搜索索引、故障、通知。
  - `data_processing.py`：Excel 解析与图片分析的具体实现。
- `uploads/`
  - 服务端接收下位机上传后的原始文件存储目录。

### 2.2 上位机 `NQI_Project`
- `Service/`
  - 连接服务端、长轮询、API 客户端、主 GUI 进程入口。
- `Module/`
  - `excel_data_viewer/`：电量数据查看。
  - `image_data_viewer/`：几何量图片查看。
  - 其他模块负责搜索、报警预警、注册审批等业务页面。
- `index/`
  - 主窗口、模块装载与菜单组织。
- `public/`
  - 通用线程、缓存、队列、日志、配置等基础能力。

### 2.3 下位机 `NQI_Project_lower_client`
- `api/`
  - 向服务端注册、认证、上传数据、长轮询获取状态。
- `index/`
  - 下位机主界面与交互入口。
- `config/`
  - 服务地址、设备配置等。
- `security/`
  - 硬件密钥、注册安全逻辑。
- `meter_data_cache/`
  - 下位机本地缓存与上传中转数据。
- `static/`
  - 资源文件。

## 3. 本轮已完成的关键优化

### 3.1 服务端真正启动后台解析线程
已修改文件：`D:\WorkSpace\NQI_Project_Server\main.py`
- 在服务启动时调用 `start_processing_workers()`。
- 在服务关闭时调用 `stop_processing_workers()`。
- 显式导入 `serialize_excel_record` / `serialize_image_record`，保证电量与图片查询接口直接返回服务端解析结果。

### 3.2 服务端解析链路的运行逻辑
当前逻辑如下：
1. 下位机上传 Excel 或图片到服务端。
2. 服务端先把原始文件落盘到 `uploads/`，同时在原始数据表中插入一条记录，状态为 `pending`。
3. `server_processing_runtime.py` 中的两个后台线程持续轮询：
   - Excel 线程处理 `MeterExcelData.processing_status = pending`
   - 图片线程处理 `MeterImageData.processing_status = pending`
4. 线程取到待处理记录后：
   - 状态先改成 `processing`
   - Excel 走 `parse_excel_file(...)`
   - 图片走 `analyze_image_file(...)`
5. 解析/分析成功后：
   - 写入解析结果表 / 图片分析结果表
   - 原始记录状态更新为 `done`
   - 生成搜索索引
   - 同步故障记录
   - 触发预警通知并写入数据库
6. 如果处理失败：
   - 原始记录状态更新为 `failed`
   - 写入错误原因
   - 同步故障记录与预警通知

## 4. 上位机电量数据页面现在的逻辑
已修改文件：`D:\WorkSpace\NQI_Project\Module\excel_data_viewer\index\excel_viewer_window.py`

### 4.1 当前页面行为
- 页面显示后，不再从本地缓存恢复数据。
- 改为直接调用服务端接口：
  - 列表：`/api/data/excel`
  - 详情：`/api/data/excel/{file_id}`
  - 下载：`/api/file/download/excel/{file_id}`
- “服务器数据”页签显示服务端记录，不再显示缓存记录。
- “查看”按钮直接读取服务端解析后的 `parsed_data` 并刷新实时图表。
- “下载”按钮把源 Excel 下载到本机 `Downloads\NQI\excel`。
- 历史记录与趋势图都改为基于服务端解析结果生成。

### 4.2 电量页内部逻辑
1. 页面可见后后台触发 `bootstrap_cache_load()`，但实际执行的是服务端拉取。
2. 拉取最新记录列表，按设备选取最新且优先 `done` 的记录。
3. 详情接口返回 `parse_result.parsed_data`。
4. 上位机只负责把 `parsed_data` 反序列化成页面原有图表结构，不再解析 Excel 文件本身。
5. 趋势图从服务端历史记录中读取解析结果后再计算均值曲线。

## 5. 上位机几何量图片页面现在的逻辑
已修改文件：`D:\WorkSpace\NQI_Project\Module\image_data_viewer\index\image_viewer_window.py`

### 5.1 当前页面行为
- 页面显示后，直接读取服务端图片分析结果，不再依赖上位机本地缓存判断。
- 改为直接调用服务端接口：
  - 列表：`/api/data/image`
  - 详情：`/api/data/image/{file_id}`
  - 下载：`/api/file/download/image/{file_id}`
- “服务器数据”页签显示服务端图片记录。
- “查看”按钮显示服务端分析结果、原图路径、识别图路径、识别结论。
- “下载”按钮把原始图片下载到本机 `Downloads\NQI\image`。
- 实时页优先显示服务端已分析完成的最新图片结果。

### 5.2 图片页内部逻辑
1. 页面可见后触发服务端数据后台加载。
2. 按设备取最新图片记录。
3. 若状态为 `done`，直接用服务端返回的 `analysis_result` 刷新实时区域。
4. 历史页筛选条件改为基于服务端数据源，而不是缓存文件。
5. 历史详情显示服务端的：
   - 原图路径
   - 识别图路径
   - 是否故障
   - 分析摘要
   - 处理状态

## 6. 本轮修改带来的直接收益
- 服务端“等待后台分析”现在对应真实后台线程，不再只是界面提示。
- 上位机电量页不再重复解析 Excel，减少卡顿与重复计算。
- 上位机几何量页不再本地随机判断识别结果，改为读取服务端统一分析结论。
- 电量与图片两个查看页都支持从服务端记录直接下载源数据。
- 查询页、历史页、实时页的数据口径与数据库保持一致，避免“缓存和数据库不一致”。

## 7. 本轮验证结果
已完成语法编译检查：
- `D:\WorkSpace\NQI_Project_Server\main.py`
- `D:\WorkSpace\NQI_Project\Module\excel_data_viewer\index\excel_viewer_window.py`
- `D:\WorkSpace\NQI_Project\Module\image_data_viewer\index\image_viewer_window.py`

## 8. 后续建议
- 下一步建议补一组接口级自动化测试：
  - 上传后状态从 `pending -> processing -> done/failed`
  - Excel 解析结果字段完整性
  - 图片分析结果字段完整性
  - 上位机列表页/详情页返回数据一致性
- 搜索准确率指标要做到千分之一以内时，建议把：
  - 时间
  - 地点
  - 设备编号
  - 故障标记
  - 数据类型
  都纳入统一搜索索引表与回归测试样例。