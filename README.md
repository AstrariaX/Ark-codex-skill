# Ark Codex Skill

用 AI 辅助制作的一个用于制作《明日方舟》透明桌面宠物的 Claude Code / Codex skill。给它一个干员名（可选皮肤名），它会自动从 PRTS Wiki 导出该干员的 WebM 动画，转换成带透明通道的 PNG 帧，生成桌宠并加入桌宠库。

借鉴了 [Ark-Pets](https://github.com/isHarryh/Ark-Pets) 的 AnimStage 多动画组架构概念。

> 仓库：[AstrariaX/Ark-codex-skill](https://github.com/AstrariaX/Ark-codex-skill)

## 功能特性

- 自动检索 PRTS 干员页面并加载”干员模型”查看器
- 默认使用原皮（默认时装），也可指定任意时装组
- 支持多动画组：基建、正面、背面，各组有独立动画集，可多选激活
- 自动跳过 PRTS 导出的坏文件（`Default` 经常是 110 字节空文件）
- 动态状态映射：Skill、Die、Start、Attack 等动画从文件名自动提取，无需硬编码
- 将 WebM 抽帧为 1000×1000、60fps 的透明 PNG，自动计算包围盒并生成 `manifest.json`
- 支持同时运行多个角色，各自独立行为状态
- 统一角色管理面板：查看已有角色及动画组、下载新角色或为已有角色补充动画组
- 动作设置面板：每个动画可独立设置循环或一次性播放
- 马尔可夫状态机驱动角色自主行为（idle → walk → sit → sleep 等）
- 2D 物理引擎：重力下落、多显示器边界、宠物间斥力
- 音效系统：落地音效、点击音效，可调音量
- 系统托盘：Claude Code / Codex 运行时拉起托盘进程，也可脱离宿主程序手动启动
- 一键生成桌面和开始菜单的”打开桌宠 / 启动托盘”快捷方式
- 项目模板初始自带予愿安洁莉娜，生成后可以直接启动
- 轮廓描边、透明穿透、迷你模式、全屏自动隐藏
- 按角色记忆位置/大小/倍速，支持随 Claude Code / Codex 启动

## 监听器说明

`codex_pet_launcher.pyw` 是一个轻量常驻监听器，负责整个生命周期：

- 检测到 Claude Code / Codex / ChatGPT 启动时，拉起桌宠和托盘进程
- 检测到上述程序退出时，关闭桌宠和托盘进程
- 托盘图标 `codex_tray.pyw` 只在宿主程序运行期间存在

桌宠也可以脱离宿主程序独立运行：直接双击”打开桌宠”快捷方式或运行 `pythonw main.py`。

如果监听器被手动退出（例如托盘里的”退出”），宿主程序再次启动时不会自动拉起桌宠。恢复方式：

1. 下次登录 Windows 时注册表会自动启动监听器
2. 或双击“启动托盘”快捷方式手动恢复

托盘菜单说明：

- `显示桌宠`：显示或重新拉起桌宠
- `隐藏桌宠`：关闭桌宠（功能等同原来的“完全退出桌宠”），托盘保留，可再次用“显示桌宠”打开
- `开机自启动`：勾选后登录 Windows 时自动启动监听器
- `退出`：关闭桌宠、托盘和监听器本身

## 快捷方式

`create_shortcuts.py` 会在桌面和开始菜单创建两个快捷方式：

- `打开桌宠.lnk`：直接启动桌宠
- `启动托盘.lnk`：启动监听器（托盘），推荐在监听器退出后使用

## 目录结构

```text
ark-codex-skill/
├── README.md
├── .gitignore
└── ark-codex-skill/             # 可安装的 skill 本体
    ├── SKILL.md                 # skill 主说明
    ├── scripts/
    │   ├── scaffold_deskpet.py  # 生成桌宠项目
    │   ├── setup_env.py         # 创建 .venv 并安装依赖
    │   ├── prts_export.py       # 从 PRTS 导出 WebM
    │   ├── process_webm.py      # WebM 转透明 PNG 帧
    │   └── create_shortcuts.py  # 创建桌面/开始菜单快捷方式
    ├── references/
    │   └── prts-ui.md           # PRTS 查看器 DOM 参考
    └── assets/
        └── deskpet-app/         # 桌宠应用模板
            ├── main.py          # 主程序
            ├── behavior.py      # 马尔可夫状态机
            ├── physics.py       # 2D 物理引擎
            ├── window_detect.py # 全屏窗口检测
            ├── codex_monitor.py # CC/Codex 会话监控
            ├── codex_pet_launcher.pyw  # 宿主程序监听器
            ├── codex_tray.pyw   # 系统托盘
            └── pets/予愿安洁莉娜/  # 初始自带角色
```

## 环境要求

- Windows 10/11（桌宠程序目前仅适配 Windows）
- Python 3.10 或更高版本
- 可访问 `https://prts.wiki`
- 有网络权限安装依赖（PySide6、Playwright）

所有依赖都安装到项目自己的 `.venv`，不会影响全局 Python 环境。

## 使用指南

### 第一步：部署这个 skill

对 Claude Code 说：

```text
安装 GitHub 仓库 AstrariaX/Ark-codex-skill 里的 ark-codex-skill skill
```

也可以手动安装：把仓库里的 `ark-codex-skill/` 目录复制到 `~/.claude/skills/`。

> 同样兼容 Codex：复制到 `~/.codex/skills/` 即可。

### 第二步：调用

默认原皮：

```text
用 ark-codex-skill 制作干员 浊心斯卡蒂 的桌宠
```

指定皮肤：

```text
用 ark-codex-skill 制作干员 浊心斯卡蒂 的桌宠，皮肤用 升华
```

不写皮肤就是默认原皮。制作完成后右键小人可管理角色和动画组。

也可以指定动画组：

```text
用 ark-codex-skill 给干员 浊心斯卡蒂 下载正面动画组
```

## 桌宠功能

- 单击播放互动动画
- 双击切换迷你模式（隐藏/显示字幕条）
- 拖动角色，松手后受重力下落并播放落地音效
- 右键菜单：
  - 按动画组分子菜单选择动作（放松/坐下/睡觉/互动/散步/技能等）
  - 动画组多选激活
  - 动作设置（循环/一次性）
  - 面朝方向控制
  - 角色管理（下载/切换/删除）
  - 透明穿透、锁定拖动、轮廓描边
  - 缩放、倍速、设置、退出
- 头顶字幕：Claude Code / Codex 运行状态、最近任务、模型、运行时长、Token 用量
- 马尔可夫状态机驱动自主行为
- 多角色同时显示，各自独立行为和物理模拟
- 宠物间斥力避免重叠
- 每个角色独立记住位置、大小、动作倍速
- 迷你模式、全屏应用自动隐藏
- 可设置随 Claude Code / Codex 启动和关闭，也可手动独立运行
- 监听 `~/.claude/projects/` 和 `~/.codex/sessions/`，自动选择活跃会话，只读不修改数据

## 常见问题

### PRTS 导出失败或按钮找不到

PRTS 页面改版会影响脚本。先看 `ark-codex-skill/references/prts-ui.md` 里的 DOM 说明，再同步更新 `ark-codex-skill/scripts/prts_export.py` 的选择器。

### 打开后没有看到小人

运行 `my-deskpet/调试运行.bat`，把控制台报错或 `pet_error.log` 内容发出来。

### 需要手动从网站下载素材

可以直接在 PRTS 干员页的”干员模型”里手动操作：

1. 点击”点此载入模型”
2. 时装组选默认（或指定皮肤）
3. 模型组选”基建”/”正面”/”背面”
4. 动画依次选需要的动作（基建：`Default / Interact / Move / Relax / Sit / Sleep`；正面/背面：`Idle / Attack / Skill_1` 等）
5. 点击下载图标按钮导出 WebM
6. 把文件放进 `my-deskpet/work/webm/`，再让 Claude Code 用 skill 继续抽帧入库

## 注意事项

- 《明日方舟》素材版权归 Hypergryph 所有，PRTS 资料遵循其站内许可。本项目仅用于个人学习与自用，请勿用于商业发布。
- 桌宠程序目前仅支持 Windows；macOS/Linux 可以运行素材处理脚本，但桌宠程序需要额外适配。

## 贡献

欢迎提交 PR 修复 PRTS 页面变动、增加新动画映射、优化抽帧速度或补充平台适配。
