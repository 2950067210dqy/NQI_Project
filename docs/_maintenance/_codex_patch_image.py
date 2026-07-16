from pathlib import Path
import textwrap

ROOT = Path(r"D:\WorkSpace")
IMAGE = ROOT / "NQI_Project" / "Module" / "image_data_viewer" / "index" / "image_viewer_window.py"

def rd(p): return p.read_text(encoding="utf-8", errors="ignore")
def wr(p,t): p.write_text(t.rstrip("\n")+"\n", encoding="utf-8")
def rep_all(p,o,n):
    t=rd(p)
    if o in t: wr(p,t.replace(o,n))
def ins_before(p,m,b):
    t=rd(p); s=textwrap.dedent(b).strip("\n")
    if s in t: return
    i=t.find(m)
    if i<0: raise RuntimeError(f"missing marker in {p.name}: {m}")
    wr(p,t[:i]+s+"\n\n"+t[i:])
def rep_method(p,name,block):
    lines=rd(p).splitlines(); start=None
    for i,l in enumerate(lines):
        if l.startswith(f"    def {name}("): start=i; break
    if start is None: raise RuntimeError(f"missing method {name} in {p.name}")
    end=len(lines)
    for i in range(start+1,len(lines)):
        l=lines[i]
        if l.startswith("    def ") or l.startswith("    @") or l.startswith("class "):
            end=i; break
    lines[start:end]=textwrap.dedent(block).strip("\n").splitlines()
    wr(p,"\n".join(lines))

rep_all(IMAGE,'self.tab_widget.addTab(self.cache_tab(), "缓存数据")','self.tab_widget.addTab(self.cache_tab(), "服务器数据")')
rep_all(IMAGE,'self.tab_widget.addTab(self.cache_tab, "缓存数据")','self.tab_widget.addTab(self.cache_tab, "服务器数据")')
rep_all(IMAGE,'主界面已显示，几何量缓存等待后台加载','主界面已显示，等待加载服务器几何量数据')
rep_all(IMAGE,'正在后台加载几何量缓存数据','正在后台加载服务器几何量数据')
rep_all(IMAGE,'几何量缓存加载完成','服务器几何量数据加载完成')
rep_all(IMAGE,'几何量缓存后台加载失败','服务器几何量数据后台加载失败')

ins_before(IMAGE,'    def bootstrap_cache_load(self):','''
    def _get_api_client(self):
        """返回页面用于读取服务器分析结果的 API 客户端。"""
        return getattr(self.server_client, 'client', None) if self.server_client else None

    def _fetch_image_records(self, device_id: str = None, limit: int = 100):
        """直接从服务端读取图片记录列表。"""
        api = self._get_api_client()
        if api is None:
            return []
        response = api.list_image_data(device_id=device_id, limit=limit, skip=0) or {}
        return list(response.get('data', []))

    def _fetch_image_detail(self, file_id: int):
        """读取包含 analysis_result 的完整图片记录。"""
        api = self._get_api_client()
        if api is None:
            return None
        response = api.get_image_detail(file_id) or {}
        return response.get('data')

    def _normalize_image_record(self, record: dict) -> dict:
        """统一列表/详情记录结构。"""
        analysis_result = record.get('analysis_result') or {}
        upload_time = record.get('upload_time') or ''
        return {
            'file_id': record.get('id'),
            'device_id': record.get('device_id', ''),
            'file_name': record.get('file_name', ''),
            'timestamp': upload_time.replace('T', ' ')[:19] if upload_time else '',
            'upload_time': upload_time,
            'file_path': record.get('file_path', ''),
            'recognized_path': analysis_result.get('recognized_path') or record.get('file_path', ''),
            'analysis_result': analysis_result,
            'processing_status': record.get('processing_status', ''),
            'processing_error': record.get('processing_error'),
            'image_type': record.get('image_type', ''),
        }

    def _download_image_record(self, record: dict):
        """把服务端原始图片下载到本机。"""
        api = self._get_api_client()
        normalized = self._normalize_image_record(record)
        if api is None or not normalized.get('file_id'):
            self.log_message('下载失败: 服务器客户端不可用')
            return
        save_dir = Path.home() / 'Downloads' / 'NQI' / 'image'
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / normalized.get('file_name', f"image_{normalized['file_id']}.png")
        api.download_image_file(int(normalized['file_id']), save_path)
        self.status_label.setText(f"状态: 已下载 - {normalized.get('file_name', '')}")
        self.log_message(f"已下载几何量数据: {save_path}")

    def _display_history_record(self, record: dict):
        """在历史详情区域展示一条服务端图片记录。"""
        normalized = self._normalize_image_record(record)
        original_path = normalized.get('file_path')
        recognized_path = normalized.get('recognized_path')
        self.history_original_label.clear(); self.history_recognized_label.clear()
        if original_path and Path(original_path).exists():
            pixmap = QPixmap(original_path)
            if not pixmap.isNull():
                self.history_original_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.history_original_label.setText('原图路径不可用')
        if recognized_path and Path(recognized_path).exists():
            pixmap = QPixmap(recognized_path)
            if not pixmap.isNull():
                self.history_recognized_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        elif original_path and Path(original_path).exists():
            pixmap = QPixmap(original_path)
            if not pixmap.isNull():
                self.history_recognized_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.history_recognized_label.setText('识别图路径不可用')
        has_fault = normalized['analysis_result'].get('has_fault', False)
        summary = normalized['analysis_result'].get('analysis_summary', '')
        if has_fault:
            self.history_recognition_result_label.setText('识别故障 ⚠')
            self.history_recognition_result_label.setStyleSheet('color: red; font-size: 14px; font-weight: bold;')
        else:
            self.history_recognition_result_label.setText('未识别故障 ✓')
            self.history_recognition_result_label.setStyleSheet('color: green; font-size: 14px; font-weight: bold;')
        self.history_info_label.setText(
            f"设备: {normalized.get('device_id', '')}\n"
            f"文件: {normalized.get('file_name', '')}\n"
            f"时间: {normalized.get('timestamp', '')}\n"
            f"状态: {normalized.get('processing_status', '')}\n"
            f"结论: {summary}\n"
            f"原图路径: {original_path}\n"
            f"识别图路径: {recognized_path}"
        )

    def _load_image_record_into_ui(self, record: dict) -> bool:
        """将一条服务端图片记录加载到实时展示页。"""
        normalized = self._normalize_image_record(record)
        if not normalized.get('file_id'):
            return False
        if normalized.get('processing_status') != 'done':
            self.status_label.setText(f"状态: 等待服务端分析 - {normalized.get('device_id', '')}")
            self.log_message(f"图片仍在服务端处理中: {normalized.get('file_name', '')}")
            return False
        original_path = normalized.get('file_path')
        if not original_path or not Path(original_path).exists():
            self.log_message(f"原图路径不可用: {original_path}")
            return False
        device_tab = self.get_or_create_device_image_tab(normalized['device_id'])
        target_widget = self.get_next_widget_for_device(device_tab)
        if not target_widget:
            return False
        target_widget.load_original_image(Path(original_path))
        target_widget.apply_server_analysis(normalized['analysis_result'], Path(normalized.get('recognized_path') or original_path))
        device_tab.info_labels['batch'].setText(f"最后接收: {normalized.get('timestamp', '')}")
        with self.widget_access_lock:
            current_count = sum(1 for widget in device_tab.image_widgets if widget.original_image_path)
            widget_count = len(device_tab.image_widgets)
        device_tab.info_labels['count'].setText(f"图片数量: {current_count}/{widget_count}")
        return True
''')

rep_method(IMAGE,'showEvent','''
    def showEvent(self, a0: typing.Optional[QtGui.QShowEvent]) -> None:
        """窗口显示事件"""
        logger.info("几何量图片数据查看器窗口已显示")
        self.is_visible = True
        super().showEvent(a0)
        if not self.cache_bootstrap_started:
            self.cache_bootstrap_started = True
            self.report_background_task('正在从服务器加载几何量分析结果')
            QTimer.singleShot(120, self.bootstrap_cache_load)
''')
rep_method(IMAGE,'bootstrap_cache_load','''
    def bootstrap_cache_load(self):
        """窗口显示后从服务端后台拉取分析完成的数据。"""
        try:
            self.load_latest_from_cache()
            self.load_history_from_cache()
            self.load_cache_images_to_table()
            self.report_background_task('几何量服务端数据加载完成')
        except Exception as exc:
            logger.error(f'几何量服务端数据加载失败: {exc}')
            self.report_background_task(f'几何量服务端数据加载失败: {exc}')
''')
rep_method(IMAGE,'on_cache_data_ready','''
    def on_cache_data_ready(self, file_path: str, device_id: str):
        """收到新图片通知后，直接回源服务端读取最新分析结果。"""
        logger.info(f"[几何量数据页面] 收到服务端数据通知: {Path(file_path).name if file_path else 'server_record'}, 设备: {device_id}")
        self.log_message(f"收到新图片通知: 设备 {device_id}")
        for raw_record in self._fetch_image_records(device_id=device_id, limit=20):
            if self._load_image_record_into_ui(raw_record):
                self.load_history_from_cache()
                self.load_cache_images_to_table()
                break
''')
rep_method(IMAGE,'_update_history_from_cache','''
    def _update_history_from_cache(self):
        """服务端模式下直接刷新历史记录。"""
        self.load_history_from_cache()
''')
rep_method(IMAGE,'update_history_list','''
    def update_history_list(self):
        """更新历史记录列表。"""
        self.history_list.clear()
        for record in self.history_records:
            item_text = f"[{record.get('timestamp', '')}] {record.get('device_id', 'unknown')} - {record.get('file_name', 'unknown')} [{record.get('processing_status', '')}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
''')
rep_method(IMAGE,'on_history_item_clicked','''
    def on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史记录后读取服务端详情。"""
        record = item.data(Qt.ItemDataRole.UserRole) or {}
        if not record or not record.get('file_id'):
            return
        detail = self._fetch_image_detail(int(record['file_id'])) or record
        self._display_history_record(detail)
''')
rep_method(IMAGE,'filter_history','''
    def filter_history(self):
        """按设备和图片类型筛选服务端历史记录。"""
        selected_device = self.history_device_combo.currentText()
        selected_type = self.history_type_combo.currentText()
        filtered = []
        for record in self.history_records:
            if selected_device != '全部设备' and record.get('device_id') != selected_device:
                continue
            image_type = record.get('image_type') or '未分类'
            if selected_type != '全部类型' and image_type != selected_type:
                continue
            filtered.append(record)
        self.history_list.clear()
        for record in filtered:
            item = QListWidgetItem(f"[{record.get('timestamp', '')}] {record.get('device_id', 'unknown')} - {record.get('file_name', 'unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
''')
rep_method(IMAGE,'load_history_from_cache','''
    def load_history_from_cache(self):
        """直接从服务端加载图片历史记录。"""
        logger.info("开始从服务端加载图片历史记录...")
        records = [self._normalize_image_record(record) for record in self._fetch_image_records(limit=200)]
        self.history_records = records
        self.history_device_combo.clear(); self.history_device_combo.addItem('全部设备')
        for device_id in sorted({record.get('device_id') for record in records if record.get('device_id')}):
            self.history_device_combo.addItem(device_id)
        type_values = sorted({record.get('image_type') or '未分类' for record in records})
        self.history_type_combo.clear(); self.history_type_combo.addItem('全部类型')
        for image_type in type_values:
            self.history_type_combo.addItem(image_type)
        self.update_history_list()
''')
rep_method(IMAGE,'load_latest_from_cache','''
    def load_latest_from_cache(self):
        """为每个设备加载最新的服务端已分析记录。"""
        logger.info("开始从服务端加载最新图片...")
        records = [self._normalize_image_record(record) for record in self._fetch_image_records(limit=200)]
        latest_by_device = {}
        for record in records:
            device_id = record.get('device_id')
            if not device_id or device_id in latest_by_device:
                continue
            latest_by_device[device_id] = record
        self.device_image_tabs.clear()
        loaded_count = 0
        for record in latest_by_device.values():
            if self._load_image_record_into_ui(record):
                loaded_count += 1
        if loaded_count == 0:
            placeholder_widget = QWidget()
            placeholder_layout = QVBoxLayout(placeholder_widget)
            placeholder_layout.addWidget(QLabel('等待服务器分析结果...'))
            self.device_image_tabs.addTab(placeholder_widget, '无设备')
            self.status_label.setText('状态: 暂无已分析图片数据')
            return
        self.status_label.setText(f"状态: 已加载 {loaded_count} 个设备的服务端图片数据")
''')
rep_method(IMAGE,'load_cache_images_to_table','''
    def load_cache_images_to_table(self):
        """加载服务端图片记录到表格。"""
        records = [self._normalize_image_record(record) for record in self._fetch_image_records(limit=100)]
        self.cache_image_table.setRowCount(len(records))
        for row, record in enumerate(records):
            self.cache_image_table.setRowHeight(row, 80)
            self.cache_image_table.setItem(row, 0, QTableWidgetItem(record.get('device_id', '')))
            self.cache_image_table.setItem(row, 1, QTableWidgetItem(record.get('file_name', '')))
            self.cache_image_table.setItem(row, 2, QTableWidgetItem(record.get('timestamp', '')))
            has_fault = record.get('analysis_result', {}).get('has_fault', False)
            result_text = record.get('processing_status', 'pending') if record.get('processing_status') != 'done' else ('识别故障 ⚠' if has_fault else '未识别故障 ✓')
            result_item = QTableWidgetItem(result_text)
            if record.get('processing_status') == 'done':
                result_item.setForeground(Qt.GlobalColor.red if has_fault else Qt.GlobalColor.green)
            self.cache_image_table.setItem(row, 3, result_item)
            original_path = record.get('file_path')
            if original_path and Path(original_path).exists():
                thumbnail_label = QLabel(); pixmap = QPixmap(original_path)
                if not pixmap.isNull():
                    thumbnail_label.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.cache_image_table.setCellWidget(row, 4, thumbnail_label)
            action_widget = QWidget(); action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2); action_layout.setSpacing(6)
            view_btn = QPushButton('查看'); view_btn.setStyleSheet('font-size: 9px; padding: 2px 8px;')
            view_btn.clicked.connect(lambda checked, r=record: self.view_image_cache_record(r)); action_layout.addWidget(view_btn)
            download_btn = QPushButton('下载'); download_btn.setStyleSheet('font-size: 9px; padding: 2px 8px;')
            download_btn.clicked.connect(lambda checked, r=record: self._download_image_record(r)); action_layout.addWidget(download_btn)
            action_layout.addStretch(); self.cache_image_table.setCellWidget(row, 5, action_widget)
        self.log_message(f"加载了 {len(records)} 条服务端图片记录")
''')
rep_method(IMAGE,'view_image_cache_record','''
    def view_image_cache_record(self, record: dict):
        """查看一条服务端图片记录。"""
        self._display_history_record(record)
        self.tab_widget.setCurrentIndex(1)
        self.log_message(f"已加载服务端记录: {record.get('file_name', '')}")
''')
rep_method(IMAGE,'set_server_client','''
    def set_server_client(self, client: Client_server):
        """设置服务端客户端，并在页面可见时触发后台刷新。"""
        self.server_client = client
        if self.is_visible:
            QTimer.singleShot(0, self.bootstrap_cache_load)
''')
rep_method(IMAGE,'closeEvent','''
    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, 'queue_thread') and self.queue_thread:
            self.queue_thread.stop()
            logger.info("图片数据查看器队列监听线程已停止")
        super().closeEvent(event)
''')
print('image patch ok')