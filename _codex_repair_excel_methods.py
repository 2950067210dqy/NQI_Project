from pathlib import Path
import re
import textwrap

path = Path(r"D:\WorkSpace\NQI_Project\Module\excel_data_viewer\index\excel_viewer_window.py")
text = path.read_text(encoding='utf-8', errors='ignore')

def replace_method(source: str, name: str, block: str) -> str:
    pattern = rf"(?ms)^\s*def {name}\(.*?(?=^\s*def [A-Za-z_]|^class |\Z)"
    replacement = textwrap.dedent(block).strip('\n') + '\n\n'
    new_source, count = re.subn(pattern, replacement, source, count=1)
    if count != 1:
        raise RuntimeError(f'method not found: {name}')
    return new_source

replacements = {
'showEvent': '''
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        self.is_visible = True
        logger.info("电量数据查看器窗口已显示")
        if not self.cache_bootstrap_started:
            self.cache_bootstrap_started = True
            self.report_background_task('正在从服务器加载电量解析结果')
            QTimer.singleShot(120, self.bootstrap_cache_load)
''',
'hideEvent': '''
    def hideEvent(self, event):
        """窗口隐藏事件"""
        super().hideEvent(event)
        self.is_visible = False
        logger.info("电量数据查看器窗口隐藏")
''',
'report_background_task': '''
    def report_background_task(self, message: str):
        """把电量页面后台任务同步到主窗口状态栏。"""
        try:
            if self.main_gui is not None and getattr(self.main_gui, 'status_bar', None) is not None:
                self.main_gui.status_bar.update_background_task(message)
        except Exception:
            pass
''',
'_get_api_client': '''
    def _get_api_client(self):
        """返回页面用于读取服务器解析结果的 API 客户端。"""
        return getattr(self.server_client, 'client', None) if self.server_client else None
''',
'_fetch_excel_records': '''
    def _fetch_excel_records(self, device_id: str = None, limit: int = 100):
        """直接从服务端读取电量记录列表。"""
        api = self._get_api_client()
        if api is None:
            return []
        response = api.list_excel_data(device_id=device_id, limit=limit, skip=0) or {}
        return list(response.get('data', []))
''',
'_fetch_excel_detail': '''
    def _fetch_excel_detail(self, file_id: int):
        """读取包含 parsed_data 的完整电量记录。"""
        api = self._get_api_client()
        if api is None:
            return None
        response = api.get_excel_detail(file_id) or {}
        return response.get('data')
''',
'_normalize_excel_record': '''
    def _normalize_excel_record(self, record: dict) -> dict:
        """统一列表/详情记录结构。"""
        parse_result = record.get('parse_result') or {}
        upload_time = record.get('upload_time') or ''
        return {
            'device_id': record.get('device_id', ''),
            'file_id': record.get('id'),
            'file_name': record.get('file_name', ''),
            'file_path': record.get('file_path', ''),
            'timestamp': upload_time.replace('T', ' ')[:19] if upload_time else '',
            'upload_time': upload_time,
            'parse_result': parse_result,
            'sheet_count': parse_result.get('sheet_count', 0),
            'rated_voltage': parse_result.get('rated_voltage', 0),
            'rated_voltage_unit': parse_result.get('rated_voltage_unit', ''),
            'rated_frequency': parse_result.get('rated_frequency', 0),
            'rated_frequency_unit': parse_result.get('rated_frequency_unit', ''),
            'processing_status': record.get('processing_status', ''),
            'processing_error': record.get('processing_error'),
        }
''',
'_pick_preferred_excel_record': '''
    def _pick_preferred_excel_record(self, records: list):
        """优先选取服务端已完成解析的记录。"""
        for record in records:
            if record.get('processing_status') == 'done':
                return record
        return records[0] if records else None
''',
'_download_excel_record': '''
    def _download_excel_record(self, record: dict):
        """把服务端原始 Excel 下载到本机。"""
        api = self._get_api_client()
        normalized = self._normalize_excel_record(record)
        if api is None or not normalized.get('file_id'):
            self.log_message('下载失败: 服务器客户端不可用')
            return
        save_dir = Path.home() / 'Downloads' / 'NQI' / 'excel'
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / normalized.get('file_name', f"excel_{normalized['file_id']}.xlsx")
        api.download_excel_file(int(normalized['file_id']), save_path)
        self.status_label.setText(f"状态: 已下载 - {normalized.get('file_name', '')}")
        self.log_message(f"已下载电量数据: {save_path}")
''',
'_load_excel_record_into_ui': '''
    def _load_excel_record_into_ui(self, record: dict, switch_to_realtime: bool = True) -> bool:
        """将一条服务端记录加载到实时展示页。"""
        normalized = self._normalize_excel_record(record)
        if not normalized.get('file_id'):
            return False
        if normalized.get('processing_status') != 'done':
            self.status_label.setText(f"状态: 等待服务端解析 - {normalized.get('device_id', '')}")
            self.log_message(f"文件仍在服务端处理中: {normalized.get('file_name', '')}")
            return False
        detail = self._fetch_excel_detail(int(normalized['file_id'])) or record
        sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
        if not sheet_data_dict:
            self.log_message(f"服务端未返回可显示的解析结果: {normalized.get('file_name', '')}")
            return False
        self.device_data[normalized['device_id']] = sheet_data_dict
        self.create_or_update_device_tab(normalized['device_id'], sheet_data_dict, normalized.get('file_name'))
        if switch_to_realtime:
            self.main_tabs.setCurrentIndex(0)
        return True
''',
'bootstrap_cache_load': '''
    def bootstrap_cache_load(self):
        """窗口显示后从服务端后台拉取解析完成的数据。"""
        try:
            self.load_latest_from_cache()
            self.load_history_from_cache()
            self.load_cache_data_to_table()
            self.refresh_trend_chart()
            self.report_background_task('电量服务端数据加载完成')
        except Exception as exc:
            logger.error(f'电量服务端数据加载失败: {exc}')
            self.report_background_task(f'电量服务端数据加载失败: {exc}')
''',
'on_cache_data_ready': '''
    def on_cache_data_ready(self, file_path: str, device_id: str):
        """收到新数据通知后，直接回源服务端读取最新解析结果。"""
        logger.info(f"[电量数据页面] 收到服务端数据通知: {Path(file_path).name if file_path else 'server_record'}, 设备: {device_id}")
        self.log_message(f"收到新数据通知: 设备 {device_id}")
        latest = self._pick_preferred_excel_record(self._fetch_excel_records(device_id=device_id, limit=20))
        if latest and self._load_excel_record_into_ui(latest):
            self.load_history_from_cache()
            self.load_cache_data_to_table()
            self.refresh_trend_chart()
''',
'build_sheet_data_dict_from_record': '''
    def build_sheet_data_dict_from_record(self, record: dict) -> dict:
        """优先使用服务端解析结果，仅在本地路径可访问时回退本地解析。"""
        parse_result = record.get('parse_result') or {}
        extra_data = record.get('extra_data') or {}
        if not parse_result and isinstance(extra_data, dict):
            parse_result = extra_data.get('parse_result', {})
        parsed_data = parse_result.get('parsed_data') if isinstance(parse_result, dict) else None
        if parsed_data:
            return self.deserialize_sheet_data_dict(parsed_data)
        file_path = record.get('file_path', '')
        if file_path and Path(file_path).exists():
            return self.parse_excel_all_sheets(file_path)
        return {}
''',
'_update_history_from_cache': '''
    def _update_history_from_cache(self):
        """服务端模式下直接刷新历史记录。"""
        self.load_history_from_cache()
''',
'load_history_data': '''
    def load_history_data(self):
        """根据筛选条件加载历史数据。"""
        self.history_list.clear()
        selected_device = self.history_device_combo.currentText()
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        for record in self.history_data:
            if selected_device != '全部设备' and record['device_id'] != selected_device:
                continue
            try:
                record_date = datetime.strptime(record['timestamp'], '%Y-%m-%d %H:%M:%S').date()
            except Exception:
                continue
            if not (start_date <= record_date <= end_date):
                continue
            item = QListWidgetItem(f"{record['timestamp']} - {record['device_id']} - {record['file_name']} [{record.get('processing_status', '')}]")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
''',
'on_history_item_clicked': '''
    def on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史记录后读取服务端详情。"""
        record = item.data(Qt.ItemDataRole.UserRole)
        if not record or not record.get('file_id'):
            return
        detail = self._fetch_excel_detail(int(record['file_id'])) or record
        sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
        if not sheet_data_dict:
            self.log_message(f"记录尚未解析完成: {record.get('file_name', '')}")
            return
        self.history_display_tabs.clear()
        widget = self.create_device_tab_content(record['device_id'], sheet_data_dict, record.get('file_name'))
        self.history_display_tabs.addTab(widget, f"{record['device_id']} - {record['file_name']}")
''',
'load_history_from_cache': '''
    def load_history_from_cache(self):
        """直接从服务端加载历史记录。"""
        logger.info("开始从服务端加载电量历史记录...")
        records = [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=200)]
        self.history_data = records
        self.history_device_combo.clear()
        self.history_device_combo.addItem('全部设备')
        for device_id in sorted({record['device_id'] for record in records if record.get('device_id')}):
            self.history_device_combo.addItem(device_id)
        self.load_history_data()
''',
'load_latest_from_cache': '''
    def load_latest_from_cache(self):
        """为每个设备加载最新的服务端已解析记录。"""
        logger.info("开始从服务端加载最新电量记录...")
        records = [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=200)]
        latest_by_device = {}
        for record in records:
            device_id = record.get('device_id')
            if not device_id or device_id in latest_by_device:
                continue
            latest_by_device[device_id] = record
        self.device_tabs.clear()
        self.device_tab_dict.clear()
        self.device_data.clear()
        loaded_count = 0
        for record in latest_by_device.values():
            if self._load_excel_record_into_ui(record, switch_to_realtime=False):
                loaded_count += 1
        if loaded_count == 0:
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.addWidget(QLabel('等待服务器解析结果...'))
            self.device_tabs.addTab(placeholder, '无设备')
            self.status_label.setText('状态: 暂无已解析电量数据')
            return
        self.status_label.setText(f"状态: 已加载 {loaded_count} 个设备的服务端电量数据")
''',
'create_trend_chart_tab': '''
    def create_trend_chart_tab(self):
        """创建数据趋势图选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("选择设备:"))
        self.trend_device_combo = QComboBox()
        self.trend_device_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_device_combo)
        control_layout.addWidget(QLabel("数据类型:"))
        self.trend_data_type_combo = QComboBox()
        self.trend_data_type_combo.addItems(["功率W", "电压", "电流", "相角"])
        self.trend_data_type_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_data_type_combo)
        control_layout.addWidget(QLabel("相位:"))
        self.trend_phase_combo = QComboBox()
        self.trend_phase_combo.addItems(["A相", "B相", "C相"])
        self.trend_phase_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_phase_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_trend_chart)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        self.trend_figure = Figure(figsize=(12, 6))
        self.trend_canvas = FigureCanvasQTAgg(self.trend_figure)
        layout.addWidget(self.trend_canvas)
        return tab
''',
'load_cache_data_to_table': '''
    def load_cache_data_to_table(self):
        """加载服务端电量记录到表格。"""
        records = [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=100)]
        self.cache_table.setRowCount(len(records))
        for row, record in enumerate(records):
            status = record.get('processing_status', 'pending')
            self.cache_table.setItem(row, 0, QTableWidgetItem(record['device_id']))
            self.cache_table.setItem(row, 1, QTableWidgetItem(record['file_name']))
            self.cache_table.setItem(row, 2, QTableWidgetItem(record['timestamp']))
            self.cache_table.setItem(row, 3, QTableWidgetItem(str(record['sheet_count']) if status == 'done' else status))
            voltage_text = '--' if status != 'done' else f"{record['rated_voltage']}{record['rated_voltage_unit']}"
            freq_text = '--' if status != 'done' else f"{record['rated_frequency']}{record['rated_frequency_unit']}"
            self.cache_table.setItem(row, 4, QTableWidgetItem(voltage_text))
            self.cache_table.setItem(row, 5, QTableWidgetItem(freq_text))
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(6)
            view_btn = QPushButton('查看')
            view_btn.setStyleSheet('font-size: 9px; padding: 2px 8px;')
            view_btn.clicked.connect(lambda checked, r=record: self.view_cache_record(r))
            action_layout.addWidget(view_btn)
            download_btn = QPushButton('下载')
            download_btn.setStyleSheet('font-size: 9px; padding: 2px 8px;')
            download_btn.clicked.connect(lambda checked, r=record: self._download_excel_record(r))
            action_layout.addWidget(download_btn)
            action_layout.addStretch()
            self.cache_table.setCellWidget(row, 6, action_widget)
        self.log_message(f"加载了 {len(records)} 条服务端电量记录")
''',
'view_cache_record': '''
    def view_cache_record(self, record: dict):
        """查看一条服务端电量记录。"""
        if self._load_excel_record_into_ui(record):
            self.log_message(f"已加载服务端记录: {record.get('file_name', '')}")
''',
'refresh_trend_chart': '''
    def refresh_trend_chart(self):
        """刷新趋势图设备列表。"""
        devices = sorted({record['device_id'] for record in self.history_data if record.get('device_id')})
        current_device = self.trend_device_combo.currentText()
        self.trend_device_combo.clear()
        self.trend_device_combo.addItems(devices)
        if current_device in devices:
            self.trend_device_combo.setCurrentText(current_device)
        self.update_trend_chart(self.trend_device_combo.currentText())
''',
'update_trend_chart': '''
    def update_trend_chart(self, device_id: str = None):
        """基于服务端解析后的结构化数据绘制趋势图。"""
        try:
            if not device_id:
                device_id = self.trend_device_combo.currentText()
            if not device_id:
                return
            records = [record for record in self._fetch_excel_records(device_id=device_id, limit=20) if record.get('processing_status') == 'done']
            if not records:
                self.trend_figure.clear()
                ax = self.trend_figure.add_subplot(111)
                ax.text(0.5, 0.5, '暂无可用趋势数据', ha='center', va='center', transform=ax.transAxes)
                self.trend_canvas.draw()
                self.log_message(f"设备 {device_id} 没有已解析的历史数据")
                return
            data_type = self.trend_data_type_combo.currentText()
            phase = self.trend_phase_combo.currentText()
            timestamps = []
            values = []
            for record in reversed(records):
                detail = self._fetch_excel_detail(int(record['id']))
                if not detail:
                    continue
                sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
                if not sheet_data_dict:
                    continue
                selected_value = None
                for sheet in sheet_data_dict.values():
                    for data_type_item in sheet.data:
                        if data_type_item.name != data_type:
                            continue
                        for phase_item in data_type_item.data.y:
                            if phase_item.name != phase:
                                continue
                            for device_item in phase_item.data:
                                numeric_values = []
                                for raw_value in device_item.data:
                                    try:
                                        numeric_values.append(float(raw_value))
                                    except Exception:
                                        continue
                                if numeric_values:
                                    selected_value = sum(numeric_values) / len(numeric_values)
                                    break
                            if selected_value is not None:
                                break
                        if selected_value is not None:
                            break
                    if selected_value is not None:
                        break
                if selected_value is None:
                    continue
                timestamps.append((detail.get('upload_time') or '').replace('T', ' ')[:19])
                values.append(selected_value)
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)
            if values:
                ax.plot(range(len(values)), values, marker='o', linewidth=1.5)
                ax.set_xticks(range(len(timestamps)))
                ax.set_xticklabels(timestamps, rotation=30, ha='right', fontsize=8)
                ax.set_title(f'{device_id} - {data_type} - {phase}')
                ax.set_ylabel(data_type)
                ax.grid(True, linestyle='--', alpha=0.35)
            else:
                ax.text(0.5, 0.5, '暂无可用趋势数据', ha='center', va='center', transform=ax.transAxes)
                ax.set_axis_off()
            self.trend_figure.tight_layout()
            self.trend_canvas.draw()
        except Exception as e:
            logger.error(f"更新趋势图失败: {e}")
            self.log_message(f"更新趋势图失败: {e}")
''',
'set_server_client': '''
    def set_server_client(self, client: Client_server):
        """设置服务端客户端，并在页面可见时触发后台刷新。"""
        self.server_client = client
        if self.is_visible:
            QTimer.singleShot(0, self.bootstrap_cache_load)
''',
'closeEvent': '''
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'queue_thread'):
            self.queue_thread.stop()
        super().closeEvent(event)
''',
'refresh_data': '''
    def refresh_data(self):
        """刷新数据"""
        self.bootstrap_cache_load()
''',
}

for name, block in replacements.items():
    text = replace_method(text, name, block)

path.write_text(text, encoding='utf-8')
print('excel methods repaired')