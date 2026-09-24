"""Portable defaults; machine-specific values belong in an ignored config file."""
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def settings():
    from .store import read
    binaries=Path(sys.executable).parent
    local_server=binaries/'mcp-for-blender'
    result={
        'geometry_python':sys.executable,
        'mcp_python':sys.executable,
        'mcp_server':str(local_server) if local_server.is_file() else (shutil.which('mcp-for-blender') or str(local_server)),
        'blender':'/Applications/Blender.app/Contents/MacOS/Blender',
        'studio':'/Applications/BambuStudio.app/Contents/MacOS/BambuStudio',
    }
    file=os.environ.get('VT_CONFIG')
    if file:
        supplied=read(Path(file).expanduser())
        if not isinstance(supplied,dict) or set(supplied)-set(result):raise ValueError('Unknown configuration fields')
        if any(not isinstance(v,str) or not v.strip() for v in supplied.values()):raise ValueError('Configuration paths must be nonempty strings')
        result.update({k:str(Path(v).expanduser()) for k,v in supplied.items()})
    return result
