#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import importlib.util
from pathlib import Path
p=Path('system_files/usr/share/limad-windows/recipe_engine.py')
spec=importlib.util.spec_from_file_location('recipe_engine', p)
m=importlib.util.module_from_spec(spec); import sys; sys.modules[spec.name]=m; spec.loader.exec_module(m)
cases={
 'NWS-Desktop-Setup.exe':('nws','nws','dotnet48'),
 'Adobe-Photoshop-Setup.exe':('adobe','creative','dxvk'),
 'MyCADInstaller.msi':('cad','cad','vcrun2022'),
 'unknown-tool.exe':('generic','standard','vcrun2022'),
}
for name,(recipe,profile,dep) in cases.items():
    plan=m.analyze(Path(name))
    assert plan.recipe==recipe,(name,plan)
    assert plan.profile==profile,(name,plan)
    assert dep in plan.dependencies,(name,plan)
    if recipe == 'nws':
        assert 'corefonts' in plan.dependencies,(name,plan)
    else:
        assert 'corefonts' not in plan.dependencies,(name,plan)
print('Windows recipe engine profiles and dependency plans: PASS')
PY
python3 -c 'from pathlib import Path; import sys; [compile(Path(p).read_text(encoding="utf-8"), p, "exec") for p in sys.argv[1:]]' system_files/usr/share/limad-windows/recipe_engine.py system_files/usr/share/limad-windows/installer.py
