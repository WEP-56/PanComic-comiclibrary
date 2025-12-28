# PanComic

一个基于 PySide6 的跨平台漫画聚合阅读与下载工具，支持多个漫画源。

## ✨ 功能特性

- 🔍 **多源搜索** - 支持 PicACG、JMComic 等漫画源
- 📖 **在线阅读** - 流畅的阅读体验，支持缓存加速
- 📥 **批量下载** - 智能下载队列，支持断点续传
- 📚 **本地管理** - 完善的本地漫画库管理
- 🎨 **现代界面** - Fluent Design 风格 UI
- ⚙️ **灵活配置** - API 分流测速、图片服务器选择

## 📸 截图

<!\example1.png>   <!\example2.png>

## 🚀 快速开始

### 环境要求

- Python 3.10+

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/PanComic.git
cd PanComic

# 安装依赖
pip install -r pancomic/requirements.txt

# 运行
python -m pancomic.main
```

## 📁 项目结构

```
PanComic/
├── pancomic/              # 主程序
│   ├── adapters/          # 漫画源适配器
│   ├── controllers/       # 控制器
│   ├── core/              # 核心模块
│   ├── models/            # 数据模型
│   ├── ui/                # 用户界面
│   │   ├── pages/         # 页面
│   │   ├── widgets/       # 组件
│   │   └── dialogs/       # 对话框
│   └── infrastructure/    # 基础设施
├── forapi/                # API 相关方法封装
│   ├── jmcomic/           # JMComic API
│   └── picacg/            # PicACG API
│   └── wnacg_source,py    # 绅士漫画 API
└── downloads/             # 下载目录
```

## ⚠️ 免责声明

- 本项目仅供学习和研究使用
- 不提供任何漫画内容，所有内容来自第三方
- 请遵守当地法律法规
- 涉及成人内容时，请确保已满 18 岁

## 🙏 致谢

本项目基于以下开源项目：

- [picacg-qttext](https://github.com/847361092/picacg-qttext) - PicACG Qt 客户端
- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) - JMComic Python API

## 📄 License

MIT License
