#!/usr/bin/env python3
"""Install an exact skill snapshot, keeping the previous installation as a backup."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import os
import shutil
import sys
import tempfile


def install(root, skills_dir, python):
    dest=skills_dir.expanduser().resolve()/'virtually-there'
    if dest.is_symlink():raise ValueError('Refusing to replace a symlinked skill installation.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    with tempfile.TemporaryDirectory(prefix='.vt-install-',dir=dest.parent) as temporary:
        stage=Path(temporary)/'new';previous=Path(temporary)/'previous'
        shutil.copytree(root/'skill',stage)
        (stage/'references/runtime.json').write_text(json.dumps({'project_root':str(root),'python':python},indent=2)+'\n')
        if dest.exists():
            backup=root/'outputs'/'skill-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            shutil.copytree(dest,backup)
            os.replace(dest,previous)
        try:os.replace(stage,dest)
        except OSError:
            if previous.exists():os.replace(previous,dest)
            raise
    return {'installed':str(dest),'backup':str(backup) if backup else None,'runtime':python}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skills-dir',type=Path,default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills')
    args=parser.parse_args()
    print(json.dumps(install(Path(__file__).resolve().parents[1],args.skills_dir,sys.executable)))

if __name__=='__main__':main()
