#!/usr/bin/env python3
"""Check data_root path configuration"""
from metabolic_backend.config import get_settings
from pathlib import Path
import os

s = get_settings()
print(f'data_root: {s.data_root}')
print(f'cwd: {os.getcwd()}')

parsed_path = s.data_root / 'documents' / 'parsed'
print(f'parsed_docs: {parsed_path}')
print(f'exists: {parsed_path.exists()}')
print(f'is_dir: {parsed_path.is_dir()}')

if parsed_path.exists():
    contents = list(parsed_path.glob("*"))
    print(f'contents ({len(contents)} items):')
    for item in contents:
        print(f'  - {item.name}')
else:
    # Try absolute path
    abs_parsed = Path('/home/gram/metabolic_syndrome_project/data/documents/parsed')
    print(f'\nTrying absolute path: {abs_parsed}')
    print(f'exists: {abs_parsed.exists()}')
    if abs_parsed.exists():
        contents = list(abs_parsed.glob("*"))
        print(f'contents ({len(contents)} items):')
        for item in contents:
            print(f'  - {item.name}')
