from pathlib import Path
import hashlib, json
root = Path(__file__).parent
files = sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json' and '__pycache__' not in p.parts)
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(f'manifest.json: {len(manifest)} files')
