"""WNACG (绅士漫画) 专用设置对话框"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QMessageBox, QGroupBox, QTextEdit, QWidget
)
from PySide6.QtCore import Qt, Signal

from pancomic.adapters.wnacg_adapter import WNACGAdapter


class WNACGSettingsDialog(QDialog):
    """WNACG (绅士漫画) 专用设置对话框"""
    
    # 设置保存信号
    settings_saved = Signal()
    
    def __init__(self, adapter: WNACGAdapter, parent: Optional[QWidget] = None):
        """
        初始化WNACG设置对话框
        
        Args:
            adapter: WNACG适配器实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.adapter = adapter
        
        self.setWindowTitle("绅士漫画 设置")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("绅士漫画 设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 域名设置组
        domain_group = QGroupBox("域名设置")
        domain_layout = QVBoxLayout(domain_group)
        
        # 域名选择说明
        domain_info = QLabel("绅士漫画会自动从发布页获取最新可用域名，无需手动设置。")
        domain_info.setWordWrap(True)
        domain_info.setStyleSheet("color: #666666; font-size: 12px; margin-bottom: 10px;")
        domain_layout.addWidget(domain_info)
        
        # 当前域名显示
        current_domain_label = QLabel("当前使用域名:")
        domain_layout.addWidget(current_domain_label)
        
        self.current_domain_display = QLabel("自动获取中...")
        self.current_domain_display.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
            }
        """)
        domain_layout.addWidget(self.current_domain_display)
        
        # 域名测试按钮
        domain_test_layout = QHBoxLayout()
        self.domain_test_btn = QPushButton("测试当前域名")
        self.domain_test_btn.clicked.connect(self._test_current_domain)
        domain_test_layout.addWidget(self.domain_test_btn)
        
        self.domain_result_label = QLabel("点击测试域名可用性")
        self.domain_result_label.setWordWrap(True)
        domain_test_layout.addWidget(self.domain_result_label, 1)
        domain_layout.addLayout(domain_test_layout)
        
        # 刷新域名按钮
        refresh_domain_layout = QHBoxLayout()
        self.refresh_domain_btn = QPushButton("刷新域名列表")
        self.refresh_domain_btn.clicked.connect(self._refresh_domains)
        refresh_domain_layout.addWidget(self.refresh_domain_btn)
        
        self.refresh_result_label = QLabel("从发布页获取最新可用域名")
        self.refresh_result_label.setWordWrap(True)
        refresh_domain_layout.addWidget(self.refresh_result_label, 1)
        domain_layout.addLayout(refresh_domain_layout)
        
        layout.addWidget(domain_group)
        
        # 其他设置组
        other_group = QGroupBox("其他设置")
        other_layout = QVBoxLayout(other_group)
        
        # 说明文本
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(120)
        info_text.setPlainText(
            "绅士漫画 (WNACG) 特点：\n"
            "• 无需登录即可使用\n"
            "• 自动域名发现和切换\n"
            "• 支持同人誌、单行本、韩漫等分类\n"
            "• 已禁止新用户注册，API相对稳定\n"
            "• 本子站性质，整本作为一个章节处理"
        )
        info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
                font-size: 12px;
                color: #495057;
            }
        """)
        other_layout.addWidget(info_text)
        
        layout.addWidget(other_group)
        
        # 按钮组
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 35)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        buttons_layout.addWidget(cancel_btn)
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.setFixedSize(80, 35)
        save_btn.clicked.connect(self._save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        buttons_layout.addWidget(save_btn)
        
        layout.addLayout(buttons_layout)
    
    def _connect_signals(self) -> None:
        """连接信号"""
        pass
    
    def _load_current_settings(self) -> None:
        """加载当前设置"""
        try:
            # 尝试获取当前域名
            if hasattr(self.adapter.api.async_source, 'domain') and self.adapter.api.async_source.domain:
                domain = self.adapter.api.async_source.domain
                self.current_domain_display.setText(domain)
            else:
                self.current_domain_display.setText("未初始化")
        except Exception as e:
            print(f"Failed to load current domain: {e}")
            self.current_domain_display.setText("获取失败")
    
    def _test_current_domain(self) -> None:
        """测试当前域名"""
        self.domain_test_btn.setEnabled(False)
        self.domain_result_label.setText("测试中...")
        
        try:
            # 简单的搜索测试
            result = self.adapter.search("test", 1)
            if result and result.get("comics"):
                self.domain_result_label.setText("✅ 域名可用")
                self.domain_result_label.setStyleSheet("color: green;")
            else:
                self.domain_result_label.setText("⚠️ 域名响应异常")
                self.domain_result_label.setStyleSheet("color: orange;")
        except Exception as e:
            self.domain_result_label.setText(f"❌ 域名不可用: {str(e)[:50]}")
            self.domain_result_label.setStyleSheet("color: red;")
        finally:
            self.domain_test_btn.setEnabled(True)
    
    def _refresh_domains(self) -> None:
        """刷新域名列表"""
        self.refresh_domain_btn.setEnabled(False)
        self.refresh_result_label.setText("正在从发布页获取最新域名...")
        
        try:
            # 重新初始化适配器以获取新域名
            old_domain = getattr(self.adapter.api.async_source, 'domain', '未知')
            
            # 清除当前域名，强制重新获取
            self.adapter.api.async_source.domain = None
            
            # 执行一次搜索来触发域名获取
            result = self.adapter.search("test", 1)
            
            new_domain = getattr(self.adapter.api.async_source, 'domain', '未知')
            
            if new_domain and new_domain != old_domain:
                self.current_domain_display.setText(new_domain)
                self.refresh_result_label.setText(f"✅ 已更新域名: {old_domain} → {new_domain}")
                self.refresh_result_label.setStyleSheet("color: green;")
            elif new_domain:
                self.refresh_result_label.setText(f"ℹ️ 域名未变化: {new_domain}")
                self.refresh_result_label.setStyleSheet("color: blue;")
            else:
                self.refresh_result_label.setText("❌ 获取域名失败")
                self.refresh_result_label.setStyleSheet("color: red;")
                
        except Exception as e:
            self.refresh_result_label.setText(f"❌ 刷新失败: {str(e)[:50]}")
            self.refresh_result_label.setStyleSheet("color: red;")
        finally:
            self.refresh_domain_btn.setEnabled(True)
    
    def _save_settings(self) -> None:
        """保存设置"""
        try:
            # WNACG 目前没有需要持久化的设置
            # 域名是自动获取的，不需要保存
            
            QMessageBox.information(self, "保存成功", "设置已保存")
            
            # 发送信号
            self.settings_saved.emit()
            
            # 关闭对话框
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置时出错：{str(e)}")
    
    def _apply_settings(self) -> None:
        """应用设置到适配器"""
        # WNACG 目前没有需要应用的设置
        pass