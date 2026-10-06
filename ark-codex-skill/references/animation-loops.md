# 动作循环和过渡帧

PRTS的WebM导出片段不一定包含整数个动作周期。直接从末帧跳回第0帧时，姿势、衣摆或角色位置可能突然变化。

`scripts/prepare_loops.py`先从原始PNG帧中选择相似姿势和运动方向的循环边界，再用双向光流在末帧和首帧之间生成透明过渡帧。原始帧和WebM保留，新增帧接在原始帧编号之后。

## 使用

关闭正在使用该角色的桌宠。先在桌宠项目的虚拟环境里安装额外的素材处理依赖，路径替换为实际目录。

```powershell
<project>/.venv/Scripts/python.exe -m pip install -r <skill>/scripts/requirements-loops.txt
<project>/.venv/Scripts/python.exe <skill>/scripts/prepare_loops.py --pet <project>/pets/<operator>
```

默认处理已有的`idle`、`move`、`sit`和`sleep`状态，每个状态补3帧。它不会处理互动动作。脚本直接在IDE运行时，默认处理skill自带的予愿安洁莉娜目录。自动匹配至少相隔0.5秒的姿势，并比较相邻帧的变化方向。

自动匹配只是候选循环。预览至少两个完整周期，观察角色整体位置、衣摆和特效。如果选中了局部重复姿势、录制里含有入场动作，或光流使细节变形，应手动指定区间或减少补帧。素材本身没有重复动作时，补帧不能将它变成自然的周期动画。

区间使用从0开始的帧号，`--start`包含该帧，`--end`不包含该帧。以下通用示例选择第10帧到第49帧，并补3帧。实际区间需根据该角色的动画预览调整。

```powershell
<project>/.venv/Scripts/python.exe <skill>/scripts/prepare_loops.py --pet <project>/pets/<operator> --state idle --start 10 --end 50 --transition-frames 3
```

`--transition-frames 0`只选择循环区间，不生成补帧。再次运行时只替换上次生成的帧，减少补帧数量时会清理多余的生成帧。

## 播放规则

处理后的manifest为各状态增加以下字段。

- `source_count`记录原始帧数，单次播放只使用这些帧。
- `loop_start`和`loop_end`记录选择的原始帧区间。
- `loop_frames`记录循环时的帧编号顺序，包含所选原始帧和追加的过渡帧。
- `loop_duration`记录一个循环的毫秒数。
- `count`记录原始帧加新增帧的总数，`duration`仍记录原始片段时长。

模板在待机、拖动、自动坐下/睡觉和右键指定的持续动作中使用`loop_frames`。单击互动仍播一次。没有指定持续播放时，坐下播一次后返回待机，睡觉停在原始末帧。未处理的角色维持原有播放行为。重新运行WebM抽帧会重建manifest，之后需重新处理循环。

新增依赖仅供离线素材处理使用。桌宠播放只需要原有PySide6，不会在运行时计算光流。
