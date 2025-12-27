"""设置页面 - 集成所有设置功能"""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, 
    QStackedWidget, QLabel, QLineEdit, QComboBox, QCheckBox, 
    QPushButton, QSpinBox, QFileDialog, QMessageBox, QListWidgetItem,
    QGroupBox, QFormLayout, QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from pathlib import Path

from pancomic.core.config_manager import ConfigManager
from pancomic.adapters.picacg_adapter import PicACGAdapter
from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.adapters.ehentai_adapter import EHentaiAdapter


class SettingsPage(QWidget):
    """设置页面 - 左侧标签，右侧设置内容"""
    
    # 设置保存信号
    settings_saved = Signal()
    
    # JMComic测速完成信号 (使用object类型传递dict)
    _jm_api_test_done = Signal(object)
    _jm_img_test_done = Signal(object)
    
    def __init__(self, 
                 config_manager: ConfigManager,
                 picacg_adapter: Optional[PicACGAdapter] = None,
                 jmcomic_adapter: Optional[JMComicAdapter] = None,
                 ehentai_adapter: Optional[EHentaiAdapter] = None,
                 parent: Optional[QWidget] = None):
        """
        初始化设置页面
        
        Args:
            config_manager: 配置管理器
            picacg_adapter: PicACG适配器
            jmcomic_adapter: JMComic适配器  
            ehentai_adapter: EHentai适配器
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.picacg_adapter = picacg_adapter
        self.jmcomic_adapter = jmcomic_adapter
        self.ehentai_adapter = ehentai_adapter
        
        self._setup_ui()
        self._load_settings()
        self._connect_signals()
    
    def showEvent(self, event) -> None:
        """页面显示时更新登录状态"""
        super().showEvent(event)
        self._update_picacg_login_status()
    
    def _setup_ui(self) -> None:
        """设置UI界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧导航列表
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(200)
        self.nav_list.setSpacing(2)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: none;
                border-right: 1px solid #3a3a3a;
            }
            QListWidget::item {
                padding: 12px 16px;
                color: white;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
        """)
        
        # 添加导航项
        nav_items = [
            "常规设置",
            "PicACG",
            "JMComic", 
            "下载设置",
            "使用须知"
        ]
        
        for item_text in nav_items:
            item = QListWidgetItem(item_text)
            self.nav_list.addItem(item)
        
        layout.addWidget(self.nav_list)
        
        # 右侧内容区域
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #1e1e1e;
            }
        """)
        
        # 创建各个设置页面
        self.pages = {}
        self.pages['general'] = self._create_general_page()
        self.pages['picacg'] = self._create_picacg_page()
        self.pages['jmcomic'] = self._create_jmcomic_page()
        self.pages['download'] = self._create_download_page()
        self.pages['tips'] = self._create_tips_page()
        
        # 添加页面到堆栈
        for page in self.pages.values():
            self.content_stack.addWidget(page)
        
        layout.addWidget(self.content_stack, 1)
        
        # 连接导航
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        
        # 默认选择第一项
        self.nav_list.setCurrentRow(0)
    
    def _create_general_page(self) -> QWidget:
        """创建常规设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("常规设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 主题设置
        theme_group = QGroupBox("外观设置")
        theme_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色主题", "浅色主题", "跟随系统"])
        theme_layout.addRow("主题:", self.theme_combo)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["简体中文", "English"])
        theme_layout.addRow("语言:", self.language_combo)
        
        layout.addWidget(theme_group)
        
        # 更新设置
        update_group = QGroupBox("更新设置")
        update_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        update_layout = QVBoxLayout(update_group)
        
        self.auto_check_updates = QCheckBox("启动时自动检查更新")
        self.auto_check_updates.setStyleSheet("color: white;")
        update_layout.addWidget(self.auto_check_updates)
        
        layout.addWidget(update_group)
        
        # 数据管理
        data_group = QGroupBox("数据管理")
        data_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        data_layout = QVBoxLayout(data_group)
        
        # 清除缓存按钮
        cache_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("清除缓存")
        self.clear_cache_btn.setFixedWidth(120)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #d83b01;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #ea4300; }
        """)
        cache_layout.addWidget(self.clear_cache_btn)
        
        self.cache_info_label = QLabel("清除图片缓存以释放磁盘空间")
        self.cache_info_label.setStyleSheet("color: #888888; margin-left: 10px;")
        cache_layout.addWidget(self.cache_info_label)
        cache_layout.addStretch()
        data_layout.addLayout(cache_layout)
        
        # 清除日志按钮
        logs_layout = QHBoxLayout()
        self.clear_logs_btn = QPushButton("清除日志")
        self.clear_logs_btn.setFixedWidth(120)
        self.clear_logs_btn.clicked.connect(self._clear_logs)
        self.clear_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #d83b01;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #ea4300; }
        """)
        logs_layout.addWidget(self.clear_logs_btn)
        
        self.logs_info_label = QLabel("清除应用程序日志文件")
        self.logs_info_label.setStyleSheet("color: #888888; margin-left: 10px;")
        logs_layout.addWidget(self.logs_info_label)
        logs_layout.addStretch()
        data_layout.addLayout(logs_layout)
        
        layout.addWidget(data_group)
        
        layout.addStretch()
        
        # 保存按钮 (右下角)
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.general_save_btn = QPushButton("保存设置")
        self.general_save_btn.setFixedSize(120, 40)
        self.general_save_btn.clicked.connect(self._on_save_clicked)
        self.general_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1084d8; }
            QPushButton:pressed { background-color: #006cbd; }
        """)
        save_layout.addWidget(self.general_save_btn)
        layout.addLayout(save_layout)
        
        return page
    
    def _create_picacg_page(self) -> QWidget:
        """创建PicACG设置页面"""
        from PySide6.QtWidgets import QButtonGroup, QRadioButton, QGridLayout
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("PicACG 设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 登录设置
        login_group = QGroupBox("登录设置")
        login_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        login_layout = QFormLayout(login_group)
        
        self.picacg_email = QLineEdit()
        self.picacg_email.setPlaceholderText("输入PicACG邮箱")
        self.picacg_email.setStyleSheet("padding: 8px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        self.picacg_email.textChanged.connect(self._on_setting_changed)
        login_layout.addRow("邮箱:", self.picacg_email)
        
        self.picacg_password = QLineEdit()
        self.picacg_password.setEchoMode(QLineEdit.Password)
        self.picacg_password.setPlaceholderText("输入密码")
        self.picacg_password.setStyleSheet("padding: 8px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        self.picacg_password.textChanged.connect(self._on_setting_changed)
        login_layout.addRow("密码:", self.picacg_password)
        
        # 登录按钮和状态
        login_btn_layout = QHBoxLayout()
        self.picacg_login_btn = QPushButton("测试登录")
        self.picacg_login_btn.setFixedWidth(100)
        self.picacg_login_btn.clicked.connect(self._test_picacg_login)
        login_btn_layout.addWidget(self.picacg_login_btn)
        
        self.picacg_login_status = QLabel("未登录")
        self.picacg_login_status.setStyleSheet("color: #ff4444; margin-left: 10px;")
        login_btn_layout.addWidget(self.picacg_login_status)
        login_btn_layout.addStretch()
        
        login_layout.addRow("", login_btn_layout)
        
        self.picacg_auto_login = QCheckBox("启动时自动登录")
        self.picacg_auto_login.setStyleSheet("color: white;")
        self.picacg_auto_login.stateChanged.connect(self._on_setting_changed)
        login_layout.addRow("", self.picacg_auto_login)
        
        layout.addWidget(login_group)
        
        # API设置 - 使用单选按钮组
        api_group = QGroupBox("API 分流")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        api_layout = QVBoxLayout(api_group)
        
        # API分流选择 (单选按钮组)
        api_radio_layout = QGridLayout()
        self.picacg_api_group = QButtonGroup(self)
        
        # API端点列表
        api_options = [
            ("picaapi.picacomic.com", "https://picaapi.picacomic.com"),
            ("post-api.wikawika.xyz", "https://post-api.wikawika.xyz"),
            ("bika-api.jpacg.cc", "https://bika-api.jpacg.cc"),
            ("188.114.98.153", "https://188.114.98.153"),
            ("bika2-api.jpacg.cc", "https://bika2-api.jpacg.cc"),
            ("104.21.91.145", "https://104.21.91.145"),
        ]
        
        self.picacg_api_radios = {}
        self.picacg_api_labels = {}
        for i, (text, url) in enumerate(api_options):
            radio = QRadioButton(text)
            radio.setStyleSheet("color: white;")
            radio.setProperty("url", url)
            self.picacg_api_group.addButton(radio, i)
            self.picacg_api_radios[i] = radio
            api_radio_layout.addWidget(radio, i, 0)
            
            # 延迟标签
            label = QLabel("")
            label.setStyleSheet("color: #888888; min-width: 80px;")
            self.picacg_api_labels[i] = label
            api_radio_layout.addWidget(label, i, 1)
        
        self.picacg_api_radios[0].setChecked(True)  # 默认第一个
        api_layout.addLayout(api_radio_layout)
        
        # API测速按钮
        api_test_layout = QHBoxLayout()
        self.picacg_api_test_btn = QPushButton("测试API分流")
        self.picacg_api_test_btn.setFixedWidth(120)
        self.picacg_api_test_btn.clicked.connect(self._test_picacg_api)
        api_test_layout.addWidget(self.picacg_api_test_btn)
        api_test_layout.addStretch()
        api_layout.addLayout(api_test_layout)
        
        layout.addWidget(api_group)
        
        # 图片设置 - 使用单选按钮组
        image_group = QGroupBox("图片分流")
        image_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        image_layout = QVBoxLayout(image_group)
        
        # 图片服务器选择 (单选按钮组)
        img_radio_layout = QGridLayout()
        self.picacg_img_group = QButtonGroup(self)
        
        img_options = [
            ("storage.diwodiwo.xyz", "storage.diwodiwo.xyz"),
            ("storage-b.picacomic.com", "storage-b.picacomic.com"),
            ("s3.picacomic.com", "s3.picacomic.com"),
            ("s2.picacomic.com", "s2.picacomic.com"),
            ("storage1.picacomic.com", "storage1.picacomic.com"),
        ]
        
        self.picacg_img_radios = {}
        self.picacg_img_labels = {}
        for i, (text, server) in enumerate(img_options):
            radio = QRadioButton(text)
            radio.setStyleSheet("color: white;")
            radio.setProperty("server", server)
            self.picacg_img_group.addButton(radio, i)
            self.picacg_img_radios[i] = radio
            img_radio_layout.addWidget(radio, i, 0)
            
            # 延迟标签
            label = QLabel("")
            label.setStyleSheet("color: #888888; min-width: 80px;")
            self.picacg_img_labels[i] = label
            img_radio_layout.addWidget(label, i, 1)
        
        self.picacg_img_radios[0].setChecked(True)  # 默认第一个
        image_layout.addLayout(img_radio_layout)
        
        # 图片测速按钮
        img_test_layout = QHBoxLayout()
        self.picacg_image_test_btn = QPushButton("测试图片分流")
        self.picacg_image_test_btn.setFixedWidth(120)
        self.picacg_image_test_btn.clicked.connect(self._test_picacg_image)
        img_test_layout.addWidget(self.picacg_image_test_btn)
        img_test_layout.addStretch()
        image_layout.addLayout(img_test_layout)
        
        # 图片质量
        quality_layout = QHBoxLayout()
        quality_label = QLabel("图片质量:")
        quality_label.setStyleSheet("color: white;")
        quality_layout.addWidget(quality_label)
        
        self.picacg_quality = QComboBox()
        self.picacg_quality.addItems(["原图", "高质量", "中等质量", "低质量"])
        self.picacg_quality.setFixedWidth(150)
        quality_layout.addWidget(self.picacg_quality)
        quality_layout.addStretch()
        image_layout.addLayout(quality_layout)
        
        layout.addWidget(image_group)
        
        layout.addStretch()
        
        # 保存按钮 (右下角)
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.picacg_save_btn = QPushButton("保存设置")
        self.picacg_save_btn.setFixedSize(120, 40)
        self.picacg_save_btn.clicked.connect(self._on_save_clicked)
        self.picacg_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1084d8; }
            QPushButton:pressed { background-color: #006cbd; }
        """)
        save_layout.addWidget(self.picacg_save_btn)
        layout.addLayout(save_layout)
        
        return page
    
    def _create_jmcomic_page(self) -> QWidget:
        """创建JMComic设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("JMComic 设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 登录设置
        login_group = QGroupBox("登录设置")
        login_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        login_layout = QFormLayout(login_group)
        
        self.jm_username = QLineEdit()
        self.jm_username.setPlaceholderText("输入用户名")
        self.jm_username.setStyleSheet("padding: 8px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        login_layout.addRow("用户名:", self.jm_username)
        
        self.jm_password = QLineEdit()
        self.jm_password.setEchoMode(QLineEdit.Password)
        self.jm_password.setPlaceholderText("输入密码")
        self.jm_password.setStyleSheet("padding: 8px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        login_layout.addRow("密码:", self.jm_password)
        
        # 登录按钮和状态
        jm_login_btn_layout = QHBoxLayout()
        self.jm_login_btn = QPushButton("测试登录")
        self.jm_login_btn.setFixedWidth(100)
        self.jm_login_btn.clicked.connect(self._test_jmcomic_login)
        jm_login_btn_layout.addWidget(self.jm_login_btn)
        
        self.jm_login_status = QLabel("未登录")
        self.jm_login_status.setStyleSheet("color: #ff4444; margin-left: 10px;")
        jm_login_btn_layout.addWidget(self.jm_login_status)
        jm_login_btn_layout.addStretch()
        login_layout.addRow("", jm_login_btn_layout)
        
        self.jm_auto_login = QCheckBox("启动时自动登录")
        self.jm_auto_login.setStyleSheet("color: white;")
        login_layout.addRow("", self.jm_auto_login)
        
        layout.addWidget(login_group)
        
        # API分流设置
        api_group = QGroupBox("API 分流")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        api_layout = QVBoxLayout(api_group)
        
        # API分流选择 (单选按钮组)
        from PySide6.QtWidgets import QButtonGroup, QRadioButton, QGridLayout
        
        api_radio_layout = QGridLayout()
        self.jm_api_group = QButtonGroup(self)
        
        api_options = [
            ("分流1 (cdnbea.club)", 1),
            ("分流2 (cdnbea.cc)", 2),
            ("分流3 (cdnbea.net)", 3),
            ("分流4 (jmapiproxyxxx.vip)", 4),
            ("CDN分流", 5),
            ("US反代分流", 6),
        ]
        
        self.jm_api_radios = {}
        self.jm_api_labels = {}
        for i, (text, value) in enumerate(api_options):
            radio = QRadioButton(text)
            radio.setStyleSheet("color: white;")
            self.jm_api_group.addButton(radio, value)
            self.jm_api_radios[value] = radio
            api_radio_layout.addWidget(radio, i, 0)
            
            # 延迟标签
            label = QLabel("")
            label.setStyleSheet("color: #888888; min-width: 80px;")
            self.jm_api_labels[value] = label
            api_radio_layout.addWidget(label, i, 1)
        
        self.jm_api_radios[5].setChecked(True)  # 默认CDN分流
        api_layout.addLayout(api_radio_layout)
        
        # CDN地址输入
        cdn_api_layout = QHBoxLayout()
        cdn_api_label = QLabel("CDN地址:")
        cdn_api_label.setStyleSheet("color: white;")
        cdn_api_layout.addWidget(cdn_api_label)
        
        self.jm_cdn_api_ip = QLineEdit()
        self.jm_cdn_api_ip.setText("104.18.227.172")
        self.jm_cdn_api_ip.setPlaceholderText("CDN IP地址")
        self.jm_cdn_api_ip.setFixedWidth(150)
        self.jm_cdn_api_ip.setStyleSheet("padding: 6px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        cdn_api_layout.addWidget(self.jm_cdn_api_ip)
        cdn_api_layout.addStretch()
        api_layout.addLayout(cdn_api_layout)
        
        # API测速按钮
        api_test_layout = QHBoxLayout()
        self.jm_api_test_btn = QPushButton("测试API分流")
        self.jm_api_test_btn.setFixedWidth(120)
        self.jm_api_test_btn.clicked.connect(self._test_jmcomic_api)
        api_test_layout.addWidget(self.jm_api_test_btn)
        api_test_layout.addStretch()
        api_layout.addLayout(api_test_layout)
        
        layout.addWidget(api_group)
        
        # 图片分流设置
        img_group = QGroupBox("图片分流")
        img_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        img_layout = QVBoxLayout(img_group)
        
        img_radio_layout = QGridLayout()
        self.jm_img_group = QButtonGroup(self)
        
        img_options = [
            ("分流1 (cdn-msp)", 1),
            ("分流2 (cdn-msp2)", 2),
            ("分流3 (jmapiproxy3)", 3),
            ("分流4 (jmapiproxy4)", 4),
            ("CDN分流", 5),
            ("US反代分流", 6),
        ]
        
        self.jm_img_radios = {}
        self.jm_img_labels = {}
        for i, (text, value) in enumerate(img_options):
            radio = QRadioButton(text)
            radio.setStyleSheet("color: white;")
            self.jm_img_group.addButton(radio, value)
            self.jm_img_radios[value] = radio
            img_radio_layout.addWidget(radio, i, 0)
            
            label = QLabel("")
            label.setStyleSheet("color: #888888; min-width: 80px;")
            self.jm_img_labels[value] = label
            img_radio_layout.addWidget(label, i, 1)
        
        self.jm_img_radios[5].setChecked(True)  # 默认CDN分流
        img_layout.addLayout(img_radio_layout)
        
        # CDN图片地址输入
        cdn_img_layout = QHBoxLayout()
        cdn_img_label = QLabel("CDN地址:")
        cdn_img_label.setStyleSheet("color: white;")
        cdn_img_layout.addWidget(cdn_img_label)
        
        self.jm_cdn_img_ip = QLineEdit()
        self.jm_cdn_img_ip.setText("104.18.227.172")
        self.jm_cdn_img_ip.setPlaceholderText("CDN IP地址")
        self.jm_cdn_img_ip.setFixedWidth(150)
        self.jm_cdn_img_ip.setStyleSheet("padding: 6px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        cdn_img_layout.addWidget(self.jm_cdn_img_ip)
        cdn_img_layout.addStretch()
        img_layout.addLayout(cdn_img_layout)
        
        # 图片测速按钮
        img_test_layout = QHBoxLayout()
        self.jm_img_test_btn = QPushButton("测试图片分流")
        self.jm_img_test_btn.setFixedWidth(120)
        self.jm_img_test_btn.clicked.connect(self._test_jmcomic_img)
        img_test_layout.addWidget(self.jm_img_test_btn)
        img_test_layout.addStretch()
        img_layout.addLayout(img_test_layout)
        
        layout.addWidget(img_group)
        
        # 保存按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.jm_save_btn = QPushButton("保存JMComic设置")
        self.jm_save_btn.setFixedSize(150, 36)
        self.jm_save_btn.clicked.connect(self._save_jmcomic_settings)
        self.jm_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #106ebe; }
        """)
        save_layout.addWidget(self.jm_save_btn)
        layout.addLayout(save_layout)
        
        layout.addStretch()
        
        return page
    
    def _create_download_page(self) -> QWidget:
        """创建下载设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("下载设置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 下载路径
        path_group = QGroupBox("下载路径")
        path_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        path_layout = QFormLayout(path_group)
        
        path_input_layout = QHBoxLayout()
        self.download_path = QLineEdit()
        self.download_path.setPlaceholderText("选择下载保存路径")
        self.download_path.setStyleSheet("padding: 8px; background-color: #2d2d2d; border: 1px solid #3a3a3a; color: white;")
        path_input_layout.addWidget(self.download_path)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_download_path)
        path_input_layout.addWidget(browse_btn)
        
        path_layout.addRow("保存路径:", path_input_layout)
        
        layout.addWidget(path_group)
        
        # 下载设置
        download_group = QGroupBox("下载设置")
        download_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        download_layout = QFormLayout(download_group)
        
        self.concurrent_downloads = QSpinBox()
        self.concurrent_downloads.setMinimum(1)
        self.concurrent_downloads.setMaximum(10)
        self.concurrent_downloads.setValue(3)
        self.concurrent_downloads.setSuffix(" 个")
        download_layout.addRow("并发下载数:", self.concurrent_downloads)
        
        self.auto_retry = QCheckBox("自动重试失败的下载")
        self.auto_retry.setStyleSheet("color: white;")
        self.auto_retry.setChecked(True)
        download_layout.addRow("", self.auto_retry)
        
        self.max_retries = QSpinBox()
        self.max_retries.setMinimum(0)
        self.max_retries.setMaximum(10)
        self.max_retries.setValue(3)
        self.max_retries.setSuffix(" 次")
        download_layout.addRow("最大重试次数:", self.max_retries)
        
        layout.addWidget(download_group)
        
        # 缓存设置
        cache_group = QGroupBox("缓存设置")
        cache_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; }")
        cache_layout = QFormLayout(cache_group)
        
        self.cache_size = QSpinBox()
        self.cache_size.setMinimum(10)
        self.cache_size.setMaximum(10000)
        self.cache_size.setValue(500)
        self.cache_size.setSuffix(" MB")
        self.cache_size.setSingleStep(50)
        cache_layout.addRow("缓存大小限制:", self.cache_size)
        
        layout.addWidget(cache_group)
        
        # 保存按钮
        save_btn_layout = QHBoxLayout()
        save_btn_layout.addStretch()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setFixedSize(120, 36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.save_btn.clicked.connect(self.save_settings)
        save_btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(save_btn_layout)
        layout.addStretch()
        
        return page
    
    def _create_tips_page(self) -> QWidget:
        """创建使用须知页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 语言切换
        lang_layout = QHBoxLayout()
        lang_layout.addStretch()
        
        self.tips_lang_label = QLabel("Language / 语言:")
        self.tips_lang_label.setStyleSheet("color: white; font-weight: bold;")
        lang_layout.addWidget(self.tips_lang_label)
        
        self.tips_language_combo = QComboBox()
        self.tips_language_combo.addItems(["中文", "English"])
        self.tips_language_combo.setCurrentIndex(0)
        self.tips_language_combo.currentTextChanged.connect(self._update_tips_language)
        self.tips_language_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 3px;
                min-width: 80px;
            }
        """)
        lang_layout.addWidget(self.tips_language_combo)
        layout.addLayout(lang_layout)
        
        # 标题
        self.tips_title = QLabel("使用须知")
        self.tips_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(self.tips_title)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
        """)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)
        
        # 免责声明
        self.disclaimer_group = QGroupBox()
        self.disclaimer_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; font-size: 16px; }")
        disclaimer_layout = QVBoxLayout(self.disclaimer_group)
        
        self.disclaimer_text = QLabel()
        self.disclaimer_text.setWordWrap(True)
        self.disclaimer_text.setTextFormat(Qt.RichText)
        self.disclaimer_text.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                line-height: 1.6;
                padding: 15px;
                background-color: #2a2a2a;
                border-radius: 8px;
                border-left: 4px solid #ff6b6b;
            }
        """)
        disclaimer_layout.addWidget(self.disclaimer_text)
        
        content_layout.addWidget(self.disclaimer_group)
        
        # 功能状态
        self.status_group = QGroupBox()
        self.status_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; font-size: 16px; }")
        status_layout = QVBoxLayout(self.status_group)
        
        self.status_text = QLabel()
        self.status_text.setWordWrap(True)
        self.status_text.setTextFormat(Qt.RichText)
        self.status_text.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                line-height: 1.6;
                padding: 15px;
                background-color: #2a2a2a;
                border-radius: 8px;
                border-left: 4px solid #4ecdc4;
            }
        """)
        status_layout.addWidget(self.status_text)
        
        content_layout.addWidget(self.status_group)
        
        # 反馈与支持
        self.feedback_group = QGroupBox()
        self.feedback_group.setStyleSheet("QGroupBox { font-weight: bold; color: white; font-size: 16px; }")
        feedback_layout = QVBoxLayout(self.feedback_group)
        
        self.feedback_text = QLabel()
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setTextFormat(Qt.RichText)
        self.feedback_text.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                line-height: 1.6;
                padding: 15px;
                background-color: #2a2a2a;
                border-radius: 8px;
                border-left: 4px solid #45b7d1;
            }
        """)
        feedback_layout.addWidget(self.feedback_text)
        
        content_layout.addWidget(self.feedback_group)
        
        # GitHub 链接
        github_layout = QHBoxLayout()
        github_layout.addStretch()
        
        self.github_button = QPushButton()
        self.github_button.setFixedSize(200, 40)
        self.github_button.setStyleSheet("""
            QPushButton {
                background-color: #24292e;
                color: white;
                border: 2px solid #444d56;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2f363d;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #1b1f23;
            }
        """)
        self.github_button.clicked.connect(self._open_github)
        github_layout.addWidget(self.github_button)
        github_layout.addStretch()
        
        content_layout.addLayout(github_layout)
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # 初始化文本内容
        self._update_tips_content()
        
        return page
    
    def _open_github(self):
        """打开GitHub主页"""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://github.com"))
    
    def _update_tips_language(self):
        """更新Tips页面语言"""
        self._update_tips_content()
    
    def _update_tips_content(self):
        """更新Tips页面内容"""
        is_chinese = self.tips_language_combo.currentText() == "中文"
        
        if is_chinese:
            # 中文内容
            self.tips_title.setText("使用须知")
            self.disclaimer_group.setTitle("📋 免责声明")
            self.status_group.setTitle("🚀 功能状态")
            self.feedback_group.setTitle("💬 反馈与支持")
            self.github_button.setText("🔗 访问 GitHub 主页")
            
            disclaimer_content = """
            <p><strong>PanComic</strong> 是一款免费开源的漫画阅读软件，仅供学习和研究使用。</p>
            <p><strong>重要提醒：</strong></p>
            <ul>
                <li>本软件不提供任何漫画内容，所有内容均来自第三方网站</li>
                <li>用户需自行承担使用本软件的风险和责任</li>
                <li>请遵守当地法律法规，合理使用本软件</li>
                <li>涉及成人内容时，请确保您已满18岁</li>
                <li>开发者不对软件使用产生的任何后果承担责任</li>
            </ul>
            """
            
            status_content = """
            <p><strong>✅ 已实现功能：</strong></p>
            <ul>
                <li>两个漫画源的搜索、阅读和下载功能</li>
                <li>连接了番剧wiki，可以通过关键词搜索，然后筛选搜索结果（不提供番剧视频资源）</li>
                <li>健全完善的下载管理器以及漫画阅读器</li>
            </ul>
            <p><strong>🔧 待完善功能：</strong></p>
            <ul>
                <li>两个漫画源的搜索完善（如JM号搜索）</li>
                <li>JM源稳定性修复（禁漫某次更新后反爬变强了，多次搜索后可能会遇到http0或者超市，建议优先使用哔咔）</li>
                <li>更多漫画源支持</li>
                <li>线程优化，主页面稳定性优化</li>
                <li>Gui美化完善</li>
            </ul>
            """
            
            feedback_content = """
            <p>如果您在使用过程中遇到任何问题或有改进建议，欢迎通过以下方式反馈：</p>
            <ul>
                <li><strong>GitHub Issues：</strong> 在项目仓库提交问题（尽可能上传appdata中的loggs）</li>
                <li><strong>功能建议：</strong> 提交新功能需求</li>
                <li><strong>Bug 报告：</strong> 详细描述问题复现步骤</li>
            </ul>
            <p><strong>感谢您的支持和反馈！</strong></p>
            """
        else:
            # 英文内容
            self.tips_title.setText("Usage Guidelines")
            self.disclaimer_group.setTitle("📋 Disclaimer")
            self.status_group.setTitle("🚀 Feature Status")
            self.feedback_group.setTitle("💬 Feedback & Support")
            self.github_button.setText("🔗 Visit GitHub Homepage")
            
            disclaimer_content = """
            <p><strong>ComicGo</strong> is a free and open-source comic reading software for educational and research purposes only.</p>
            <p><strong>Important Notice:</strong></p>
            <ul>
                <li>This software does not provide any comic content; all content comes from third-party websites</li>
                <li>Users are responsible for the risks and consequences of using this software</li>
                <li>Please comply with local laws and regulations when using this software</li>
                <li>For adult content, please ensure you are 18 years or older</li>
                <li>Developers are not responsible for any consequences arising from the use of this software</li>
            </ul>
            """
            
            status_content = """
            <p><strong>✅ Implemented Features:</strong></p>
            <ul>
                <li>Search, reading, and download functions for two comic sources</li>
                <li>PicACG - Full feature support</li>
                <li>JMComic - Basic feature support</li>
            </ul>
            <p><strong>🔧 Features to be Improved:</strong></p>
            <ul>
                <li>JMComic login function optimization</li>
                <li>Support for more comic sources</li>
                <li>Interface optimization and feature enhancement</li>
            </ul>
            """
            
            feedback_content = """
            <p>If you encounter any issues or have suggestions for improvement, please provide feedback through:</p>
            <ul>
                <li><strong>GitHub Issues:</strong> Submit issue reports in the project repository</li>
                <li><strong>Feature Requests:</strong> Submit new feature requirements</li>
                <li><strong>Bug Reports:</strong> Provide detailed steps to reproduce the problem</li>
            </ul>
            <p><strong>Thank you for your support and feedback!</strong></p>
            """
        
        self.disclaimer_text.setText(disclaimer_content)
        self.status_text.setText(status_content)
        self.feedback_text.setText(feedback_content)
    
    def _load_settings(self) -> None:
        """加载设置"""
        try:
            # 加载常规设置
            theme = self.config_manager.get('general.theme', 'dark')
            theme_map = {'dark': 0, 'light': 1, 'system': 2}
            self.theme_combo.setCurrentIndex(theme_map.get(theme, 0))
            
            language = self.config_manager.get('general.language', 'zh_CN')
            language_map = {'zh_CN': 0, 'en_US': 1}
            self.language_combo.setCurrentIndex(language_map.get(language, 0))
            
            self.auto_check_updates.setChecked(self.config_manager.get('general.auto_check_updates', True))
            
            # 加载PicACG设置
            if self.picacg_adapter:
                config = self.picacg_adapter.config
                credentials = config.get('credentials', {})
                
                # 从配置管理器加载设置
                self.picacg_email.setText(self.config_manager.get('picacg.email', credentials.get('email', '')))
                self.picacg_password.setText(self.config_manager.get('picacg.password', credentials.get('password', '')))
                self.picacg_auto_login.setChecked(self.config_manager.get('picacg.auto_login', False))
                
                # 设置当前API端点 (单选按钮)
                current_endpoint = self.config_manager.get('picacg.endpoint', self.picacg_adapter.get_current_endpoint())
                for i, radio in self.picacg_api_radios.items():
                    if radio.property("url") == current_endpoint:
                        radio.setChecked(True)
                        break
                
                # 设置当前图片服务器 (单选按钮)
                current_server = self.config_manager.get('picacg.image_server', self.picacg_adapter.get_current_image_server())
                for i, radio in self.picacg_img_radios.items():
                    if radio.property("server") == current_server:
                        radio.setChecked(True)
                        break
                
                # 设置图片质量
                quality = self.config_manager.get('picacg.image_quality', config.get('image_quality', 'original'))
                quality_map = {'original': 0, 'high': 1, 'medium': 2, 'low': 3}
                self.picacg_quality.setCurrentIndex(quality_map.get(quality, 0))
                
                # 检查当前登录状态
                self._update_picacg_login_status()
            
            # 加载JMComic设置
            self.jm_username.setText(self.config_manager.get('jmcomic.username', ''))
            self.jm_password.setText(self.config_manager.get('jmcomic.password', ''))
            self.jm_auto_login.setChecked(self.config_manager.get('jmcomic.auto_login', False))
            
            # 加载分流选择
            api_index = self.config_manager.get('jmcomic.api_endpoint', 5)  # 默认CDN分流
            img_index = self.config_manager.get('jmcomic.img_endpoint', 5)
            if api_index in self.jm_api_radios:
                self.jm_api_radios[api_index].setChecked(True)
            if img_index in self.jm_img_radios:
                self.jm_img_radios[img_index].setChecked(True)
            
            # 加载CDN地址
            self.jm_cdn_api_ip.setText(self.config_manager.get('jmcomic.cdn_api_ip', '104.18.227.172'))
            self.jm_cdn_img_ip.setText(self.config_manager.get('jmcomic.cdn_img_ip', '104.18.227.172'))
            
            # 加载下载设置
            download_path = self.config_manager.get('download.download_path', '')
            if not download_path:
                # 设置默认下载路径
                from pathlib import Path
                app_dir = Path(__file__).parent.parent.parent  # Go up to project root
                download_path = str(app_dir / "downloads")
                # 保存默认路径到配置
                self.config_manager.set('download.download_path', download_path)
            
            self.download_path.setText(download_path)
            self.concurrent_downloads.setValue(self.config_manager.get('download.concurrent_downloads', 3))
            self.auto_retry.setChecked(self.config_manager.get('download.auto_retry', True))
            self.max_retries.setValue(self.config_manager.get('download.max_retries', 3))
            self.cache_size.setValue(self.config_manager.get('cache.cache_size_mb', 500))
            
        except Exception as e:
            print(f"加载设置失败: {e}")
    
    def _connect_signals(self) -> None:
        """连接信号"""
        if self.picacg_adapter:
            self.picacg_adapter.login_completed.connect(self._on_picacg_login_completed, Qt.UniqueConnection)
            self.picacg_adapter.login_failed.connect(self._on_picacg_login_failed, Qt.UniqueConnection)
            self.picacg_adapter.endpoint_test_completed.connect(self._on_picacg_api_test_completed, Qt.UniqueConnection)
            self.picacg_adapter.image_server_test_completed.connect(self._on_picacg_image_test_completed, Qt.UniqueConnection)
        
        # JMComic信号
        if self.jmcomic_adapter:
            self.jmcomic_adapter.login_completed.connect(self._on_jmcomic_login_completed, Qt.UniqueConnection)
            self.jmcomic_adapter.login_failed.connect(self._on_jmcomic_login_failed, Qt.UniqueConnection)
        
        # JMComic测速信号
        self._jm_api_test_done.connect(self._on_jm_api_test_done)
        self._jm_img_test_done.connect(self._on_jm_img_test_done)
    
    def _update_picacg_login_status(self) -> None:
        """更新PicACG登录状态显示"""
        if self.picacg_adapter and self.picacg_adapter.is_logged_in():
            self.picacg_login_status.setText("已登录")
            self.picacg_login_status.setStyleSheet("color: #00aa00;")
        else:
            self.picacg_login_status.setText("未登录")
            self.picacg_login_status.setStyleSheet("color: #ff4444;")
    
    def _test_picacg_login(self) -> None:
        """测试PicACG登录"""
        if not self.picacg_adapter:
            QMessageBox.warning(self, "登录", "PicACG适配器不可用")
            return
        
        email = self.picacg_email.text().strip()
        password = self.picacg_password.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "登录", "请输入邮箱和密码")
            return
        
        print(f"🔐 PicACG设置页面开始登录: {email}")
        
        self.picacg_login_btn.setEnabled(False)
        self.picacg_login_btn.setText("登录中...")
        self.picacg_login_status.setText("登录中...")
        self.picacg_login_status.setStyleSheet("color: #ffaa00;")
        
        try:
            self.picacg_adapter.login({'email': email, 'password': password})
            print("📤 PicACG登录请求已发送")
        except Exception as e:
            print(f"❌ PicACG登录请求失败: {e}")
            self.picacg_login_btn.setEnabled(True)
            self.picacg_login_btn.setText("测试登录")
            self.picacg_login_status.setText("登录失败")
            self.picacg_login_status.setStyleSheet("color: #ff4444;")
    
    def _test_picacg_api(self) -> None:
        """测试PicACG API分流"""
        if not self.picacg_adapter:
            return
        
        self.picacg_api_test_btn.setEnabled(False)
        self.picacg_api_test_btn.setText("测试中...")
        
        # 清空之前的测速结果
        for label in self.picacg_api_labels.values():
            label.setText("测试中...")
            label.setStyleSheet("color: #ffaa00; min-width: 80px;")
        
        self.picacg_adapter.test_endpoints()
    
    def _test_picacg_image(self) -> None:
        """测试PicACG图片分流"""
        if not self.picacg_adapter:
            return
        
        self.picacg_image_test_btn.setEnabled(False)
        self.picacg_image_test_btn.setText("测试中...")
        
        # 清空之前的测速结果
        for label in self.picacg_img_labels.values():
            label.setText("测试中...")
            label.setStyleSheet("color: #ffaa00; min-width: 80px;")
        
        self.picacg_adapter.test_image_servers()
    
    def _test_jmcomic_login(self) -> None:
        """测试JMComic登录"""
        if not self.jmcomic_adapter:
            QMessageBox.warning(self, "登录", "JMComic适配器不可用")
            return
        
        username = self.jm_username.text().strip()
        password = self.jm_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "登录", "请输入用户名和密码")
            return
        
        self.jm_login_btn.setEnabled(False)
        self.jm_login_btn.setText("登录中...")
        self.jm_login_status.setText("登录中...")
        self.jm_login_status.setStyleSheet("color: #ffaa00;")
        
        # 先静默保存分流设置（不弹窗）
        self._apply_jmcomic_settings()
        
        try:
            self.jmcomic_adapter.login({'username': username, 'password': password})
        except Exception as e:
            self.jm_login_btn.setEnabled(True)
            self.jm_login_btn.setText("测试登录")
            self.jm_login_status.setText(f"登录失败: {str(e)[:20]}")
            self.jm_login_status.setStyleSheet("color: #ff4444;")
    
    def _on_jmcomic_login_completed(self, success: bool, message: str) -> None:
        """JMComic登录完成"""
        self.jm_login_btn.setEnabled(True)
        self.jm_login_btn.setText("测试登录")
        
        if success:
            self.jm_login_status.setText("已登录")
            self.jm_login_status.setStyleSheet("color: #00aa00;")
        else:
            self.jm_login_status.setText(f"登录失败")
            self.jm_login_status.setStyleSheet("color: #ff4444;")
    
    def _on_jmcomic_login_failed(self, error: str) -> None:
        """JMComic登录失败"""
        self.jm_login_btn.setEnabled(True)
        self.jm_login_btn.setText("测试登录")
        self.jm_login_status.setText("登录失败")
        self.jm_login_status.setStyleSheet("color: #ff4444;")
    
    def _test_jmcomic_api(self) -> None:
        """测试JMComic API分流"""
        import threading
        import requests
        import time
        
        self.jm_api_test_btn.setEnabled(False)
        self.jm_api_test_btn.setText("测试中...")
        
        # 清空之前的结果
        for label in self.jm_api_labels.values():
            label.setText("")
        
        # JMComic API端点列表 - CDN分流测试cdnxxx-proxy.vip域名
        api_endpoints = [
            ("https://www.cdnbea.club", 1),
            ("https://www.cdnbea.cc", 2),
            ("https://www.cdnbea.net", 3),
            ("https://www.jmapiproxyxxx.vip", 4),
            ("https://www.cdnxxx-proxy.vip", 5),  # CDN分流 - 测试域名可达性
            ("https://www.cdnxxx-proxy.vip", 6),  # US反代
        ]
        
        def test_endpoint(url, index):
            try:
                headers = {'User-Agent': 'okhttp/3.8.1'}
                start = time.time()
                resp = requests.get(url, timeout=5, verify=False, headers=headers)
                elapsed = (time.time() - start) * 1000
                if resp.status_code < 500:
                    return index, elapsed
                return index, -1
            except Exception as e:
                print(f"API测速失败 {url}: {e}")
                return index, -1
        
        def run_tests():
            import urllib3
            urllib3.disable_warnings()
            
            results = {}
            for url, idx in api_endpoints:
                idx_result, time_ms = test_endpoint(url, idx)
                results[idx_result] = time_ms
            
            # 使用信号更新UI
            self._jm_api_test_done.emit(results)
        
        threading.Thread(target=run_tests, daemon=True).start()
    
    # 信号定义需要在类级别，这里用方法内更新
    def _on_jm_api_test_done(self, results: dict) -> None:
        """更新JMComic API测试结果"""
        self.jm_api_test_btn.setEnabled(True)
        self.jm_api_test_btn.setText("测试API分流")
        
        for idx, time_ms in results.items():
            if idx in self.jm_api_labels:
                if time_ms > 0:
                    self.jm_api_labels[idx].setText(f"<font color='#7fb80e'>{int(time_ms)}ms</font>")
                else:
                    self.jm_api_labels[idx].setText("<font color='#d71345'>失败</font>")
    
    def _test_jmcomic_img(self) -> None:
        """测试JMComic图片分流"""
        import threading
        import requests
        import time
        
        self.jm_img_test_btn.setEnabled(False)
        self.jm_img_test_btn.setText("测试中...")
        
        for label in self.jm_img_labels.values():
            label.setText("")
        
        # 图片服务器列表 - 直接测试域名
        img_endpoints = [
            ("https://cdn-msp.jmapinodeudzn.net", 1),
            ("https://cdn-msp2.jmapinodeudzn.net", 2),
            ("https://cdn-msp.jmapiproxy3.cc", 3),
            ("https://cdn-msp.jmapiproxy4.cc", 4),
            ("https://cdn-msp.jmapiproxy3.cc", 5),  # CDN分流
            ("https://cdn-msp.jmapiproxy3.cc", 6),  # US反代
        ]
        
        def test_endpoint(url, index):
            try:
                headers = {'User-Agent': 'okhttp/3.8.1'}
                start = time.time()
                resp = requests.get(url, timeout=5, verify=False, headers=headers)
                elapsed = (time.time() - start) * 1000
                if resp.status_code < 500:
                    return index, elapsed
                return index, -1
            except Exception as e:
                print(f"图片测速失败 {url}: {e}")
                return index, -1
        
        def run_tests():
            import urllib3
            urllib3.disable_warnings()
            
            results = {}
            for url, idx in img_endpoints:
                idx_result, time_ms = test_endpoint(url, idx)
                results[idx_result] = time_ms
            
            self._jm_img_test_done.emit(results)
        
        threading.Thread(target=run_tests, daemon=True).start()
    
    def _on_jm_img_test_done(self, results: dict) -> None:
        """更新JMComic图片测试结果"""
        self.jm_img_test_btn.setEnabled(True)
        self.jm_img_test_btn.setText("测试图片分流")
        
        for idx, time_ms in results.items():
            if idx in self.jm_img_labels:
                if time_ms > 0:
                    self.jm_img_labels[idx].setText(f"<font color='#7fb80e'>{int(time_ms)}ms</font>")
                else:
                    self.jm_img_labels[idx].setText("<font color='#d71345'>失败</font>")
    
    def _apply_jmcomic_settings(self) -> None:
        """应用JMComic分流设置到适配器（不弹窗）"""
        try:
            api_index = self.jm_api_group.checkedId()
            img_index = self.jm_img_group.checkedId()
            cdn_api_ip = self.jm_cdn_api_ip.text().strip()
            cdn_img_ip = self.jm_cdn_img_ip.text().strip()
            
            print(f"[Settings] 应用JMComic设置: API={api_index}, IMG={img_index}, CDN_API={cdn_api_ip}, CDN_IMG={cdn_img_ip}")
            print(f"[Settings] jmcomic_adapter: {self.jmcomic_adapter}, initialized: {self.jmcomic_adapter._is_initialized if self.jmcomic_adapter else 'N/A'}")
            
            # 更新适配器配置
            if self.jmcomic_adapter:
                self.jmcomic_adapter.config['api_endpoint'] = api_index
                self.jmcomic_adapter.config['img_endpoint'] = img_index
                self.jmcomic_adapter.config['cdn_api_ip'] = cdn_api_ip
                self.jmcomic_adapter.config['cdn_img_ip'] = cdn_img_ip
                
                # 更新JMComic原版Setting
                self.jmcomic_adapter.update_proxy_settings(api_index, img_index, cdn_api_ip, cdn_img_ip)
            else:
                print("[Settings] jmcomic_adapter 为 None!")
        except Exception as e:
            import traceback
            print(f"应用JMComic设置失败: {e}")
            traceback.print_exc()
    
    def _save_jmcomic_settings(self) -> None:
        """保存JMComic设置"""
        try:
            # 保存登录信息
            self.config_manager.set('jmcomic.username', self.jm_username.text().strip())
            self.config_manager.set('jmcomic.password', self.jm_password.text().strip())
            self.config_manager.set('jmcomic.auto_login', self.jm_auto_login.isChecked())
            
            # 保存分流选择
            api_index = self.jm_api_group.checkedId()
            img_index = self.jm_img_group.checkedId()
            self.config_manager.set('jmcomic.api_endpoint', api_index)
            self.config_manager.set('jmcomic.img_endpoint', img_index)
            
            # 保存CDN地址
            self.config_manager.set('jmcomic.cdn_api_ip', self.jm_cdn_api_ip.text().strip())
            self.config_manager.set('jmcomic.cdn_img_ip', self.jm_cdn_img_ip.text().strip())
            
            # 应用设置到适配器
            self._apply_jmcomic_settings()
            
            self.config_manager.save_config()
            QMessageBox.information(self, "保存成功", "JMComic设置已保存")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存设置失败: {e}")
    
    def _browse_download_path(self) -> None:
        """浏览下载路径"""
        current_path = self.download_path.text()
        if not current_path:
            current_path = str(Path.home() / "Downloads")
        
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择下载路径",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.download_path.setText(directory)
    
    def _on_picacg_login_completed(self, success: bool, message: str) -> None:
        """PicACG登录完成"""
        print(f"📥 PicACG设置页面收到登录完成信号: success={success}, message={message}")
        
        self.picacg_login_btn.setEnabled(True)
        self.picacg_login_btn.setText("测试登录")
        
        if success:
            print("✅ PicACG登录成功")
            self.picacg_login_status.setText("已登录")
            self.picacg_login_status.setStyleSheet("color: #00aa00;")
        else:
            print(f"❌ PicACG登录失败: {message}")
            self.picacg_login_status.setText("登录失败")
            self.picacg_login_status.setStyleSheet("color: #ff4444;")
    
    def _on_picacg_login_failed(self, error: str) -> None:
        """PicACG登录失败"""
        print(f"📥 PicACG设置页面收到登录失败信号: {error}")
        
        self.picacg_login_btn.setEnabled(True)
        self.picacg_login_btn.setText("测试登录")
        self.picacg_login_status.setText("登录失败")
        self.picacg_login_status.setStyleSheet("color: #ff4444;")
    
    def _on_picacg_api_test_completed(self, results: Dict[str, float]) -> None:
        """PicACG API测试完成"""
        self.picacg_api_test_btn.setEnabled(True)
        self.picacg_api_test_btn.setText("测试API分流")
        
        if not results:
            # 测试失败，显示错误
            for label in self.picacg_api_labels.values():
                label.setText("失败")
                label.setStyleSheet("color: #ff4444; min-width: 80px;")
            return
        
        # 更新每个端点的测速结果
        fastest_time = float('inf')
        fastest_index = -1
        
        for i, radio in self.picacg_api_radios.items():
            url = radio.property("url")
            if url in results:
                time_ms = results[url]
                if time_ms > 0:
                    self.picacg_api_labels[i].setText(f"{int(time_ms)}ms")
                    self.picacg_api_labels[i].setStyleSheet("color: #00aa00; min-width: 80px;")
                    if time_ms < fastest_time:
                        fastest_time = time_ms
                        fastest_index = i
                else:
                    self.picacg_api_labels[i].setText("失败")
                    self.picacg_api_labels[i].setStyleSheet("color: #ff4444; min-width: 80px;")
            else:
                self.picacg_api_labels[i].setText("")
                self.picacg_api_labels[i].setStyleSheet("color: #888888; min-width: 80px;")
        
        # 自动选择最快的端点
        if fastest_index >= 0:
            self.picacg_api_radios[fastest_index].setChecked(True)
    
    def _on_picacg_image_test_completed(self, results: Dict[str, float]) -> None:
        """PicACG图片服务器测试完成"""
        self.picacg_image_test_btn.setEnabled(True)
        self.picacg_image_test_btn.setText("测试图片分流")
        
        if not results:
            # 测试失败，显示错误
            for label in self.picacg_img_labels.values():
                label.setText("失败")
                label.setStyleSheet("color: #ff4444; min-width: 80px;")
            return
        
        # 更新每个服务器的测速结果
        fastest_time = float('inf')
        fastest_index = -1
        
        for i, radio in self.picacg_img_radios.items():
            server = radio.property("server")
            if server in results:
                time_ms = results[server]
                if time_ms > 0:
                    self.picacg_img_labels[i].setText(f"{int(time_ms)}ms")
                    self.picacg_img_labels[i].setStyleSheet("color: #00aa00; min-width: 80px;")
                    if time_ms < fastest_time:
                        fastest_time = time_ms
                        fastest_index = i
                else:
                    self.picacg_img_labels[i].setText("失败")
                    self.picacg_img_labels[i].setStyleSheet("color: #ff4444; min-width: 80px;")
            else:
                self.picacg_img_labels[i].setText("")
                self.picacg_img_labels[i].setStyleSheet("color: #888888; min-width: 80px;")
        
        # 自动选择最快的服务器
        if fastest_index >= 0:
            self.picacg_img_radios[fastest_index].setChecked(True)
    
    def save_settings(self) -> None:
        """保存所有设置"""
        try:
            # 保存常规设置
            theme_map = {0: 'dark', 1: 'light', 2: 'system'}
            self.config_manager.set('general.theme', theme_map[self.theme_combo.currentIndex()])
            
            language_map = {0: 'zh_CN', 1: 'en_US'}
            self.config_manager.set('general.language', language_map[self.language_combo.currentIndex()])
            
            self.config_manager.set('general.auto_check_updates', self.auto_check_updates.isChecked())
            
            # 保存PicACG设置
            if self.picacg_adapter:
                email = self.picacg_email.text().strip()
                password = self.picacg_password.text().strip()
                
                if email and password:
                    self.picacg_adapter.config['credentials'] = {
                        'email': email,
                        'password': password
                    }
                
                # 保存自动登录设置
                self.config_manager.set('picacg.auto_login', self.picacg_auto_login.isChecked())
                self.config_manager.set('picacg.email', email)
                self.config_manager.set('picacg.password', password)
                
                # 保存端点设置 (从单选按钮获取)
                checked_api_id = self.picacg_api_group.checkedId()
                if checked_api_id >= 0 and checked_api_id in self.picacg_api_radios:
                    endpoint = self.picacg_api_radios[checked_api_id].property("url")
                    self.picacg_adapter.set_endpoint(endpoint)
                    self.config_manager.set('picacg.endpoint', endpoint)
                
                # 保存图片服务器设置 (从单选按钮获取)
                checked_img_id = self.picacg_img_group.checkedId()
                if checked_img_id >= 0 and checked_img_id in self.picacg_img_radios:
                    server = self.picacg_img_radios[checked_img_id].property("server")
                    self.picacg_adapter.set_image_server(server)
                    self.config_manager.set('picacg.image_server', server)
                
                # 保存图片质量
                quality_map = {0: 'original', 1: 'high', 2: 'medium', 3: 'low'}
                quality = quality_map[self.picacg_quality.currentIndex()]
                self.picacg_adapter.config['image_quality'] = quality
                self.config_manager.set('picacg.image_quality', quality)
            
            # 保存下载设置
            self.config_manager.set('download.download_path', self.download_path.text().strip())
            self.config_manager.set('download.concurrent_downloads', self.concurrent_downloads.value())
            self.config_manager.set('download.auto_retry', self.auto_retry.isChecked())
            self.config_manager.set('download.max_retries', self.max_retries.value())
            self.config_manager.set('cache.cache_size_mb', self.cache_size.value())
            
            # 保存配置文件
            self.config_manager.save_config()
            
            # 发送保存信号
            self.settings_saved.emit()
            
            print("✅ 设置已保存")
            
        except Exception as e:
            print(f"❌ 保存设置失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存设置失败: {e}")
    
    def _on_save_clicked(self) -> None:
        """保存按钮点击处理"""
        self.save_settings()
        QMessageBox.information(self, "保存成功", "设置已保存")
    
    def _on_setting_changed(self) -> None:
        """设置项发生变化时的处理"""
        # 延迟保存，避免频繁保存
        if not hasattr(self, '_save_timer'):
            from PySide6.QtCore import QTimer
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._auto_save)
        
        self._save_timer.start(1000)  # 1秒后自动保存
    
    def _auto_save(self) -> None:
        """自动保存设置"""
        try:
            self.save_settings()
            print("🔄 设置已自动保存")
        except Exception as e:
            print(f"⚠️ 自动保存失败: {e}")
    
    def navigate_to_picacg(self) -> None:
        """导航到PicACG设置页面"""
        self.nav_list.setCurrentRow(1)  # PicACG是第二个项目（索引1）
    
    def navigate_to_jmcomic(self) -> None:
        """导航到JMComic设置页面"""
        self.nav_list.setCurrentRow(2)  # JMComic是第三个项目（索引2）
    
    def _clear_cache(self) -> None:
        """清除图片缓存"""
        import shutil
        
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认清除", 
            "确定要清除所有图片缓存吗？\n这不会影响已下载的漫画。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # 获取缓存目录
            if hasattr(self, 'config_manager'):
                # 从app.py获取缓存路径
                import sys
                if sys.platform == 'win32':
                    cache_dir = Path.home() / 'AppData' / 'Roaming' / 'PanComic' / 'cache'
                elif sys.platform == 'darwin':
                    cache_dir = Path.home() / 'Library' / 'Application Support' / 'PanComic' / 'cache'
                else:
                    cache_dir = Path.home() / '.config' / 'pancomic' / 'cache'
                
                if cache_dir.exists():
                    # 计算缓存大小
                    total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
                    size_mb = total_size / (1024 * 1024)
                    
                    # 清除缓存
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    
                    QMessageBox.information(
                        self, 
                        "清除成功", 
                        f"已清除 {size_mb:.2f} MB 缓存"
                    )
                else:
                    QMessageBox.information(self, "提示", "缓存目录为空")
        except Exception as e:
            QMessageBox.critical(self, "清除失败", f"清除缓存失败: {e}")
    
    def _clear_logs(self) -> None:
        """清除日志文件"""
        import shutil
        
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认清除", 
            "确定要清除所有日志文件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # 获取日志目录
            import sys
            if sys.platform == 'win32':
                logs_dir = Path.home() / 'AppData' / 'Roaming' / 'PanComic' / 'logs'
            elif sys.platform == 'darwin':
                logs_dir = Path.home() / 'Library' / 'Application Support' / 'PanComic' / 'logs'
            else:
                logs_dir = Path.home() / '.config' / 'pancomic' / 'logs'
            
            if logs_dir.exists():
                # 计算日志大小
                total_size = sum(f.stat().st_size for f in logs_dir.rglob('*') if f.is_file())
                size_kb = total_size / 1024
                file_count = len(list(logs_dir.rglob('*')))
                
                # 清除日志
                shutil.rmtree(logs_dir)
                logs_dir.mkdir(parents=True, exist_ok=True)
                
                QMessageBox.information(
                    self, 
                    "清除成功", 
                    f"已清除 {file_count} 个日志文件 ({size_kb:.2f} KB)"
                )
            else:
                QMessageBox.information(self, "提示", "日志目录为空")
        except Exception as e:
            QMessageBox.critical(self, "清除失败", f"清除日志失败: {e}")

    def apply_theme(self, theme: str) -> None:
        """Apply theme to settings page components."""
        if theme == 'light':
            # Light theme colors
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
        else:
            # Dark theme colors
            bg_primary = '#1e1e1e'
            bg_secondary = '#2d2d2d'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
        
        # Navigation list
        self.nav_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {bg_secondary};
                border: none;
                border-right: 1px solid {border_color};
            }}
            QListWidget::item {{
                padding: 12px 16px;
                color: {text_primary};
                border: none;
            }}
            QListWidget::item:hover {{
                background-color: {border_color};
            }}
            QListWidget::item:selected {{
                background-color: {accent_color};
                color: white;
            }}
        """)
        
        # Content stack - apply to all child widgets
        self.content_stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {bg_primary};
            }}
            QGroupBox {{
                font-weight: bold;
                color: {text_primary};
            }}
            QCheckBox {{
                color: {text_primary};
            }}
            QRadioButton {{
                color: {text_primary};
            }}
            QLabel {{
                color: {text_primary};
            }}
        """)
        
        # Update PicACG API radio buttons
        if hasattr(self, 'picacg_api_radios'):
            for radio in self.picacg_api_radios.values():
                radio.setStyleSheet(f"color: {text_primary};")
        
        # Update PicACG image radio buttons
        if hasattr(self, 'picacg_img_radios'):
            for radio in self.picacg_img_radios.values():
                radio.setStyleSheet(f"color: {text_primary};")
        
        # Update PicACG API labels
        if hasattr(self, 'picacg_api_labels'):
            for label in self.picacg_api_labels.values():
                current_text = label.text()
                if 'ms' in current_text:
                    label.setStyleSheet(f"color: #00aa00; min-width: 80px;")
                elif '失败' in current_text:
                    label.setStyleSheet(f"color: #ff4444; min-width: 80px;")
                else:
                    label.setStyleSheet(f"color: {text_muted}; min-width: 80px;")
        
        # Update PicACG image labels
        if hasattr(self, 'picacg_img_labels'):
            for label in self.picacg_img_labels.values():
                current_text = label.text()
                if 'ms' in current_text:
                    label.setStyleSheet(f"color: #00aa00; min-width: 80px;")
                elif '失败' in current_text:
                    label.setStyleSheet(f"color: #ff4444; min-width: 80px;")
                else:
                    label.setStyleSheet(f"color: {text_muted}; min-width: 80px;")
        
        # Update JMComic API radio buttons
        if hasattr(self, 'jm_api_radios'):
            for radio in self.jm_api_radios.values():
                radio.setStyleSheet(f"color: {text_primary};")
        
        # Update JMComic image radio buttons
        if hasattr(self, 'jm_img_radios'):
            for radio in self.jm_img_radios.values():
                radio.setStyleSheet(f"color: {text_primary};")
        
        # Update JMComic API labels
        if hasattr(self, 'jm_api_labels'):
            for label in self.jm_api_labels.values():
                # Keep the color based on content (green for success, red for failure)
                current_text = label.text()
                if 'ms' in current_text:
                    label.setStyleSheet(f"color: #00aa00; min-width: 80px;")
                elif '失败' in current_text:
                    label.setStyleSheet(f"color: #ff4444; min-width: 80px;")
                else:
                    label.setStyleSheet(f"color: {text_muted}; min-width: 80px;")
        
        # Update JMComic image labels
        if hasattr(self, 'jm_img_labels'):
            for label in self.jm_img_labels.values():
                current_text = label.text()
                if 'ms' in current_text:
                    label.setStyleSheet(f"color: #00aa00; min-width: 80px;")
                elif '失败' in current_text:
                    label.setStyleSheet(f"color: #ff4444; min-width: 80px;")
                else:
                    label.setStyleSheet(f"color: {text_muted}; min-width: 80px;")
        
        # Update CDN labels
        if hasattr(self, 'jm_cdn_api_ip'):
            pass  # Keep input style as is per user request
        if hasattr(self, 'jm_cdn_img_ip'):
            pass  # Keep input style as is per user request
        
        # Update PicACG auto login checkbox
        if hasattr(self, 'picacg_auto_login'):
            self.picacg_auto_login.setStyleSheet(f"color: {text_primary};")
        
        # Update JMComic auto login checkbox
        if hasattr(self, 'jm_auto_login'):
            self.jm_auto_login.setStyleSheet(f"color: {text_primary};")
        
        # Update general settings auto check updates checkbox
        if hasattr(self, 'auto_check_updates'):
            self.auto_check_updates.setStyleSheet(f"color: {text_primary};")
        
        # Update download settings auto retry checkbox
        if hasattr(self, 'auto_retry'):
            self.auto_retry.setStyleSheet(f"color: {text_primary};")
        
        # Update tips page components
        if hasattr(self, 'tips_title'):
            self.tips_title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {text_primary}; margin-bottom: 20px;")
        
        # Tips language label
        if hasattr(self, 'tips_lang_label'):
            self.tips_lang_label.setStyleSheet(f"color: {text_primary}; font-weight: bold;")
        
        # Tips language combo
        if hasattr(self, 'tips_language_combo'):
            self.tips_language_combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: {bg_secondary};
                    color: {text_primary};
                    border: 1px solid {border_color};
                    padding: 5px;
                    border-radius: 3px;
                    min-width: 80px;
                }}
                QComboBox:hover {{
                    border: 1px solid {accent_color};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 25px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 4px solid {text_primary};
                    margin-right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {bg_secondary};
                    border: 1px solid {border_color};
                    selection-background-color: {accent_color};
                    color: {text_primary};
                }}
            """)
        
        # Tips text areas
        tips_bg = '#F5F5F5' if theme == 'light' else '#2a2a2a'
        tips_text_color = '#333333' if theme == 'light' else '#cccccc'
        
        if hasattr(self, 'disclaimer_text'):
            self.disclaimer_text.setStyleSheet(f"""
                QLabel {{
                    color: {tips_text_color};
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 15px;
                    background-color: {tips_bg};
                    border-radius: 8px;
                    border-left: 4px solid #ff6b6b;
                }}
            """)
        
        if hasattr(self, 'status_text'):
            self.status_text.setStyleSheet(f"""
                QLabel {{
                    color: {tips_text_color};
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 15px;
                    background-color: {tips_bg};
                    border-radius: 8px;
                    border-left: 4px solid #4ecdc4;
                }}
            """)
        
        if hasattr(self, 'feedback_text'):
            self.feedback_text.setStyleSheet(f"""
                QLabel {{
                    color: {tips_text_color};
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 15px;
                    background-color: {tips_bg};
                    border-radius: 8px;
                    border-left: 4px solid #45b7d1;
                }}
            """)
        
        # GitHub button
        if hasattr(self, 'github_button'):
            if theme == 'light':
                self.github_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f6f8fa;
                        color: #24292e;
                        border: 1px solid #e1e4e8;
                        border-radius: 6px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #e1e4e8;
                        border-color: #d1d5da;
                    }
                    QPushButton:pressed {
                        background-color: #d1d5da;
                    }
                """)
            else:
                self.github_button.setStyleSheet("""
                    QPushButton {
                        background-color: #24292e;
                        color: white;
                        border: 2px solid #444d56;
                        border-radius: 6px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #2f363d;
                        border-color: #586069;
                    }
                    QPushButton:pressed {
                        background-color: #1b1f23;
                    }
                """)
