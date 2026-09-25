#!/usr/bin/env python3
"""Build a source-only ZIP from an explicit allowlist; never upload anything."""
import argparse
import hashlib
import re
from pathlib import Path
import zipfile

# Only reviewed source paths belong in a release; runtime notes cannot opt in by extension.
SOURCE_FILES = """
.github/workflows/tests.yml
.gitignore
LICENSE
README.md
THIRD_PARTY.md
config.example.json
docs/guide.md
docs/introduction.md
docs/architecture.html
docs/architecture.json
docs/assets/architecture.svg
docs/assets/ARCHIFY-LICENSE.txt
examples/model.py
pyproject.toml
scripts/install_skill.py
scripts/package_release.py
skill/SKILL.md
skill/agents/openai.yaml
skill/references/execution.md
skill/references/runtime.json
skill/references/sharing.md
tests/test_delivery.py
tests/test_design_contract.py
tests/test_design_review.py
tests/test_fail_closed.py
tests/test_lettering.py
tests/test_process_cleanup.py
tests/test_release.py
tests/test_solid_geometry.py
tests/test_workflow.py
vt.py
vt/GEOMETRY_LICENSE.txt
vt/__init__.py
vt/blender_bootstrap.py
vt/blender_export.py
vt/blender_geometry.py
vt/cli.py
vt/config.py
vt/geometry_backend.py
vt/geometry_worker.py
vt/lettering.py
vt/mcp_runner.py
vt/pipeline.py
vt/prompts.py
vt/solid_geometry.py
vt/store.py
""".split()


def sources(root):
    for name in sorted(SOURCE_FILES):
        rel=Path(name);p=root/rel
        if not p.is_file():raise ValueError('Missing release source: '+name)
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('External source link: '+name)
        text=p.read_text()
        if re.search(r'/Users/[a-zA-Z0-9_.-]+/',text):raise ValueError('Personal absolute path in '+name)
        if re.search(r'(?:sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{30,})',text):raise ValueError('Possible credential in '+name)
        yield p,rel


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];items=list(sources(root))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED) as archive:
        for p,rel in items:archive.write(p,'virtually-there/'+str(rel))
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix+'.sha256').write_text(digest+'  '+args.output.name+'\n')
    print(str(args.output.resolve())+' — '+str(len(items))+' source files, SHA-256 '+digest)

if __name__=='__main__':main()
