# PanComic

⚡ 一个简洁、高性能、支持多源的本地化漫画管理器（下载 + 阅读）


```❤做此项目本意是为了测试Glm4.7以及traesolo模式的实力，可惜用了一段时间发现上下文能力太差，一百多k就会胡言乱语，但它生成的阅读器非常好用，以及api封装/apdater适配的结构也很适合继续编写，所以就从Glm那里接手继续开发了，希望大伙喜欢❤```


## ✨ 功能特性

- 🔍 **多源搜索** - 支持众多漫画源
- 📖 **在线阅读** - 流畅的阅读体验，健全的阅读器功能，支持缓存加速
- 📥 **批量下载** - 智能下载队列，支持断点续传
- 📚 **本地管理** - 完善的本地漫画库管理
- 🎨 **现代界面** - Fluent Design 风格 UI

## 📸 截图

深色模式
![示例图片](example1.png)
浅色模式
![示例图片](example2.png)

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/PanComic.git
cd PanComic

# 安装依赖
pip install -r pancomic/requirements.txt

# 运行
python -m pancomic.main

# 自行打包（确保包含了PanComic.spec文件）
pyinstaller PanComic.spec --clean
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
├── forapi/                # API 封装
│   ├── jmcomic/           # JMComic API
│   └── picacg/            # PicACG API
└── downloads/             # 下载目录（首次运行生成）
```

## 🤔 待更新功能（无优先级）

- [ √ ]优化搜索结果加载，搜索占用独立线程，打算使用lazy load加载结果
- [ x ]优化jmcomic搜素，以支持jm号搜索
- [ x ]优化picacg搜索功能（未知原因导致搜索结果只有前20条）
- [ x ]优化动漫搜索功能，制作视频观看器，寻找有公开api的动漫视频源，目前接入的bangumi是动漫wiki网站，不提供动漫视频资源（找到一个库https://github.com/sdaqo/anipy-cli?tab=readme-ov-file，或许可用？🤔）
- [ x ]Gui美化，渐变，操作响应强化，任务状态弹出信息条
- [√/×]扩充更多漫画源（添加中....）
- [ √ ]增加漫画源自定义热插拔功能，以浏览器标签页形式让用户自行选择主界面漫画源


   - 已支持的漫画源
     
                       - 禁漫天堂
                       - 哔咔漫画 
                       - 绅士漫画（wnacg.com）

   - 准备更新的漫画源：

                       - 拷贝漫画（2025copy.com）
                       - ehentai(exhentai.org)
                       - BZ漫画（mangabz.com）
     
     
  

## 🖊 更新日志

- 2025/12/27  上传了项目源码与预发行release-v0.1.0
- 2025/12/28  增加了漫画源-绅士漫画、增加了漫画源热插拔功能、编写了add_comicsource_rule.md，为后续漫画源添加确立工作顺序、优化了部分线程、强化了阅读器以及资源库的兼容性、强化了资源库，现在可以拖动带图文件夹到”我的漫画“区域，它会自动生成/user文件夹，保存主动导入的本地漫画。


## ⚠️ 免责声明

- 本项目仅供学习和研究使用
- 不提供任何漫画内容，所有内容来自第三方
- 请遵守当地法律法规
- 涉及成人内容时，请确保已满 18 岁