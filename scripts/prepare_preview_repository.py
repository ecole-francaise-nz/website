#!/usr/bin/env python3
"""Create a clean preview source snapshot outside the production checkout.

Copies only known website folders. Does not copy Git history, local settings,
unrelated files or caches. Does not push or modify the destination's parent.
"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--destination', required=True, type=Path)
args = parser.parse_args()
destination = args.destination.resolve()
assert ROOT != destination and ROOT not in destination.parents, 'Use a separate directory outside the source checkout.'
assert not destination.exists(), 'Choose a new directory so existing work cannot be overwritten.'
destination.mkdir(parents=True)
for folder in ['archetypes', 'assets', 'config', 'content', 'data', 'i18n', 'layouts', 'scripts', 'static']:
    shutil.copytree(ROOT / folder, destination / folder, ignore=shutil.ignore_patterns('.DS_Store', '__pycache__', '*.pyc'))
for name in ['.gitignore', 'README.md']:
    shutil.copyfile(ROOT / name, destination / name)
(destination / 'CNAME').write_text('preview.ecole-francaise.nz\n')
(destination / '.github/workflows').mkdir(parents=True)
shutil.copyfile(ROOT / 'scripts/preview-workflow.yaml', destination / '.github/workflows/preview.yaml')
print(f'Preview source ready at {destination}; contains no production deployment workflow.')
