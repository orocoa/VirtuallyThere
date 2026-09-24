# VirtuallyThere

中文名：不虚此行。

在 Codex 中把文字、照片和生活经历变成简约抽象的 3D 小物：

**资料 → 自动选方向与六角度概念 → Blender MCP 建模／刻字 → 几何与视觉检查 → 导入 Bambu Studio。**

切片和打印由用户操作。Codex 负责理解、看图和设计，本地程序负责执行与文件管理；它不是独立运行的文字转 3D 服务。

## 安装与使用

当前实测 macOS、Python 3.12、Blender 4.1、Bambu Studio 02.08.02.61；支持 Python 3.10–3.12。需要可调用内置 imagegen 的 Codex。安装 Blender 和 Studio 后，在项目目录运行：

```sh
git clone https://github.com/orocoa/VirtuallyThere.git
cd VirtuallyThere
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python vt.py doctor
.venv/bin/python scripts/install_skill.py
```

然后在 Codex 发文字或图片：

> 用 $virtually-there 做成抽象小物，自动选方向，完成后导入 Studio，切片和打印我自己操作。

若软件位置不同，复制 `config.example.json` 为 `config.local.json`，修改路径，设置 `VT_CONFIG` 为该文件的绝对路径。移动项目后重跑安装器。旧 skill 会备份至 outputs，不覆盖用户作品。

## 交付与边界

每轮概念至少两张板，覆盖正、右、背、顶、底、斜视；第二组参考第一组。建模后从实际 STL 重导入渲染六视图。交付 **毫米 STL、可编辑 .blend、六视图、几何报告与预览页**。

新创作用同一份 brief 记录来源证据、设计解释与形体参数，生图和脚本共享这些要求；黑白选择传递到提示词和模型预览。可复用截面、弧形和布尔操作，也可自由建模。小改保留概念，只重跑受影响阶段。

保留闭合、单体、法向、自交、尺寸、落地和稳定检查；模型未变不重复检查。源文件、版本和哈希防止覆盖或错用旧结果；新项目的视觉审核还绑定当前 brief，逐项记录造型要求是否保留。`MODEL_READY` 表示可进入切片器，壁厚、支撑和刀路仍由用户在 Studio 检查。

没有自动切片、打印机连接或发送命令。Studio 打开请求必须由真实界面确认，不能当作已导入或已打印。只关闭本任务拥有的 Blender 进程。

## 开发

`vt/` 为执行代码，`skill/` 为设计与操作规则，`examples/` 为非私人造型示例，`tests/` 为回归测试。详细内部命令见 [执行契约](skill/references/execution.md)，用户无需填写 JSON。

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python vt.py --help
.venv/bin/python scripts/package_release.py --output /absolute/virtually-there.zip
```

发布包只含许可清单内的源码和文档；不包含虚拟环境、运行资料、照片、私人模型、凭证或本地配置，不自动发布到远端。项目采用 [MIT](LICENSE)，保留[第三方版权说明](THIRD_PARTY.md)。

## 验证

已有独立环境安装、真实 MCP 建模、实际 STL 六视图、几何检查和 Studio 界面导入验证。自动回归覆盖阶段门槛、错版报告、来源与参数绑定、局部修订、刻字、几何操作、进程清理、无切片交付、安装回滚与发布文件清单。

完整案例使用明确标注为虚构的文字，从两次内置生图开始建立新模型；后续回归可复用相同概念，不能冒称新的生图验收。CI 只运行自动测试，不代表艺术判断、GUI 或实物打印认证。
