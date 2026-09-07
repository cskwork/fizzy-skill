#!/usr/bin/env python3
"""Generate installable skill resources and the existing Cursor distribution."""
import argparse
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--check', action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
skill=root/'skills'/'fizzy'
extra_roots={'references': 'references'}
resources={}
resource_modes={}
for source, destination in extra_roots.items():
    for path in (root/source).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.name != 'sync-distributions.py':
            rel=Path(destination)/path.relative_to(root/source)
            resources[rel]=path.read_bytes()
            resource_modes[rel]=path.stat().st_mode & 0o777
extra_dirs={Path(d) for d in extra_roots.values()}
canonical={}
canonical_modes={}
for path in skill.rglob('*'):
    rel=path.relative_to(skill)
    if path.is_file() and '__pycache__' not in path.parts and not any(d==rel or d in rel.parents for d in extra_dirs):
        canonical[rel]=path.read_bytes()
        canonical_modes[rel]=path.stat().st_mode & 0o777
canonical.update(resources)
canonical_modes.update(resource_modes)
expected={skill/rel:data for rel,data in resources.items()}
mirror=root/'.cursor/skills'/'fizzy'
expected.update({mirror/rel:data for rel,data in canonical.items()})
expected_modes={skill/rel:mode for rel,mode in resource_modes.items()}
expected_modes.update({mirror/rel:mode for rel,mode in canonical_modes.items()})
if args.check:
    stale=[str(p.relative_to(root)) for p,data in expected.items() if not p.is_file() or p.read_bytes()!=data or (p.stat().st_mode & 0o111)!=(expected_modes[p] & 0o111)]
    extra=[str(p.relative_to(root)) for p in mirror.rglob('*') if p.is_file() and p not in expected and '__pycache__' not in p.parts]
    if stale or extra:
        raise SystemExit(f'Distribution differs: stale={stale}, extra={extra}')
    print('Packaged resources and Cursor distribution match maintained sources')
else:
    for path,data in expected.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        path.chmod(expected_modes[path])
    print(f'Generated {len(expected)} resource/distribution files; run --check')
