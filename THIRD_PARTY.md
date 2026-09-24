# Third-party notices

The project source is MIT licensed. `vt/geometry_backend.py` adapts the topology wrapper from a prior MIT-licensed project, copyright 2026 LuumiAI; its complete notice is retained in `vt/GEOMETRY_LICENSE.txt`.

Dependencies are installed separately through pip; their source is not vendored:

- `mcp-for-blender` 2.0.3 — MIT, https://github.com/ahujasid/mcp-for-blender
- MCP Python SDK — MIT, https://github.com/modelcontextprotocol/python-sdk
- NumPy, Trimesh, NetworkX, Shapely, Open3D, Manifold and fontTools retain their respective upstream licenses. See installed distribution metadata for the exact resolved versions and licenses.

Blender and Bambu Studio are external applications. No application binaries, printer profiles, proprietary fonts, credentials, personal stories, photographs or generated models are included in this source release. Generated/user assets have their own ownership and usage conditions, independent of the source-code license.

Workflow references (reviewed 2026-09-24): [OpenAI imagegen](https://github.com/openai/skills/blob/main/skills/.system/imagegen/SKILL.md) for reference roles and identity; [Blender Skills](https://github.com/arjun988/blender-skills/blob/main/.claude/skills/blender-modeler/SKILL.md) for blockout and cleanup; [BlenderAlchemy](https://github.com/ianhuang0630/BlenderAlchemyOfficial) for rendered feedback. No third-party skill or research implementation, model configuration, or external generation service is embedded. Shape helpers are original code calling the separately installed Manifold dependency.
