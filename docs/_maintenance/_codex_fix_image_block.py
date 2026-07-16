from pathlib import Path
import textwrap

path = Path(r"D:\WorkSpace\NQI_Project\Module\image_data_viewer\index\image_viewer_window.py")
text = path.read_text(encoding="utf-8", errors="ignore")
start = text.find("def showEvent(self, a0: typing.Optional[QtGui.QShowEvent]) -> None:")
end = text.find("    def create_device_image_tab(self, device_id: str) -> QWidget:")
if start < 0 or end < 0 or end <= start:
    raise RuntimeError('image window repair markers not found')
block = textwrap.dedent('''
    def showEvent(self, a0: typing.Optional[QtGui.QShowEvent]) -> None:
        """窗口显示事件"""
        logger.info("几何量图片数据查看器窗口已显示")
        self.is_visible = True
        super().showEvent(a0)
        if not self.cache_bootstrap_started:
            self.cache_bootstrap_started = True
            self.report_background_task('正在从服务器加载几何量分析结果')
            QTimer.singleShot(120, self.bootstrap_cache_load)

    def hideEvent(self, a0: typing.Optional[QtGui.QHideEvent]) -> None:
        """窗口隐藏事件"""
        logger.info("几何量图片数据查看器窗口隐藏")
        self.is_visible = False
        super().hideEvent(a0)

    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, 'queue_thread') and self.queue_thread:
            self.queue_thread.stop()
            logger.info("图片数据查看器队列监听线程已停止")
        super().closeEvent(event)

    def report_background_task(self, message: str):
        """把几何量页面后台任务同步到主窗口状态栏。"""
        try:
            if self.main_gui is not None and getattr(self.main_gui, 'status_bar', None) is not None:
                self.main_gui.status_bar.update_background_task(message)
        except Exception:
            pass

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
        self.history_original_label.clear()
        self.history_recognized_label.clear()
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

    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        info_layout = QHBoxLayout()
        self.status_label = QLabel("状态: 等待数据...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        self.clear_all_btn = QPushButton("清空显示")
        self.clear_all_btn.clicked.connect(self.clear_all_displays)
        info_layout.addWidget(self.clear_all_btn)
        main_layout.addLayout(info_layout)
        self.tab_widget = QTabWidget()
        self.realtime_tab = self.create_realtime_tab()
        self.tab_widget.addTab(self.realtime_tab, "实时识别")
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "历史识别")
        self.cache_tab = self.create_cache_table_tab()
        self.tab_widget.addTab(self.cache_tab, "服务器数据")
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "日志")
        main_layout.addWidget(self.tab_widget)
''')
text = text[:start] + block + "\n" + text[end:]
path.write_text(text, encoding="utf-8")
print('image block repaired')