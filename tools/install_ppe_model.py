"""Download a verified public construction PPE checkpoint for demo profiles."""
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://huggingface.co/killuminati1/construction-ppe-yolov8/resolve/ff33259/best.pt'
SHA256 = '31ef3ca04a17cf545f3fcfc64c4af8993a41d52ccc460e82aff01d5354603533'
PROFILES = ('general', 'construction', 'road')
MAX_BYTES = 50 * 1024 * 1024


def install():
    destination = ROOT / 'weights'
    destination.mkdir(exist_ok=True)
    missing = [destination / f'{site}.pt' for site in PROFILES if not (destination / f'{site}.pt').exists()]
    if not missing:
        print('All three files already exist; existing models were not changed.')
        return
    print('Downloading 22.5 MB construction PPE model...')
    with tempfile.TemporaryDirectory(dir=destination) as tmp:
        source = Path(tmp) / 'model.pt'
        digest = hashlib.sha256()
        size = 0
        with urlopen(URL, timeout=90) as response, source.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('Download exceeds expected maximum size')
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != SHA256:
            raise ValueError('Model SHA-256 mismatch; nothing installed')
        for target in missing:
            try:
                with target.open('xb') as output, source.open('rb') as verified:
                    shutil.copyfileobj(verified, output)
            except FileExistsError:
                print(f'Skipped existing {target.name}')
            else:
                print(f'Installed {target}')
    print('Restart backend and refresh dashboard. Chemical and mining need separate weights.')


if __name__ == '__main__':
    try:
        install()
    except Exception as exc:
        print(f'Model installation failed: {exc}', file=sys.stderr)
        sys.exit(1)
