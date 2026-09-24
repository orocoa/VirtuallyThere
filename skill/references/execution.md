# 执行契约

先读 runtime.json。在 project_root 中使用给定 python 执行 vt.py（下文 vt），不用猜系统解释器。用户不需编写以下内部文件。命令返回 JSON；失败返回非零并保留日志。

## 设计

`vt init JOB --text story.txt --images photo.jpg`：至少一种输入，新目录保存源文件副本。

`vt brief JOB --file brief.json`：新版本。结构：

```json
{"title":"作品标题","meaning":"有资料支持的记忆","form":"完整轮廓与体量关系","invariants":["必须保留的关系"],"omissions":["有意不直译的元素"],"dimensions_mm":[80,50,85],"lettering":null}
```

新创作还需 `design_contract`（旧项目无此字段仍可使用）：

```json
{"source_cues":[{"source":"sources/00-story.txt","evidence":"原文中的一段连续文字"}],"interpretation":"从这条来源选择形体关系的理由","parameters":{"gap_mm":12,"height_mm":60}}
```

source 使用 project.json 的来源路径；文字 evidence 必须逐字来自该文件，图片 evidence 写实际观察，后者由 Codex 看图核对。parameters 只放用得到的有限数值，允许空对象；毫米、角度分别用 `_mm`、`_degrees` 标注，计数应为整数。`invariants` 保留唯一必保要求列表，避免在多处重复。相向、转折、包围等只是可能的解释，不能套到每段故事。

color 可为 `black` 或 `white`，未指定默认 white；同时用于概念提示与模型预览。STL 不带耗材颜色，用户在 Studio 选对应耗材。

刻字时 lettering 为 `{"text":"精确文字"}`，不可擅加日期。

`vt prompts JOB` 写两份 imagegen 提示词。实际生图由 Codex 内置工具完成。第二组带第一组身份参考；查看后登记：

```sh
vt concept JOB --file elevations.png --views front,right,back
vt concept JOB --file volume.png --views top,bottom,three-quarter
vt concept-review JOB --file concept-review.json
```

concept-review 包含 reviewer="codex"、当前 project.json 的 concept_sha256 数组、direction_reason、observations；checks 包含 same_object、connections_consistent、voids_consistent、lettering_consistent、single_material_feasible。实际观察为真才填 true。

## 建模和检查

`vt model JOB --script authored-model.py`：通过真正 MCP 执行，隔离 Blender GUI 自动退出。脚本获得 `VT_BRIEF`（当前 brief）、`VT_PARAMETERS`（本版参数）、`VT_OUTPUT`（输出目录）、`VT_PYTHON`（外部几何解释器），最终保留网格 `VT_MODEL`。有参数时从注入值取数，不另写一套尺寸；禁止写死历史案例位置。

- Blender 内：`vt.blender_geometry` 提供 loft、ellipsoid、fuse、flat_bottom，适合自由体量组合。融合／清理后复查关键开口和刻字。
- 外部 Python：`vt.solid_geometry` 提供 arc_band、profile_extrude、subtract、export_stl。Blender 脚本调用 `vt.blender_geometry.solid_from_spec(spec, VT_OUTPUT, VT_PYTHON)` 即可经外部解释器生成并导回网格。spec 形如 `{"operation":"arc_band","parameters":{...}}`，参数从 `VT_PARAMETERS` 中对应字段取值。也可用外部 CLI `VT_PYTHON -m vt.solid_geometry SPEC.json OUTPUT.stl`。
- 需要具体操作时再读 `vt/solid_geometry.py` 的函数签名和限制，不将某个弧形参数组当作默认设计。

操作用于构建形体，不代替设计选择；不适合时使用自由 Blender 脚本。每次只启动一个隔离 Blender，外部操作沿用现有环境。

刻字可将身体临时导出至 VT_OUTPUT，用 runtime.json 的 Python 执行 `vt/lettering.py SOURCE TARGET SPEC` 再导回 Blender。spec 的 lines 每行含 font、text、em_mm、extrude_mm、3×4 transform，可选 font_index；字体必须含全部字形且逐行有实际去料。全局 contour_tolerance_mm / solid_tolerance_mm 可选。观察完整字形，不把去料量当可读性保证。

`vt check JOB`：独立几何 worker，默认无逐层切片或全表面厚度扫描。真实网格硬检查失败不能用视觉审核覆盖。悬垂等提示保留到交付，供用户在 Studio 判断支撑与切片。

查看实际模型六视图，生成 review.json，包含 reviewer="codex"、model_sha256、geometry_report_sha256、observations，以及五个 checks：silhouette、side_back_volume、meaning_preserved、lettering、resting_surface。无字时记录 lettering 不适用且没有意外文字。新 contract 项目还需当前 brief 的 `brief_sha256` 和 `invariant_checks`，每项必保要求恰好一条，例如：

```json
{"invariant":"前侧缺口保持开放","views":["front","top"],"observation":"两端之间和后方内腔相通，没有横梁封口。","passed":true}
```

只在观察成立时填 true。这是可追踪的 Codex 观察，不是算法自动理解了记忆。发现问题先写具体视角、偏差和拟调整参数；未解决不能提交通过。

`vt finish JOB --review review.json --open-studio`：绑定审查、打包并请求 Studio 打开 STL，不切片、不打印。检查 UI 真正出现模型后停止；若 UI 不可读，只报告打开请求已发送，不能虚构导入成功。也可分别 review、deliver、open-studio。

## 修订／已有模型

`vt revise-model JOB` 保留已检查概念，新开版本使旧模型与检查失效。尺寸小改用 `--parameters patch.json`，例如文件内容 `{"gap_mm":14}`，只更新已存在参数并记录差异；继承的是旧概念参考，不是新尺寸已经过审核。新模型必须重新检查。没有现成参数时，新开模型版本后局部修改脚本，记录改动尺寸；不伪造参数名，也不因缺参数重新生图。已有参数仍从当前 brief 取值。

主体数量、连接方式、开口的存在或方向等概念要求、来源解释或必保要求改变时，用 `vt brief` 新建方向并重新生图，不用参数补丁绕过概念审核。

`vt import-model JOB --stl model.stl --editable model.blend --views views/` 用于已有形体；也支持 .3dm 编辑源。views 内须有 front/right/back/top/bottom/three-quarter.png，实际对应 STL。仍需 check 和 review。

`vt status JOB` 校验文件哈希。不要编辑历史产物；变更创建新版本。超时只清理当前任务进程。交付状态 MODEL_READY 不是实打认证。
