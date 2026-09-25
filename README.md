# VirtuallyThere · 不虚此行

**用 Codex，给自己的生活做周边。**

把一段文字、几张照片，变成与个人经历有关的三维纪念物。VirtuallyThere 是一个围绕 Codex 构建的开源 Skill 与本地建模工作流：从生活素材中提取线索，生成简约、抽象的概念，再通过 Blender MCP 建成模型，检查后导入 Bambu Studio。

你提供经历和偏好，Codex 推进设计与建模；你在 Studio 中检查切片并决定打印。

[开始使用](#开始使用) · [详细指南](docs/guide.md) · [项目介绍与分享文案](docs/introduction.md) · [架构图](#它如何工作) · [参与讨论](https://github.com/orocoa/VirtuallyThere/issues)

## 为什么给生活做周边

每次旅行，总想带回一件纪念品。有时挑了很久，看到的仍是熟悉的款式；即便有溢价，也觉得为这段经历留下一件东西值得。

VirtuallyThere 从这个念头出发：既然想留下的是自己的经历，能不能从旅程本身开始设计？一处空间、一段路、照片里的两道影子，都可以成为造型的线索。

项目选择概念化、简约的表达。保留少量有辨识度的关系、轮廓和文字，让人听一句背景，就能理解这个物件与哪里、什么经历有关。它的用途也包括日常记录、相处的片段，以及想做给某个人的小礼物。

## 你可以用它做什么

| 你提供的素材 | 设计可以从哪里开始 |
| --- | --- |
| 一段旅行记录 | 路线转折、地形起伏、空间的开合 |
| 某个地方的照片和故事 | 地点轮廓、建筑之间的关系、少量地点文字 |
| 一张与你有关的生活照片 | 人与物的相对位置、影子、距离和留白 |
| 一个想纪念的时刻 | 对你有意义的关系，以及希望保留的识别线索 |

这些是创作方向示例。具体形体由本次素材决定，你也可以指定不想出现的元素。

默认造型是小体量、单色、有侧背深度的完整物件，可选择黑色或白色预览、添加少量刻字。适合希望从生活素材开始创作的人，也适合想把 vibe coding 延伸到实体制作的朋友。

## 它如何工作

![VirtuallyThere 架构：生活素材进入 Codex 与 Skill，由 imagegen 提供概念参考，本地 Python 通过 Blender MCP 建模，检查后交付到 Bambu Studio，用户完成切片打印。](docs/assets/architecture.svg)

[交互架构图 HTML](docs/architecture.html) · [可编辑图表规范](docs/architecture.json)

交互版由 [Archify](https://github.com/tt-a1i/archify) 生成，支持查看节点、切换明暗主题和导出图表。GitHub 文件页显示源码；下载 HTML 后用浏览器打开即可交互。

| 阶段 | 做什么 | 你能看到什么 |
| --- | --- | --- |
| 理解素材 | Codex 阅读文字、查看图片，整理来源线索和必须保留的设计要求 | 方向说明、来源与形体之间的关系 |
| 概念参考 | 内置 imagegen 每轮生成至少两张参考板，覆盖六个角度 | 同一物件的多角度概念图 |
| 建立模型 | Codex 编写建模脚本，本地程序通过 Blender MCP 执行 | 三维体量、可选刻字与编辑源文件 |
| 检查与修订 | 检查实际 STL，重导入渲染六视图，核对几何和设计要求 | 几何报告、视觉观察和需要修复的问题 |
| 交付 | 保存通过检查的当前模型，请求 Bambu Studio 打开并确认界面 | STL、编辑源、预览页和检查报告 |
| 实物制作 | 用户在 Studio 中选择耗材、检查支撑和刀路、切片并打印 | 由实际打印结果检验的纪念物 |

Codex 负责理解、生图调用和设计判断；本地 Python 负责执行、检查及文件管理。**运行命令行本身不会自动理解故事或生成概念图，需要在具备内置 imagegen 的 Codex 环境中使用。**

## 开始使用

### 1. 准备环境

当前实测环境是 **macOS、Python 3.12、Blender 4.1、Bambu Studio 02.08.02.61**。项目声明支持 Python 3.10–3.12；其他软件版本与平台尚未完成同等验证。

你需要：

- 能读取本地文件、执行命令并调用内置 imagegen 的 Codex 环境。
- 本机安装 Python、Blender 与 Bambu Studio。
- 创作素材：一段文字、照片，或两者一起提供。

作者的实物尝试围绕 **Bambu Lab P2S** 展开。Skill 交付的是毫米 STL，没有控制打印机的接口，也不自动生成适配所有机型的切片配置。其他机型需要用户自行选择设置并验证。

### 2. 安装项目与 Skill

在终端运行：

```sh
git clone https://github.com/orocoa/VirtuallyThere.git
cd VirtuallyThere
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python vt.py doctor
.venv/bin/python scripts/install_skill.py
```

`doctor` 检查依赖和软件路径，不启动建模或打印。输出 `"ok": true` 后再开始创作。安装器把 Skill 放进 Codex 的 skills 目录，并记录当前项目和 Python 的位置；已有安装会备份到本地 `outputs/skill-backups/`。

安装完成后，在 Codex 中调用 `$virtually-there`。中文名为「不虚此行」，展示名为 **VirtuallyThere**。

如果软件不在默认路径，按[路径配置说明](docs/guide.md#路径配置)设置。移动项目目录后，重新运行安装器。

### 3. 带着一段经历开始

把自己的文字和照片发给 Codex，再输入：

```text
$virtually-there

我想把这段经历做成一个桌面纪念物。
请从我提供的文字和照片里提取线索，采用简约、抽象的造型。
自动选方向，完成多角度概念、建模与检查后导入 Bambu Studio。
切片和打印我自己操作。
```

你可以补充尺寸、颜色、精确刻字，以及必须保留或不想出现的元素。不需要自己写 JSON。

如果想先讨论设计，可以说「先做概念，等我看过再建模」。如果已经认可形状，可以说「保持连接和开口，只调整这个尺寸」。系统会按修改影响的阶段推进，不把旧版本的检查结果当成新版本已经通过。

## 最后会得到什么

默认 Blender 流程交付：

| 文件 | 用途 |
| --- | --- |
| `model.stl` | 毫米单位网格，导入切片器 |
| `model.blend` | 可继续编辑的 Blender 源文件 |
| `views/` | 从实际 STL 重导入渲染的六个视角 |
| `geometry.json` | 几何检查结果和制造提示 |
| `manifest.json` | 当前版本、尺寸、哈希及交付范围 |
| `index.html` | 浏览器中查看模型视图与交付文件 |

来源副本、概念参考、建模脚本和审查记录保留在项目的版本目录中。已有模型导入也支持 `.3dm` 编辑源，详情见[执行契约](skill/references/execution.md)。

## 当前能力与边界

- **几何检查**覆盖闭合性、单体、法向、自交、尺寸、落地与稳定性等条件；**视觉审核**由 Codex 对照真实模型视图和当前设计要求完成。
- `MODEL_READY` 表示几何与视觉检查通过，可以进入切片器。壁厚、支撑、刀路与最终打印效果仍需要在 Studio 和实物中确认。
- 默认自动推进到模型交付与 Studio 导入；不自动切片，不连接打印机，不发送打印命令。
- 概念图、模型渲染与实物照片是三个阶段。概念图提供造型参考，最终几何以模型为准。
- 当前重点是抽象小物；精密配合、复杂装配、多色系统和高精度写实复刻不在默认流程内。
- 项目采用 MIT 开源许可；运行所需的 Codex／生图服务及打印耗材可能产生费用，开源不等于这些成本免费。

## 项目状态

当前版本 **0.3.0**。已经完成独立环境安装、真实 MCP 建模、实际 STL 六视图、几何检查和 Studio 界面导入验证。GitHub Actions 的[首次干净环境测试](https://github.com/orocoa/VirtuallyThere/actions/runs/35988664499)已通过。

自动测试覆盖流程状态、版本与哈希绑定、局部修订、刻字、几何操作、进程清理、安装回滚及发布文件清单。CI 验证软件行为；艺术判断、界面操作与实物打印需要各自的验证。

## 一起把它做得更好

欢迎给项目一个 Star，也欢迎带着自己的旅行或生活素材来[讨论](https://github.com/orocoa/VirtuallyThere/issues)。有帮助的反馈包括：

- 你希望纪念什么，哪些线索一定要保留？
- 概念或模型在哪一步偏离了你的想法？
- 实际打印时，哪个结构、刻字或细节需要调整？

我愿意用自己的 P2S 和参与者一起尝试个人纪念品的制作，再根据实物效果改进项目。具体素材、尺寸和尝试安排可以在讨论中确定。

## 开发与许可

`skill/` 保存设计和操作规则；`vt/` 是本地执行层；`examples/` 提供非私人建模示例；`tests/` 保存回归测试；`docs/` 提供使用与推广说明。

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python vt.py --help
.venv/bin/python scripts/package_release.py --output /absolute/virtually-there.zip
```

发布脚本使用明确的文件清单，不打包用户运行目录、照片、私人模型、凭证或本地配置，也不会上传远端。详细命令见[执行契约](skill/references/execution.md)。

采用 [MIT License](LICENSE)。依赖和转载部分见[第三方版权说明](THIRD_PARTY.md)。
