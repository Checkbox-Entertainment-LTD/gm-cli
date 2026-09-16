"""Prepare an isolated game source copy with its verified custom runtime constant.

GMAssetCompiler 2024.14 emits GM_runtime_version from its own assembly version.
A GML macro overrides that compiler constant without patching the official tools.
"""
import json
from pathlib import Path
import re
import shutil


def prepare(project, destination, version):
    project, destination = Path(project).resolve(), Path(destination).resolve()
    if not re.fullmatch(r'\d+(?:\.\d+){3}-c[1-9]\d*', version):
        raise ValueError('Expected verified custom runtime version')
    if destination.exists(): raise ValueError('Versioned project destination must be fresh')
    # Keep the original project layout and extension paths. Exclude only build
    # products / VCS metadata, including the invocation that contains this copy.
    root = project.parent
    excluded = {'.git', 'artifacts', 'ios-generated', 'node_modules'}
    def ignore(directory, names):
        return [name for name in names if name in excluded or name.startswith('.gm-')
                or name.startswith('.xcode-') or (Path(directory) / name).resolve() == destination
                or destination.is_relative_to((Path(directory) / name).resolve())]
    shutil.copytree(root, destination, ignore=ignore)
    # Prepend to an existing registered script. Macros are global irrespective of
    # script execution. No project-resource or compiler-binary changes are needed.
    paths = re.findall(r'"path"\s*:\s*"(scripts/[^"\r\n]+\.yy)"', project.read_text())
    scripts = sorted(destination / Path(path).with_suffix('.gml') for path in paths)
    if any(not p.resolve().is_relative_to(destination) for p in scripts):
        raise ValueError('Invalid registered script path')
    # Some registered compatibility/extension scripts have no local GML body.
    scripts = [p for p in scripts if p.is_file()]
    if not scripts: raise ValueError('A registered GML script is required for runtime identity')
    for file in destination.rglob('*.gml'):
        if re.search(rb'(?m)^\s*#macro\s+(?:\w+:)?GM_runtime_version\b', file.read_bytes()):
            raise ValueError('Project already overrides GM_runtime_version; refusing ambiguous identity')
    file = scripts[0]
    original = file.read_bytes()
    bom = b'\xef\xbb\xbf'
    file.write_bytes((bom if original.startswith(bom) else b'') +
                     ('#macro GM_runtime_version ' + json.dumps(version) + '\n').encode() +
                     (original[len(bom):] if original.startswith(bom) else original))
    return {'project': str(destination / project.name), 'version': version,
            'macroScript': str(file.relative_to(destination))}
