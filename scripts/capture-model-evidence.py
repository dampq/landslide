"""Capture actual integration checks and artifact/runtime identity; never trains a model.

Run with backend/.venv/bin/python scripts/capture-model-evidence.py.
Stop development servers first: Playwright owns ports 8000 and 4173.
"""
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/evidence' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT.mkdir(parents=True, exist_ok=False)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

report = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'python': sys.version, 'python_executable': sys.executable,
          'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'working_tree_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
          'dependencies': {p: importlib.metadata.version(p) for p in
                           ['numpy', 'pandas', 'scipy', 'scikit-learn', 'joblib', 'fastapi', 'pydantic', 'httpx', 'pytest']},
          'source_sha256': {}, 'commands': []}
for base in ['backend/api', 'src', 'tests', 'scripts']:
    for p in (ROOT / base).rglob('*'):
        if p.is_file() and p.suffix in ['.py', '.tsx', '.ts', '.json', '.mjs', '.sh'] and '__pycache__' not in p.parts:
            report['source_sha256'][str(p.relative_to(ROOT))] = sha(p)
for name in ['backend/requirements.lock', 'package-lock.json', 'model-handoff/manifest.json']:
    report['source_sha256'][name] = sha(ROOT / name)
archive = ROOT / 'model-handoff/Ashtaraksha_Teammate_Handoff.zip'
report['archive_sha256'] = sha(archive)
manifest = json.loads((ROOT / 'model-handoff/manifest.json').read_text())
report['models'] = manifest
with zipfile.ZipFile(archive) as z:
    for version, spec in manifest.items():
        for name, expected in spec['sha256'].items():
            actual = hashlib.sha256(z.read('Ashtaraksha_Teammate_Handoff/' + spec['folder'] + '/' + name)).hexdigest()
            if actual != expected:
                raise SystemExit('Artifact hash mismatch: ' + name)
report['artifact_checksums_verified'] = True
commands = [
    ['node', '--version'], ['npm', '--version'], ['/usr/bin/chromium', '--version'],
    [sys.executable, '-m', 'pip', 'check'],
    ['npm', 'run', 'build'], ['npm', 'run', 'check:i18n'], ['npm', 'run', 'test:config'],
    [sys.executable, '-m', 'pytest', 'tests/test_api.py', 'tests/test_python_setup.py',
     'tests/test_database_startup.py', 'tests/test_diagnostics.py', '-q', '--junitxml=' + str(OUT / 'pytest.xml')],
    ['npm', 'run', 'test:e2e', '--', '--reporter=json'],
]
for i, command in enumerate(commands):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log = OUT / f'{i:02d}.log'
    with log.open('w') as f:
        r = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    report['commands'].append(dict(argv=command, started_utc=started,
                                  completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  exit_code=r.returncode, log=log.name, log_sha256=sha(log)))
    (OUT / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{i:02d}: exit {r.returncode}: {" ".join(command)}', flush=True)
report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
(OUT / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
print('Evidence: ' + str(OUT), flush=True)
raise SystemExit(any(c['exit_code'] for c in report['commands']))
