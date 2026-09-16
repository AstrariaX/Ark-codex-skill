# Codex 桌宠

明日方舟 Arknights 透明桌面宠物，跟随 Claude Code / Codex 运行状态。支持 Windows 和 macOS。

## 快速开始

```bash
# Windows
双击 启动桌宠.bat

# macOS
python main.py
```

依赖在 `.venv` 内，不影响全局环境。

## 功能

### 基础交互
- **单击**：互动动画 / 显示随机台词气泡
- **双击**：切换迷你模式
- **拖动**：走路动画，松开回到之前状态
- **右键菜单**：坐下/放松/睡觉/动画组/桌宠库/设置/缩放/隐藏/退出
- **锁定拖动**：防止误触移动

### 动画系统
- **多动画组**：基建/正面/战斗等，右键切换
- **60fps 渲染**：预缩放帧缓存，整数坐标消除运动模糊
- **Alpha 降噪**：WebM 压缩噪点在 PNG 导出时自动清除
- **动画预览**：动作设置面板内实时预览各动画
- **轴线编辑器**：带动画播放、暂停、时间轴拖动的地面线调整

### 对话气泡
- 待机/点击时随机弹出台词
- 从 PRTS Wiki 自动获取角色语音文本
- 支持自定义博士名称替换

### 多宠物
- 同屏多角色，各自独立行为
- 库尔洛夫斥力防重叠
- 各角色独立记忆位置/缩放/速度

### 状态字幕
- 简短/标准/详细三档
- 显示 Codex 运行状态、模型、Token、进度

### 系统集成
- **自启动**：Windows 注册表 / macOS LaunchAgent
- **全屏自动隐藏**：检测全屏应用自动隐藏
- **穿透模式**：Ctrl+Shift+T 切换鼠标穿透（Windows）
- **系统托盘**：显示/隐藏/退出

## 架构

```
main.py              PetWindow 核心 + 入口点
config.py            常量/路径/设置
manifest.py          动画 manifest 加载
dialogs.py           设置对话框
tray.py              系统托盘
bubble.py            气泡组件
fetch_worker.py      PRTS 下载线程
prts.py              PRTS Wiki API
sound.py             音效
screen.py            屏幕几何
platform_base.py     平台抽象接口
platform_win.py      Windows 实现
platform_mac.py      macOS 实现
behavior.py          行为状态机
physics.py           2D 物理引擎
codex_monitor.py     Codex 状态监控
window_detect.py     窗口检测
```

## 跨平台

| 功能 | Windows | macOS |
|---|---|---|
| 自启动 | 注册表 Run key | LaunchAgent plist |
| 穿透点击 | WS_EX_TRANSPARENT | WA_TransparentForMouseEvents |
| 全屏检测 | Win32 GetForegroundWindow | (待完善) |
| 全局热键 | RegisterHotKey Ctrl+Shift+T | (待完善) |
| 窗口模式 | Qt.Tool | Qt.Window |

## 设置

右键 → 设置：动作倍速 / 字幕长度 / 字幕大小 / 字条长度 / 迷你模式 / 全屏自动隐藏 / 自启动 / 行为参数 / 音效 / 描边 / 博士名称

## 桌宠库

角色在 `pets/` 下，每个包含 `manifest.json` + `frames/` + `webm/`。通过 Ark Codex Skill 从 PRTS 自动生成。
