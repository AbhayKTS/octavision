from __future__ import annotations
import os
import sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / 'temp_sh17_repo' / 'data' / 'list_of_all_urls.csv'
OUT_DIR = ROOT / 'chemical_ppe_dataset' / 'raw' / 'sh17' / 'images'
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not CSV_PATH.exists():
    raise FileNotFoundError(f'Missing SH17 URL list: {CSV_PATH}')

urls = [line.strip() for line in CSV_PATH.read_text(encoding='utf-8', errors='ignore').splitlines() if line.strip()]
print(f'SH17 total_urls={len(urls)}')

failures = []
downloaded = 0
for index, url in enumerate(urls, start=1):
    filename = os.path.basename(url.split('?')[0])
    if not filename:
        failures.append((url, 'empty filename'))
        continue
    target = OUT_DIR / filename
    if target.exists():
        print(f'skip_existing {index}/{len(urls)} {filename}')
        downloaded += 1
        continue
    try:
        r = requests.get(url, timeout=30, allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        target.write_bytes(r.content)
        downloaded += 1
        if downloaded % 200 == 0:
            print(f'downloaded_so_far={downloaded}')
    except Exception as exc:
        failures.append((url, str(exc)))
        print(f'FAILED {filename}: {exc}')

print(f'FINAL downloaded={downloaded}; failures={len(failures)}')
if failures:
    fail_log = ROOT / 'chemical_ppe_dataset' / 'raw' / 'sh17' / 'failed_downloads.txt'
    with fail_log.open('w', encoding='utf-8') as f:
        for url, reason in failures:
            f.write(f'{url}\t{reason}\n')
    print(f'failure_log={fail_log}')
