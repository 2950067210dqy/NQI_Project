from pathlib import Path
path = Path(r"D:\WorkSpace\NQI_Project\Module\image_data_viewer\index\image_viewer_window.py")
text = path.read_text(encoding="utf-8", errors="ignore")
start = text.find("        self.history_info_label.setText(")
end = text.find("\n\n    def _load_image_record_into_ui", start)
if start < 0 or end < 0:
    raise RuntimeError('history info block not found')
replacement = """        self.history_info_label.setText(\n            f\"设备: {normalized.get('device_id', '')}\\n\"\n            f\"文件: {normalized.get('file_name', '')}\\n\"\n            f\"时间: {normalized.get('timestamp', '')}\\n\"\n            f\"状态: {normalized.get('processing_status', '')}\\n\"\n            f\"结论: {summary}\\n\"\n            f\"原图路径: {original_path}\\n\"\n            f\"识别图路径: {recognized_path}\"\n        )"""
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')
print('image fstring fixed')