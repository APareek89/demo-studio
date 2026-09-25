"""Extract only committed source. Never import or replace production demo data."""
from pathlib import Path
import json
import os
import tarfile
from release_common import RECEIPT, RELEASE, ENV, DATA, package, source_manifest, sha, save, verify_source

os.umask(0o077)
metadata = package()
archive = RECEIPT / 'source.tar.gz'
assert archive.stat().st_size == metadata['archives']['source.tar.gz']['bytes']
assert sha(archive) == metadata['archives']['source.tar.gz']['sha256']
expected = source_manifest()
assert not RELEASE.is_symlink() and RELEASE.resolve() == RELEASE
assert not RELEASE.exists() or not any(RELEASE.iterdir()), 'Staging requires an empty new release directory'
RELEASE.mkdir(exist_ok=True, mode=0o755)
with tarfile.open(archive) as src:
    seen = set()
    for entry in src:
        parts = Path(entry.name).parts
        assert parts and not entry.name.startswith('/') and '..' not in parts and '\\' not in entry.name
        assert entry.isdir() or entry.isfile(), 'Links and special files are not release source'
        if entry.isfile():
            assert entry.name in expected and entry.name not in seen, 'Unexpected or duplicate archive file'
            seen.add(entry.name)
    assert seen == set(expected), 'Archive file set differs from committed manifest'
    src.extractall(RELEASE, filter='data')
assert not (RELEASE / '.env').exists() and not (RELEASE / 'data').exists()
(RELEASE / 'SOURCE_COMMIT').write_text(metadata['commit'] + '\n')
count = verify_source()
save('stage-verified.json', {'commit': metadata['commit'], 'source_files': count,
                            'source_manifest_sha256': sha(RECEIPT / 'source-manifest.json'),
                            'data_imported': False, 'environment_copied': False})
print(json.dumps({'commit': metadata['commit'], 'source_files': count, 'code_only': True}))
