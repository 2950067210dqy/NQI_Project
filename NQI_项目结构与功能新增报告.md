# NQI 三项目结构分析与新增功能说明

## 1. 本轮工作边界

本轮只读写以下目录：

- `D:\WorkSpace\NQI_Project_Server`：服务器部署项目。
- `D:\WorkSpace\NQI_Project`：上位机程序。
- `D:\WorkSpace\NQI_Project_lower_client`：下位机程序。

已在 `D:\WorkSpace\AGENTS.md` 写入边界约束；`D:\BaiduSyncdisk\NQI\软件开发需求.docx` 与 `D:\BaiduSyncdisk\NQI\数据集` 仅作为只读需求和样例数据参考。

## 2. 需求文档红色未实现项

从 `软件开发需求.docx` 提取到的红色功能点为：

- 设备管理。
- 管理注册请求。
- 查看已注册的设备。
- 几何量数据下载。
- 电量数据下载。
- 故障信息反馈。
- 故障监测报警。
- 数据检索：按时间、地点、故障、设备编号检索目标数据集，并考虑自动化测试，目标检索错误率小于千分之一。

## 3. 服务器项目结构与逻辑

路径：`D:\WorkSpace\NQI_Project_Server`

主要模块：

- `main.py`：FastAPI 入口，负责设备注册/认证、数据上传、数据查询、文件下载、通知、统计、健康检查。
- `app/database.py`：SQLAlchemy ORM 模型和数据库会话，原有设备、电量文件、几何量图片、通知、统计表；本轮新增注册申请表、故障记录表、检索索引表。
- `app/websocket_manager.py`：历史 WebSocket 模块；当前服务器不支持 WebSocket，运行路径已改为 HTTP 长轮询，不再注册 `/ws` 路由。
- `app/security.py`：硬件密钥生成与校验。
- `app/config_ini.py`：读取 `config.ini` 中数据库、服务端口、上传目录、图片压缩等配置。
- `app/meter_utils.py`：Excel 解析和图片类型分类工具。
- `app/feature_services.py`：本轮新增，封装检索索引、故障判断、长轮询通知缓存等公共逻辑。
- `app/feature_routes.py`：本轮新增，封装长轮询、注册申请审批、故障反馈、统一检索 API。
- `scripts/search_accuracy_test.py`：本轮新增，检索误差率自动化测试脚本。

服务器核心流程：

1. 下位机注册或认证设备。
2. 下位机上传 Excel 电量数据或图片几何量数据。
3. 服务器保存文件到 `uploads/<device_id>/excel|image`，写入文件记录表。
4. 服务器写通知、更新统计，并通过 HTTP 长轮询通知上位机。
5. 上位机收到通知后自动下载文件到本地缓存。
6. 上位机电量/几何量查看模块从缓存读取并展示数据。

本轮新增服务器逻辑：

- 设备注册审批：硬件码未进入白名单时，`/api/device/register` 不再直接失败，而是生成 `device_registration_requests` 待审批记录。上位机可调用审批接口批准或驳回。
- HTTP 长轮询补齐：新增 `/api/polling/notifications` 和 `/api/polling/heartbeat`，并将三端运行路径固定为 HTTP 长轮询；服务器不再注册 WebSocket 路由，客户端不再启动 WebSocket 线程。
- 故障记录：上传时可传 `has_fault`；如果显式标故障，或文件名/描述命中故障关键字，会写入 `fault_records` 并发出 `fault_alarm` 通知。
- 统一检索索引：上传成功后写入 `data_search_index`，支持时间、地点、故障、设备编号、数据类型、关键字组合查询。
- 历史索引补齐：搜索前会为历史 Excel/Image 记录自动补齐检索索引，避免旧数据不可查。

新增服务器 API：

- `GET /api/polling/notifications`：上位机 HTTP 长轮询通知。
- `POST /api/polling/heartbeat`：下位机心跳保活。
- `GET /api/device/registration-requests`：查看注册申请。
- `POST /api/device/registration-requests/{request_id}/approve`：批准注册申请。
- `POST /api/device/registration-requests/{request_id}/reject`：驳回注册申请。
- `POST /api/faults/report`：手动提交故障反馈。
- `GET /api/faults`：查询故障记录。
- `GET /api/search/data`：统一数据集检索。

搜索参数：

- `data_type=excel|image`
- `device_id=E001` 或 `G001`
- `device_prefix=E` 或 `G`
- `location=北京|上海|长沙|苏州|深圳`
- `has_fault=true|false`
- `start_time=2026-01-01T00:00:00`
- `end_time=2026-01-02T00:00:00`
- `keyword=...`
- `limit`、`skip`

返回结果中的 `dataset` 就是检索目标数据集，每条记录含 `data_type`、`file_id`、`device_id`、`file_name`、`location`、`has_fault`、`fault_summary`、`occurred_at`、`download_url`。

## 4. 上位机项目结构与逻辑

路径：`D:\WorkSpace\NQI_Project`

主要模块：

- `main.py`：多进程/主程序入口，启动主 GUI、连接服务等进程。
- `Service/connect_server_service`：连接服务器的后台服务，负责上位机与服务器通信。
- `Service/connect_server_service/api/api_client.py`：上位机 HTTP API 客户端，本轮新增注册申请、审批、搜索、故障接口封装。
- `Service/connect_server_service/index/Client_server.py`：连接服务器并监听通知；本轮新增 `fault_alarm` 专门处理。
- `public/function/Cache/data_download_manager.py`：收到上传通知后自动下载 Excel 或图片，并写入本地 SQLite 缓存。
- `public/function/Cache/cache_manager.py`：维护电量数据缓存库和几何量数据缓存库。
- `Module/excel_data_viewer`：电量数据查看，读取缓存 Excel，解析 sheet、设备、相位、功率/电压/电流/相角并展示趋势。
- `Module/image_data_viewer`：几何量图片查看，读取缓存图片，显示原图/识别图/故障结果。
- `Module/experiment_setting`：实验配置页面。
- `ui`、`theme`、`public/component`：界面、主题、公共组件。

上位机逻辑：

1. `Client_server.connect_to_server()` 从配置读取服务器地址。
2. 创建 `UpperAPIClient` 并测试 `/api/devices/list`。
3. 设置下载管理器客户端和跨进程消息队列。
4. 默认启动 HTTP 长轮询，收到 `excel_upload` 或 `image_upload` 后交给下载管理器。
5. 下载管理器保存到 `data/excel` 或 `data/image`，并写入 SQLite 缓存。
6. 对应查看窗口通过队列消息刷新展示。

本轮新增上位机能力：

- `UpperAPIClient.search_data(**filters)`：调用统一检索接口。
- `UpperAPIClient.list_registration_requests()`：查看注册申请。
- `UpperAPIClient.approve_registration_request()` / `reject_registration_request()`：管理注册申请。
- `UpperAPIClient.list_faults()` / `report_fault()`：查询和反馈故障。
- `Client_server.on_notification()` 新增 `fault_alarm` 分支，报警会进入主窗口提示队列。

## 5. 下位机项目结构与逻辑

路径：`D:\WorkSpace\NQI_Project_lower_client`

主要模块：

- `main.py`：PyQt6 下位机 GUI，负责设备配置、注册、连接服务器、选择并上传电量/几何量文件。
- `api/api_client.py`：下位机 HTTP API 客户端，本轮新增上传元数据和故障反馈接口。
- `api/long_polling_client.py`：下位机 HTTP 心跳保活线程。
- `api/websocket_client.py`：历史 WebSocket 连接线程文件；当前主程序不再引用，设备在线状态改由 HTTP 长轮询维持。
- `metadata/meter_data.py`：识别 Excel 和图片文件类型，生成待上传数据对象。
- `security/hardware_key.py`：生成硬件密钥。
- `config/config.py`、`lower_config.ini`：服务器地址、设备 ID、上传路径、并发数等配置。

下位机逻辑：

1. 生成硬件密钥。
2. 提交设备注册或注册申请。
3. 认证成功后启动心跳线程，设备状态保持在线。
4. 用户选择 Excel 或图片文件。
5. 上传线程池并发上传文件。
6. 服务器保存数据，写入 HTTP 长轮询通知队列，上位机下一轮轮询收到通知后自动下载。

本轮新增下位机能力：

- `APIClient.upload_file()` 支持 `location` 和 `has_fault` 元数据，服务器会用它生成检索索引和故障记录。
- `APIClient.report_fault()` 支持下位机主动提交故障反馈。
- 注册按钮识别服务器返回的 `pending` 状态，提示“等待上位机审批”。

## 6. 新增功能运行逻辑

### 6.1 实时通知方式

当前版本不使用 WebSocket。服务器在上传、故障告警、注册申请等事件发生后，将事件写入内存长轮询通知队列；上位机通过 `/api/polling/notifications` 按 `client_id` 拉取新增事件，下位机通过 `/api/polling/heartbeat` 维持在线状态和接收注册审批状态。这样部署时只依赖普通 HTTP 接口，适配不支持 WebSocket 的服务器环境。

设备注册审批：

1. 下位机调用 `/api/device/register`。
2. 如果硬件码已经在 `hardware_key` 表中，服务器按原逻辑创建设备。
3. 如果硬件码未入白名单，服务器写入 `device_registration_requests`，状态为 `pending`。
4. 上位机调用 `list_registration_requests()` 查看申请。
5. 上位机调用 `approve_registration_request(request_id)` 后，服务器把硬件码写入白名单，并创建设备记录。
6. 下位机再次连接或认证即可正常上传数据。

数据上传与检索：

1. 下位机上传 Excel 或图片，可附带 `location` 和 `has_fault`。
2. 服务器保存文件和原始记录。
3. 服务器写 `data_search_index`：数据类型、文件 ID、设备 ID、地点、故障标记、时间、下载 URL。
4. 调用 `/api/search/data` 即可按时间、地点、故障、设备编号检索数据集。
5. 查询结果里的 `download_url` 可直接下载原始 Excel 或图片。

故障报警：

1. 上传时若 `has_fault=true`，或文件名/描述含“故障、异常、报警、fault、error、alarm、warning”等关键字，服务器创建 `fault_records`。
2. 服务器同时发出 `fault_alarm` 通知。
3. 上位机 `Client_server` 接收后写入主窗口提示队列。
4. 上位机也可以调用 `report_fault()` 手动补录故障。

检索误差率测试：

- 脚本路径：`D:\WorkSpace\NQI_Project_Server\scripts\search_accuracy_test.py`
- 默认生成 E001-E010、G001-G010，地点为北京/上海/长沙/苏州/深圳，构造 20000 条合成数据和随机查询。
- 本地模式验证检索谓词误差率，阈值默认 `0.001`。
- 带 `--base-url http://localhost:8000` 时，可对服务器接口返回结果做假阳性检查。

示例命令：

```bash
python scripts/search_accuracy_test.py --iterations 2000 --fixture-size 20000
python scripts/search_accuracy_test.py --base-url http://localhost:8000 --iterations 2000
```

## 7. 修改文件清单

服务器：

- `D:\WorkSpace\NQI_Project_Server\app\database.py`
- `D:\WorkSpace\NQI_Project_Server\app\feature_services.py`
- `D:\WorkSpace\NQI_Project_Server\app\feature_routes.py`
- `D:\WorkSpace\NQI_Project_Server\main.py`
- `D:\WorkSpace\NQI_Project_Server\scripts\search_accuracy_test.py`

上位机：

- `D:\WorkSpace\NQI_Project\Service\connect_server_service\api\api_client.py`
- `D:\WorkSpace\NQI_Project\Service\connect_server_service\index\Client_server.py`

下位机：

- `D:\WorkSpace\NQI_Project_lower_client\api\api_client.py`
- `D:\WorkSpace\NQI_Project_lower_client\main.py`

工作区边界文件：

- `D:\WorkSpace\AGENTS.md`

## 8. 验证情况

已完成：

- Python 编译检查通过：服务器新增模块和 `main.py`、上位机 API/连接模块、下位机 API/主程序均通过 `py_compile`。
- 本地检索误差率测试通过：通过 `runpy` 方式执行 `scripts/search_accuracy_test.py --iterations 2000 --fixture-size 20000`，输出 `local_error_rate=0.00000000`，满足小于千分之一的指标要求。
- 检索脚本已改为使用 Python 标准库完成接口模式请求，本地模式和接口模式都不额外依赖 `requests`。

未完成：

- 未启动真实 MySQL/FastAPI 服务做端到端接口验证。
- 直接用脚本路径加参数启动时，当前 Codex 终端偶发 `CryptUnprotectData failed: 2148073483`；已用 `runpy` 完成等价本地测试。

## 9. 注意事项

- `Base.metadata.create_all()` 能创建新表，但不会自动给旧表做复杂迁移；本轮新增的是新表，启动服务器后会自动创建。
- 当前地点默认策略：如果上传未传 `location`，服务器会根据 `device_id` 稳定映射到北京/上海/长沙/苏州/深圳之一，保证旧数据也能参与地点检索。
- 当前故障自动检测是轻量规则：显式 `has_fault` 优先，其次按文件名/描述关键字判断。后续可替换为真实模型或阈值算法。
## 9. 上位机界面补充

本次补齐 `NQI_Project` 的可视化入口，两个模块都会被主窗口的 `Module/*/main.py` 扫描机制自动加载到“数据监控”菜单下：

- `Module/data_search`：新增“数据检索”界面，支持关键词、数据类型、地点、设备编号、故障状态、时间范围和返回数量过滤，结果以数据集表格显示。
- `Module/fault_alarm`：新增“报警预警”界面，支持按设备和状态过滤报警，自动 15 秒刷新，并提供“确认处理”和“关闭报警”操作。
- `Service/connect_server_service/api/api_client.py`：新增 `update_fault_status()`，供报警界面更新报警状态。
- `NQI_Project_Server/app/feature_routes.py`：新增 `/api/faults/{fault_id}/status`，保存上位机确认/关闭报警的处理结果。
- `Module/notification_history`：新增“预警通知历史”界面，直接读取服务器 `notifications` 表中的 `fault_alarm` 记录，并支持标记已读。


## 10. 设备注册审批链路补齐

本次继续补齐了“设备注册审批”这一条链路，重点包括：

- 服务器 `register_device` 不再因为硬件码已存在就直接创建新设备；新设备默认进入 `device_registration_requests`，等待上位机审批。
- 服务器新增 `GET /api/device/registration-status`，下位机可以查询自己的注册状态、审批意见和排队序号。
- 服务器审批通过/驳回时，除了更新 `device_registration_requests` 外，也会写入 `notifications` 表，便于历史追踪。
- 上位机新增 `Module/device_registration_approval` 页面，可按状态、设备号、关键词查看申请，并执行批准/驳回。
- 下位机主界面新增“查看注册状态”按钮和状态展示栏，待审批时会自动轮询进度，审批通过后会提示可以连接服务器。

涉及新增或更新文件：

- `D:\WorkSpace\NQI_Project_Server\main.py`
- `D:\WorkSpace\NQI_Project_Server\app\feature_routes.py`
- `D:\WorkSpace\NQI_Project\Service\connect_server_service\api\api_client.py`
- `D:\WorkSpace\NQI_Project\Service\connect_server_service\index\Client_server.py`
- `D:\WorkSpace\NQI_Project\Module\device_registration_approval\main.py`
- `D:\WorkSpace\NQI_Project\Module\device_registration_approval\index\registration_approval_window.py`
- `D:\WorkSpace\NQI_Project_lower_client\api\api_client.py`
- `D:\WorkSpace\NQI_Project_lower_client\main.py`

## 11. 启动提速、状态栏联动与预警配置补充

### 11.1 上位机启动与状态栏逻辑

本轮对 `NQI_Project` 的主界面启动链路做了两类优化：

- 主进程中 `p_main_gui` 启动后，不再等待 6 秒才拉起连接服务，而是缩短为 1 秒，让首屏更快显示。
- 电量数据页面 `Module/excel_data_viewer/index/excel_viewer_window.py` 与几何量页面 `Module/image_data_viewer/index/image_viewer_window.py` 不再在构造阶段同步加载缓存，而是：
  1. 先创建页面对象并显示主界面；
  2. 页面首次真正显示时，通过 `QTimer.singleShot(...)` 延后触发缓存初始化；
  3. 加载期间把“正在后台加载电量/几何量缓存数据”写入主窗口自定义状态栏；
  4. 加载完成后把状态更新为“缓存加载完成”。

状态栏 `public/component/custom_status_bar.py` 新增了以下能力：

- `后台`：显示当前后台任务，例如连接服务器、同步设备状态、后台加载缓存、收到新数据后后台下载缓存等。
- `服务器消息(n)`：保留最近 80 条服务器消息，按钮 tooltip 可直接看到消息历史。
- `设备在线: x/y`：显示当前在线设备数量和设备总数，点击直接打开“设备在线状态”页面。
- `最新预警`：显示最近一条预警摘要，点击直接打开“预警通知历史”页面。
- 原有 `服务器地址`、`服务器状态`、`连接/重新连接` 按钮继续保留。

### 11.2 上位机连接服务联动

`Service/connect_server_service/index/Client_server.py` 继续增强为统一状态分发中心：

1. 连接成功后启动 HTTP 长轮询线程；
2. 同时启动设备状态轮询线程，每隔数秒调用 `/api/devices/list`；
3. 把在线数、总数和每台设备最新状态汇总为 `device_status_summary` 消息，发送给主窗口状态栏；
4. 如果发现设备状态变化（例如下位机离线），会产生提示消息并刷新状态栏在线汇总；
5. 收到 `fault_alarm` 时，除了普通提示，还会额外发送 `latest_alarm` 消息给状态栏；
6. 收到 `excel_upload` / `image_upload` 时，状态栏会显示后台正在同步下载缓存。

### 11.3 新增“设备在线状态”页面

新增模块：

- `D:\WorkSpace\NQI_Project\Module\device_status\main.py`
- `D:\WorkSpace\NQI_Project\Module\device_status\index\device_status_window.py`

页面功能：

- 周期性读取服务器 `/api/devices/list`；
- 表格显示设备编号、设备名称、IP、在线状态、创建时间、最后心跳时间；
- 顶部汇总显示在线设备数/离线设备数；
- 状态栏“设备在线: x/y”按钮可以直接跳转到该页面。

### 11.4 新增“预警配置”页面

新增模块：

- `D:\WorkSpace\NQI_Project\Module\alarm_rule_config\main.py`
- `D:\WorkSpace\NQI_Project\Module\alarm_rule_config\index\alarm_rule_config_window.py`

页面功能：

- 从服务器读取预警规则列表；
- 允许编辑规则名称、数据类型、指标、比较符、阈值、告警级别、启用状态和说明；
- 支持新增规则和修改已有规则；
- 对于 `upload_error` 指标，自动把比较符固定为 `enabled`，不再要求阈值；
- 当前支持的典型指标包括：
  - 电量：`file_size_kb`、`max_numeric_value`、`min_numeric_value`、`avg_numeric_value`、`sheet_count`
  - 几何量：`file_size_kb`、`original_size_kb`、`compression_ratio`
  - 通用上传异常：`upload_error`

### 11.5 服务器预警规则与上传判断逻辑

服务器新增规则模型：

- `D:\WorkSpace\NQI_Project_Server\app\database.py` 中新增 `AlarmRule` 表。

服务器新增规则接口：

- `GET /api/alarm-rules`：查询所有预警规则；
- `POST /api/alarm-rules/save`：新增或修改预警规则。

服务器新增规则服务逻辑：

- `app/feature_services.py` 新增默认规则初始化 `ensure_default_alarm_rules()`；
- 新增 `extract_excel_metrics()`：从上传的 Excel 中提取 `sheet_count`、最大值、最小值、平均值等基础数值指标；
- 新增 `build_image_metrics()`：整理几何量文件大小、原始大小、压缩率指标；
- 新增 `evaluate_alarm_rules()`：按规则逐条判断是否命中阈值；
- 新增 `merge_fault_summary()`：把基础故障描述与规则命中信息合并成统一预警摘要；
- 新增 `create_upload_error_notification()`：在上传异常时按规则写入 `notifications` 并推送 `fault_alarm` 长轮询消息。

上传链路更新为：

1. 下位机上传电量或几何量文件；
2. 服务器验证设备身份并保存文件；
3. 服务器生成基础故障标记（显式 `has_fault` 或关键字命中）；
4. 服务器提取当前文件的规则指标；
5. 服务器根据 `alarm_rules` 判断是否命中阈值；
6. 如果命中，则把命中原因合并到 `fault_summary`；
7. 服务器写入：
   - `data_search_index`
   - `fault_records`
   - `notifications`（`fault_alarm`）
   - HTTP 长轮询消息队列
8. 上位机状态栏立即显示最新预警，报警页和通知历史页也能看到记录。

### 11.6 本轮主要修改文件

服务器：

- `D:\WorkSpace\NQI_Project_Server\app\database.py`
- `D:\WorkSpace\NQI_Project_Server\app\feature_services.py`
- `D:\WorkSpace\NQI_Project_Server\app\feature_routes.py`
- `D:\WorkSpace\NQI_Project_Server\main.py`

上位机：

- `D:\WorkSpace\NQI_Project\main.py`
- `D:\WorkSpace\NQI_Project\public\component\custom_status_bar.py`
- `D:\WorkSpace\NQI_Project\index\MainWindow_index.py`
- `D:\WorkSpace\NQI_Project\Service\connect_server_service\index\Client_server.py`
- `D:\WorkSpace\NQI_Project\Service\connect_server_service\api\api_client.py`
- `D:\WorkSpace\NQI_Project\Module\excel_data_viewer\index\excel_viewer_window.py`
- `D:\WorkSpace\NQI_Project\Module\image_data_viewer\index\image_viewer_window.py`
- `D:\WorkSpace\NQI_Project\Module\device_status\main.py`
- `D:\WorkSpace\NQI_Project\Module\device_status\index\device_status_window.py`
- `D:\WorkSpace\NQI_Project\Module\alarm_rule_config\main.py`
- `D:\WorkSpace\NQI_Project\Module\alarm_rule_config\index\alarm_rule_config_window.py`

### 11.7 本轮验证情况

已完成：

- 对本轮改动的上位机关键文件和服务器关键文件执行 `python -m py_compile`，语法检查通过。
- 已确认本轮实现继续使用 HTTP 长轮询，没有引入 WebSocket。

未完成：

- 未在真实 FastAPI + MySQL 运行环境下做完整联调。
- 未实际启动上位机 GUI 观察状态栏实时行为；当前验证以静态编译和代码链路检查为主。

## 12. 2026-07-08 本轮界面交互与线程解耦优化

### 12.1 上位机菜单结构调整
- 主菜单改为 `设备`、`数据`、`预警`、`数据处理`、`工具`、`帮助`。
- `设备` 子菜单：`设备注册审批`、`设备在线状态`、`设备配置`。
- `数据` 子菜单：`电量数据查看`、`几何量图片数据查看`、`数据检索`。
- `预警` 子菜单：`预警配置`、`报警预警`。
- `数据处理`、`工具`、`帮助` 先提供空子菜单占位，便于后续继续扩展。

### 12.2 报警预警页面合并
- 原 `报警预警` 与 `预警通知历史` 已合并到同一个页面。
- 页面主体使用 `QTabWidget`：
  - Tab1：`报警预警`
  - Tab2：`预警通知历史`
- 状态栏里的最新预警跳转，也统一进入该合并页。

### 12.3 上位机卡顿优化
- 在 `BaseWindow` 中增加统一后台任务线程 `AsyncTaskThread`。
- 新增通用方法：
  - `show_loading()`
  - `hide_loading()`
  - `run_async_task()`
- 设备状态、注册审批、数据检索、预警配置、报警预警等页面的服务器读取与提交操作，均改为：
  1. 按钮点击触发
  2. 主线程显示 loading
  3. 子线程执行 HTTP 请求
  4. 通过 Qt 信号槽把结果回传主线程
  5. 主线程刷新表格 / 标签 / 状态栏
- 这样可以避免 PyQt6 主线程直接等待服务器响应，明显降低界面卡顿。

### 12.4 上位机按钮 loading 逻辑
- 所有涉及服务器交互的按钮都增加 loading 遮罩。
- 典型场景包括：
  - 刷新设备状态
  - 刷新 / 审批注册申请
  - 执行数据检索
  - 刷新 / 保存预警规则
  - 刷新报警、确认报警、关闭报警
  - 刷新通知历史、标记通知已读

### 12.5 下位机按钮 loading 与线程安全优化
- 下位机主界面新增统一遮罩 `LoadingOverlay`。
- 下位机新增通用后台线程 `AsyncTaskThread`，用于注册状态查询、设备注册、连接服务器等网络按钮。
- 下位机以下操作已接入 loading：
  - 保存配置
  - 生成硬件密钥
  - 查看注册状态
  - 注册设备
  - 连接服务器
  - 添加电量数据文件
  - 添加几何量数据文件
  - 开始上传
  - 停止上传
- 下位机长轮询线程回调改为先发射 Qt 信号，再由主线程槽函数更新界面，避免后台线程直接操作 UI。

### 12.6 本轮新增运行逻辑
1. 上位机打开页面后先立即显示界面。
2. 用户点击带服务器交互的按钮时，界面先显示 loading 遮罩。
3. 后台线程执行请求，主线程保持可响应状态。
4. 请求成功后主线程更新表格、标签、状态栏，并关闭 loading。
5. 请求失败时主线程弹出错误提示，并关闭 loading。
6. 下位机长轮询状态变化时，通过 Qt 信号通知主线程更新连接状态与注册状态。

## 13. 服务端解析下沉（2026-07-08）

### 13.1 目标
- 下位机上传后，服务器先只负责安全落盘。
- 服务器后台线程再异步处理未处理的 Excel 和图片数据。
- 上位机页面不再本地解析 Excel，也不再本地随机判断图片故障。
- 上位机后续只读取服务端返回的文件路径、处理状态、解析结果、分析结果，并保留下载原始文件能力。

### 13.2 新增/调整的数据表设计
- `meter_excel_data`
  - 新增 `location`
  - 新增 `processing_status`：`pending / processing / done / failed`
  - 新增 `processing_error`
  - 新增 `processed_at`
- `meter_image_data`
  - 新增 `location`
  - 新增 `processing_status`：`pending / processing / done / failed`
  - 新增 `processing_error`
  - 新增 `processed_at`
- `meter_excel_parse_results`
  - 一条 Excel 文件对应一条解析结果
  - 保存 `sheet_count`、`rated_voltage`、`rated_frequency`、`max/min/avg_numeric_value`
  - 保存 `parse_summary`
  - 保存完整 `parsed_data_json`，结构与上位机原页面展示所需结构对齐
- `meter_image_analysis_results`
  - 一条图片文件对应一条分析结果
  - 保存 `recognized_path`、`image_width`、`image_height`、`image_mode`
  - 保存 `mean_brightness`、`brightness_std`、`contrast_score`、`sharpness_score`
  - 保存 `dominant_color`
  - 保存 `has_fault`、`analysis_summary`、`analysis_data_json`

### 13.3 服务端处理线程逻辑
1. 下位机上传 Excel/图片文件。
2. 服务端写入 `meter_excel_data` / `meter_image_data` 主表，状态记为 `pending`。
3. 服务端后台线程轮询：
   - `excel_processor` 扫描 `meter_excel_data.processing_status = pending`
   - `image_processor` 扫描 `meter_image_data.processing_status = pending`
4. Excel 线程执行：
   - 调用 `app/data_processing.py::parse_excel_file()`
   - 将解析摘要与完整结构写入 `meter_excel_parse_results`
   - 更新主表状态为 `done` 或 `failed`
5. 图片线程执行：
   - 调用 `app/data_processing.py::analyze_image_file()`
   - 将亮度、对比度、清晰度、故障判断等写入 `meter_image_analysis_results`
   - 更新主表状态为 `done` 或 `failed`
6. 处理完成后：
   - 更新 `data_search_index`
   - 根据规则维护 `fault_records`
   - 将预警通知写入 `notifications`
   - 通过 HTTP 长轮询发送 `excel_processed` / `image_processed` / `fault_alarm`

### 13.4 上位机读取逻辑调整
- 电量页面：
  - 不再本地重新解析 Excel。
  - 改为读取服务端返回的 `parse_result.parsed_data`，再还原成原页面需要的数据对象。
- 几何量页面：
  - 不再本地随机生成故障结果。
  - 改为读取服务端返回的 `analysis_result` 并展示。
- 缓存同步层：
  - `excel_upload` / `image_upload` 只提示“服务器处理中”
  - `excel_processed` / `image_processed` 才触发上位机缓存同步

### 13.5 当前图片分析策略说明
- 当前版本没有接入外部视觉模型，也没有使用 WebSocket。
- 图片判断已从“随机”改为“确定性规则分析”：
  - 文件名/描述故障关键字
  - 平均亮度
  - 对比度
  - 清晰度
  - 分辨率
- 这样至少保证：
  - 结果可重复
  - 可落库
  - 可检索
  - 可触发预警规则
- 后续可在 `app/data_processing.py::analyze_image_file()` 上继续替换为真实识别模型。

## 14. 服务器消息中心（2026-07-08）

- 自定义状态栏中的 `服务器消息(n)` 按钮不再只把最新一条消息写到 tip。
- 现在点击后会直接打开 `服务器消息中心` 页面。
- 页面位置：
  - 状态栏 `服务器消息(n)` 按钮
  - 菜单 `工具 -> 服务器消息中心`
- 页面能力：
  - 按时间倒序查看最近 80 条服务器消息
  - 查看消息类型、消息内容、原始 payload 详情
  - 一键清空状态栏消息历史
- 状态栏内部新增结构化消息记录：
  - `timestamp`
  - `category`
  - `message`
  - `payload`
- 当状态栏继续收到新服务器消息时，如果消息中心已打开，会同步刷新页面内容。
