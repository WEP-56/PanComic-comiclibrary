"""PicACG专用设置对话框"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QCheckBox, QPushButton, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from pancomic.adapters.picacg_adapter import PicACGAdapter


class PicACGSettingsDialog(QDialog):
    """PicACG专用设置对话框"""
    
    # 设置保存信号
    settings_saved = Signal()
    
    def __init__(self, adapter: PicACGAdapter, parent: Optional[QWidget] = None):
        """
        初始化PicACG设置对话框
        
        Args:
            adapter: PicACG适配器实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.adapter = adapter
        
        self.setWindowTitle("PicACG 设置")
        self.setMinimumSize(500, 600)
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
        title = QLabel("PicACG 设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 登录设置组
        login_group = QGroupBox("登录设置")
        login_layout = QVBoxLayout(login_group)
        
        # 邮箱
        email_label = QLabel("邮箱:")
        login_layout.addWidget(email_label)
        
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("输入PicACG邮箱")
        login_layout.addWidget(self.email_edit)
        
        # 密码
        password_label = QLabel("密码:")
        login_layout.addWidget(password_label)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("输入密码")
        login_layout.addWidget(self.password_edit)
        
        # 登录按钮
        self.login_btn = QPushButton("测试登录")
        self.login_btn.clicked.connect(self._test_login)
        login_layout.addWidget(self.login_btn)
        
        # 自动登录
        self.auto_login_checkbox = QCheckBox("启动时自动登录")
        login_layout.addWidget(self.auto_login_checkbox)
        
        layout.addWidget(login_group)
        
        # API设置组
        api_group = QGroupBox("API 设置")
        api_layout = QVBoxLayout(api_group)
        
        # API端点
        endpoint_label = QLabel("API 端点:")
        api_layout.addWidget(endpoint_label)
        
        self.endpoint_combo = QComboBox()
        self.endpoint_combo.addItems([
            "https://picaapi.picacomic.com",
            "https://bika-api.jpacg.cc", 
            "https://188.114.98.153",
            "https://bika2-api.jpacg.cc",
            "https://104.21.91.145",
        ])
        api_layout.addWidget(self.endpoint_combo)
        
        # API测速
        api_test_layout = QHBoxLayout()
        self.api_test_btn = QPushButton("测试API分流")
        self.api_test_btn.clicked.connect(self._test_api_endpoints)
        api_test_layout.addWidget(self.api_test_btn)
        
        self.api_result_label = QLabel("点击测试API分流响应时间")
        self.api_result_label.setWordWrap(True)
        api_test_layout.addWidget(self.api_result_label, 1)
        api_layout.addLayout(api_test_layout)
        
        layout.addWidget(api_group)
        
        # 图片设置组
        image_group = QGroupBox("图片设置")
        image_layout = QVBoxLayout(image_group)
        
        # 图片服务器
        server_label = QLabel("图片服务器:")
        image_layout.addWidget(server_label)
        
        self.image_server_combo = QComboBox()
        self.image_server_combo.addItems([
            "storage.diwodiwo.xyz",
            "storage-b.picacomic.com",
            "s3.picacomic.com", 
            "s2.picacomic.com",
            "storage1.picacomic.com",
        ])
        image_layout.addWidget(self.image_server_combo)
        
        # 图片服务器测速
        image_test_layout = QHBoxLayout()
        self.image_test_btn = QPushButton("测试图片分流")
        self.image_test_btn.clicked.connect(self._test_image_servers)
        image_test_layout.addWidget(self.image_test_btn)
        
        self.image_result_label = QLabel("点击测试图片分流响应时间")
        self.image_result_label.setWordWrap(True)
        image_test_layout.addWidget(self.image_result_label, 1)
        image_layout.addLayout(image_test_layout)
        
        # 图片质量
        quality_label = QLabel("图片质量:")
        image_layout.addWidget(quality_label)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "原图 (original)",
            "高质量 (high)", 
            "中等质量 (medium)",
            "低质量 (low)"
        ])
        image_layout.addWidget(self.quality_combo)
        
        layout.addWidget(image_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _load_current_settings(self) -> None:
        """加载当前设置"""
        try:
            # 从适配器配置加载设置
            config = self.adapter.config
            
            # 登录信息
            credentials = config.get('credentials', {})
            self.email_edit.setText(credentials.get('email', ''))
            self.password_edit.setText(credentials.get('password', ''))
            
            # API端点
            current_endpoint = self.adapter.get_current_endpoint()
            index = self.endpoint_combo.findText(current_endpoint)
            if index >= 0:
                self.endpoint_combo.setCurrentIndex(index)
            
            # 图片服务器
            current_server = self.adapter.get_current_image_server()
            index = self.image_server_combo.findText(current_server)
            if index >= 0:
                self.image_server_combo.setCurrentIndex(index)
            
            # 图片质量
            quality = config.get('image_quality', 'original')
            quality_map = {'original': 0, 'high': 1, 'medium': 2, 'low': 3}
            self.quality_combo.setCurrentIndex(quality_map.get(quality, 0))
            
        except Exception as e:
            print(f"加载设置失败: {e}")
    
    def _connect_signals(self) -> None:
        """连接信号"""
        # 适配器信号 - 使用UniqueConnection避免重复连接
        self.adapter.login_completed.connect(self._on_login_completed, Qt.UniqueConnection)
        self.adapter.login_failed.connect(self._on_login_failed, Qt.UniqueConnection)
        self.adapter.endpoint_test_completed.connect(self._on_api_test_completed, Qt.UniqueConnection)
        self.adapter.image_server_test_completed.connect(self._on_image_test_completed, Qt.UniqueConnection)
    
    def _test_login(self) -> None:
        """测试登录"""
        email = self.email_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "登录", "请输入邮箱和密码")
            return
        
        print(f"🔐 PicACG设置对话框开始登录: {email}")
        
        # 检查适配器状态
        if not self.adapter:
            QMessageBox.critical(self, "登录", "适配器不可用")
            return
        
        if not getattr(self.adapter, '_is_initialized', False):
            QMessageBox.critical(self, "登录", "适配器未初始化")
            return
        
        print(f"✅ 适配器状态正常，开始登录...")
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        
        try:
            # 执行登录
            self.adapter.login({'email': email, 'password': password})
            print(f"📤 登录请求已发送")
        except Exception as e:
            print(f"❌ 登录请求失败: {e}")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("测试登录")
            QMessageBox.critical(self, "登录", f"登录请求失败: {e}")
    
    def _test_api_endpoints(self) -> None:
        """测试API端点"""
        self.api_test_btn.setEnabled(False)
        self.api_test_btn.setText("测试中...")
        self.api_result_label.setText("正在测试API分流...")
        
        self.adapter.test_endpoints()
    
    def _test_image_servers(self) -> None:
        """测试图片服务器"""
        self.image_test_btn.setEnabled(False)
        self.image_test_btn.setText("测试中...")
        self.image_result_label.setText("正在测试图片分流...")
        
        self.adapter.test_image_servers()
    
    def _save_settings(self) -> None:
        """保存设置"""
        try:
            # 保存登录信息
            email = self.email_edit.text().strip()
            password = self.password_edit.text().strip()
            
            if email and password:
                self.adapter.config['credentials'] = {
                    'email': email,
                    'password': password
                }
            
            # 保存API端点
            endpoint = self.endpoint_combo.currentText()
            self.adapter.set_endpoint(endpoint)
            self.adapter.config['endpoint'] = endpoint
            
            # 保存图片服务器
            server = self.image_server_combo.currentText()
            self.adapter.set_image_server(server)
            self.adapter.config['image_server'] = server
            
            # 保存图片质量
            quality_map = {0: 'original', 1: 'high', 2: 'medium', 3: 'low'}
            quality = quality_map[self.quality_combo.currentIndex()]
            self.adapter.config['image_quality'] = quality
            
            # 发送保存信号
            self.settings_saved.emit()
            
            QMessageBox.information(self, "保存", "设置已保存成功！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置失败: {e}")
    
    def _on_login_completed(self, success: bool, message: str) -> None:
        """登录完成处理"""
        print(f"📥 PicACG设置对话框收到登录完成信号: success={success}, message={message}")
        
        self.login_btn.setEnabled(True)
        self.login_btn.setText("测试登录")
        
        if success:
            print(f"✅ 登录成功")
            QMessageBox.information(self, "登录", "登录成功！")
        else:
            print(f"❌ 登录失败: {message}")
            QMessageBox.warning(self, "登录", f"登录失败: {message}")
    
    def _on_login_failed(self, error: str) -> None:
        """登录失败处理"""
        print(f"📥 PicACG设置对话框收到登录失败信号: {error}")
        
        self.login_btn.setEnabled(True)
        self.login_btn.setText("测试登录")
        QMessageBox.critical(self, "登录", f"登录错误: {error}")
    
    def _on_api_test_completed(self, results: dict) -> None:
        """API测试完成处理"""
        self.api_test_btn.setEnabled(True)
        self.api_test_btn.setText("测试API分流")
        
        if not results:
            self.api_result_label.setText("测试失败，请检查网络连接")
            return
        
        # 格式化结果
        success_count = sum(1 for r in results.values() if r > 0)
        result_text = f"测试完成: {success_count}/{len(results)} 个分流可用\n"
        
        # 找到最快的端点
        fastest = None
        fastest_time = float('inf')
        for endpoint, time in results.items():
            if time > 0 and time < fastest_time:
                fastest = endpoint
                fastest_time = time
        
        if fastest:
            result_text += f"最快: {fastest} ({fastest_time:.0f}ms)"
            # 自动选择最快的端点
            index = self.endpoint_combo.findText(fastest)
            if index >= 0:
                self.endpoint_combo.setCurrentIndex(index)
        
        self.api_result_label.setText(result_text)
    
    def _on_image_test_completed(self, results: dict) -> None:
        """图片服务器测试完成处理"""
        self.image_test_btn.setEnabled(True)
        self.image_test_btn.setText("测试图片分流")
        
        if not results:
            self.image_result_label.setText("测试失败，请检查网络连接")
            return
        
        # 格式化结果
        success_count = sum(1 for r in results.values() if r > 0)
        result_text = f"测试完成: {success_count}/{len(results)} 个分流可用\n"
        
        # 找到最快的服务器
        fastest = None
        fastest_time = float('inf')
        for server, time in results.items():
            if time > 0 and time < fastest_time:
                fastest = server
                fastest_time = time
        
        if fastest:
            result_text += f"最快: {fastest} ({fastest_time:.0f}ms)"
            # 自动选择最快的服务器
            index = self.image_server_combo.findText(fastest)
            if index >= 0:
                self.image_server_combo.setCurrentIndex(index)
        
        self.image_result_label.setText(result_text)
    
    def closeEvent(self, event) -> None:
        """关闭事件处理"""
        # 断开信号连接
        try:
            self.adapter.login_completed.disconnect(self._on_login_completed)
            self.adapter.login_failed.disconnect(self._on_login_failed)
            self.adapter.endpoint_test_completed.disconnect(self._on_api_test_completed)
            self.adapter.image_server_test_completed.disconnect(self._on_image_test_completed)
        except:
            pass
        
        super().closeEvent(event)