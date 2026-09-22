# PPTVideoStudio — Windows 桌面端（MVP 全流程已跑通）

目标：
- 输入主题/内容 → AI 生成 PPT（可编辑 PPTX，含演讲者备注）
- 上传 PPT → 生成解说词 → TTS 配音 → 导出 PPT 讲解视频（MP4 + SRT）
- Windows 端可双击安装/启动

当前状态：**全链路已在开发机验证通过**（生成 → 讲稿 → 配音 → 合成 1080p MP4）。

## 目录
```
PPTVideoStudio/
├─ desktop/        # Electron + React 桌面壳（5 个视图，全部对接真实 API）
├─ backend/        # FastAPI 本地服务（真实引擎，非占位）
│  └─ app/services/
│     ├─ outline.py      # 主题→大纲（LLM 可选，模板兜底）
│     ├─ ppt_builder.py  # python-pptx 可编辑 PPTX（深蓝+金色主题）
│     ├─ render.py       # Pillow 渲染 1920x1080 页面图（soffice 高保真钩子）
│     ├─ script_gen.py   # 逐页解说词（LLM 可选，模板兜底）
│     ├─ tts.py          # Edge-TTS 逐页配音（静音兜底）
│     └─ video.py        # FFmpeg 合成 MP4（淡入淡出+字幕烧录+SRT）
├─ scripts/start_dev.bat   # Windows 一键启动开发环境
└─ .github/workflows/build-windows.yml  # Windows 安装包 CI（NSIS exe）
```

## 快速启动（开发模式）
Windows：双击 `scripts\start_dev.bat`（自动建 venv、装依赖、起前后端）。

手动：
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main          # 127.0.0.1:8000

cd ../desktop
npm install
npm run dev                 # 桌面窗口自动弹出
```

Mac/Linux 开发同理（`python3 -m app.main`）。

## 已验证的完整流程
1. 首页输入主题 → 创建项目 → AI 生成 6~N 页 PPT（可编辑 PPTX + 页面图）
2. 编辑页改标题/要点 → 保存即重建 PPTX；一键生成逐页解说词（自动写入 PPT 备注）
3. 配音页选音色/语速 → Edge-TTS 逐页合成，可逐页试听
4. 视频页选分辨率/帧率/转场/字幕 → 后台合成 → 进度条 → 下载 MP4（含烧录字幕）
5. 设置页可配任意 OpenAI 兼容 LLM（OpenAI/DeepSeek/通义/Ollama），不配置也能全流程运行

## 验证产物（本机实测）
- `output.pptx`：6 页，真文本框可编辑，每页含演讲者备注
- `*.mp4`：1920x1080 H.264 + AAC，约 94 秒，字幕已烧录
- `*.srt`：独立字幕文件

## Windows 打包
推送 `v*` 标签到 GitHub 即自动构建 NSIS 安装包（见 workflow）：
- PyInstaller 打包后端为 exe
- FFmpeg 随包分发
- electron-builder 出安装程序

Mac 上开发、CI 出 Windows 包，无需本地 Windows 机器。

## 二期路线
- 导入 PPT 的高保真渲染（Windows 端接 PowerPoint COM）
- 数字人讲解（SadTalker/ Folk 后续）
- 声音克隆、背景音乐、批量生成
