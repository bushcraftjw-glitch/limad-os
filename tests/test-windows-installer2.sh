#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import importlib.util
import sys
root=Path('.')
installer=(root/'system_files/usr/share/limad-windows/installer.py').read_text()
recipe_path=root/'system_files/usr/share/limad-windows/recipe_engine.py'
recipe=recipe_path.read_text()
desktop=(root/'system_files/usr/share/applications/de.limad.WindowsApps.desktop').read_text()
runner=(root/'system_files/usr/local/bin/limad-winrun').read_text()
version=(root/'system_files/usr/share/limad-windows/VERSION').read_text().strip()

def fail(message):
    sys.exit('WINDOWS INSTALLER 2.2.6 FAILED: '+message)
for needle in ['_prefix_is_ready', '_normalized_bottle_name', 'APPS_HOME', 'prefix_for', 'dependency_status', 'completed_steps', 'RUNTIME_DOWNLOADS', 'MANUAL_DEPENDENCIES', 'continue_after_dependency_error', 'build_install_page', 'build_programs_page', 'build_repair_page', 'build_environments_page', 'build_log_page', 'build_settings_page']:
    if needle not in installer: fail('installer missing '+needle)
for needle in ['optional_dependencies', 'blockers', 'confidence', 'inspect_strings', 'webview2', 'dotnetdesktop8', 'access2016']:
    if needle not in recipe: fail('analyzer missing '+needle)
if '"corefonts": "corefonts"' not in installer: fail('corefonts support missing')
if '"standard": ("win10", ("vcrun2022",), ())' not in recipe: fail('standard profile must remain minimal')
if '--prefix' not in runner or '--exe' not in runner: fail('runner does not select per-app prefix')
if 'Icon=de.limad.WindowsApps' not in desktop: fail('dock icon changed')
if 'X-LiMaD-Version=2.2.6' not in desktop or version != '2.2.6': fail('version mismatch')
if 'sandbox_prefix = sandbox_root / relative_prefix' not in installer: fail('Soda prefix mapping missing')
if 'wurde aus Sicherheitsgründen nicht gelöscht' not in installer: fail('incomplete environment safety missing')
compile(installer, 'installer.py', 'exec')
compile(recipe, 'recipe_engine.py', 'exec')
spec=importlib.util.spec_from_file_location('recipe_engine', recipe_path)
module=importlib.util.module_from_spec(spec)
sys.modules['recipe_engine']=module
spec.loader.exec_module(module)
for name, profile in [('NWS-Desktop-Setup.exe','nws'),('office-setup.exe','office'),('game-launcher.exe','gaming')]:
    plan=module.analyze(Path(name))
    if plan.profile != profile: fail(f'{name} profile {plan.profile} != {profile}')
    if profile == 'nws' and 'corefonts' not in plan.dependencies: fail('NWS corefonts dependency missing')
    if profile != 'nws' and 'corefonts' in plan.dependencies: fail('corefonts returned outside NWS plan')
print('Windows-Programme Installer 2.2.6, Bottles/System-Wine environments and dock identity: PASS')
PY
