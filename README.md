# Ark Codex Skill

> 增强版位于 `feat/event-driven-deskpet-yao` 分支，`main` 暂未包含这些改进。包含全局任务监听、动作联动、中英文透明居中字幕、完成字幕10秒隐藏、防重复启动、窗口位置恢复和“遥”素材库。详见 [增强功能与验证](ENHANCEMENTS.md) 和 [发布检查](RELEASE_CHECKLIST.md)。这是独立Python桌宠，不是Codex原生Custom pets。

用AI辅助制作的一个用于制作《明日方舟》透明桌面宠物（Codex 桌宠）的 Codex skill。给它一个干员名（可选皮肤名），它会自动从 PRTS Wiki 导出该干员的基建 WebM 动画，转换成带透明通道的 PNG 帧，生成桌宠并加入桌宠库。

> 增强版：[peripheral6/Ark-codex-skill](https://github.com/peripheral6/Ark-codex-skill/tree/feat/event-driven-deskpet-yao)；原作者：[AstrariaX/Ark-codex-skill](https://github.com/AstrariaX/Ark-codex-skill)。独立运行仓库：[ark-deskpet](https://github.com/peripheral6/ark-deskpet)。

## 功能特性

- 自动检索 PRTS 干员页面并加载“干员模型”查看器
- 默认使用原皮（默认时装），也可指定任意时装组
- 模型组固定使用“基建”，导出 `Default / Interact / Move / Relax / Sit / Sleep` 六段动画
- 自动跳过 PRTS 导出的坏文件（`Default` 经常是 110 字节空文件）
- 将 WebM 抽帧为 1000×1000、20fps 的透明 PNG，自动计算包围盒并生成 `manifest.json`
- 支持桌宠库：可以存放多个干员，右键“桌宠库”随时切换
- 系统托盘：ChatGPT/Codex 运行时拉起托盘进程，提供“显示桌宠 / 隐藏桌宠 / 开机自启动 / 退出”，应用退出时托盘一起退出
- 一键生成桌面和开始菜单的“打开桌宠 / 启动托盘”快捷方式
- 项目模板初始自带予愿安洁莉娜，生成后可以直接启动
- 生成的项目自带完整桌宠程序：状态字幕、拖动、锁定、迷你模式、全屏自动隐藏、按角色记忆位置/大小/倍速、随 ChatGPT/Codex 启动

## 监听器说明

`codex_pet_launcher.pyw` 是一个轻量常驻监听器，负责整个生命周期：

- 检测到 ChatGPT / Codex 启动时，拉起桌宠和托盘进程
- 检测到 ChatGPT / Codex 退出时，关闭桌宠和托盘进程
- 托盘图标 `codex_tray.pyw` 只在 ChatGPT / Codex 运行期间存在

如果监听器被手动退出（例如托盘里的“退出”），ChatGPT 再次启动时不会自动拉起桌宠。恢复方式：

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
    ├── SKILL.md                 # Codex skill 主说明
    ├── agents/
    │   └── openai.yaml          # Codex UI 元数据
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

直接对 Codex 说：

```text
安装 GitHub 仓库 peripheral6/Ark-codex-skill 的 feat/event-driven-deskpet-yao 分支中的 ark-codex-skill skill
```

也可以手动安装：把仓库里的 `ark-codex-skill/` 目录复制到 `~/.codex/skills/`。

如果使用 Codex 的 skill 安装器，也可以这样安装：

```text
--repo peripheral6/Ark-codex-skill --ref feat/event-driven-deskpet-yao --path ark-codex-skill
```

### 第二步：调用

默认原皮：

```text
用 ark-codex-skill 制作干员 浊心斯卡蒂 的桌宠
```

指定皮肤：

```text
用 ark-codex-skill 制作干员 浊心斯卡蒂 的桌宠，皮肤用 升华
```

不写皮肤就是默认原皮。制作完成后右键小人 -> 桌宠库，可以随时切换已入库的角色。

注意：项目自带予愿安洁莉娜与遥。先完成依赖安装，再双击 `启动桌宠.bat`。从本分支仓库根目录生成遥：

```powershell
python ark-codex-skill/scripts/scaffold_deskpet.py --target my-pet --pet 遥
python ark-codex-skill/scripts/setup_env.py my-pet --skip-browser
.\my-pet\启动桌宠.bat
```

使用已打包角色不需要浏览器；从PRTS导出新角色时不要跳过浏览器安装。

## 桌宠功能

- 单击播放互动动画
- 双击切换迷你模式（隐藏/显示字幕条）
- 拖动播放走路动画，松手恢复之前状态
- 右键菜单：坐下 / 放松 / 睡觉 / 桌宠库 / 锁定 / 设置 / 放大 / 缩小 / 退出
- 头顶字幕：仅显示Codex状态，可中英文切换，透明居中显示
- 每个角色独立记住位置、大小、动作倍速
- 迷你模式、全屏应用自动隐藏
- 可设置随 ChatGPT / Codex 启动和关闭
- 监听 `~/.codex/sessions/`，只读不修改 Codex 数据

## 常见问题

### PRTS 导出失败或按钮找不到

PRTS 页面改版会影响脚本。先看 `ark-codex-skill/references/prts-ui.md` 里的 DOM 说明，再同步更新 `ark-codex-skill/scripts/prts_export.py` 的选择器。

### 打开后没有看到小人

再次运行启动脚本会显示已有桌宠，并将窗口校正到屏幕内。若仍不可见，运行 `my-deskpet/调试运行.bat` 检查控制台报错或 `pet_error.log`。不要只凭PID文件存在判断窗口已显示。

### 其他任务没有触发动作

在桌宠设置中清空跟踪任务ID，并开启动作联动。留空代表全部本地任务，不是当前打开的页面。云端或未写本地日志的任务不在监听范围内。完成字幕显示10秒后隐藏。

### 需要手动从网站下载素材

可以直接在 PRTS 干员页的“干员模型”里手动操作：

1. 点击“点此载入模型”
2. 时装组选默认（或指定皮肤）
3. 模型组选“基建”
4. 动画依次选 `Default / Interact / Move / Relax / Sit / Sleep`
5. 点击下载图标按钮导出 WebM
6. 把文件放进 `my-deskpet/work/webm/`，再让 Codex 用 skill 继续抽帧入库

## 注意事项

- 《明日方舟》素材版权归 Hypergryph 所有，PRTS 资料遵循其站内许可。本项目仅用于个人学习与自用，请勿用于商业发布。
- 桌宠程序目前仅支持 Windows；macOS/Linux 可以运行素材处理脚本，但桌宠程序需要额外适配。

## 贡献

欢迎提交 PR 修复 PRTS 页面变动、增加新动画映射、优化抽帧速度或补充平台适配。
