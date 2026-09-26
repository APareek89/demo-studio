"""Extract exact committed mobile source; reuse the unchanged deployed venv."""
import json
import os
from pathlib import Path
import tarfile
from app_common import RECEIPT, RELEASE, OLD, PYTHON, package, source_manifest, sha, save, verify_source


def main():
    os.umask(0o077)
    metadata = package()
    archive = RECEIPT / 'source.tar.gz'
    assert not archive.is_symlink() and archive.is_file()
    assert archive.stat().st_size == metadata['archives']['source.tar.gz']['bytes']
    assert sha(archive) == metadata['archives']['source.tar.gz']['sha256']
    expected = source_manifest()
    assert 'SOURCE_COMMIT' not in expected
    assert not RELEASE.is_symlink() and RELEASE.resolve() == RELEASE
    assert RELEASE.is_dir() and not any(RELEASE.iterdir()), 'New mobile release must be empty'
    assert PYTHON.is_file(), 'Existing LiveKit runtime must remain available'
    for name in ('requirements.txt','requirements-livekit.txt','requirements-livekit-trial.txt'):
        assert name in expected and sha(OLD/name)==expected[name], 'Changed dependencies require a separate runtime review'
    parents = {str(parent) for name in expected for parent in Path(name).parents if str(parent) != '.'}
    with tarfile.open(archive) as src:
        seen = set()
        for entry in src:
            parts = Path(entry.name).parts
            assert parts and not entry.name.startswith('/') and '..' not in parts and '\\' not in entry.name
            assert str(Path(entry.name)) == entry.name.rstrip('/'), 'Archive path must be canonical'
            assert entry.isdir() or entry.isfile(), 'Links and special files are not release source'
            if entry.isfile():
                assert entry.name in expected and entry.name not in seen, 'Unexpected or duplicate archive file'
                seen.add(entry.name)
            else:
                assert entry.name.rstrip('/') in parents, 'Unexpected archive directory'
        assert seen == set(expected), 'Archive file set differs from committed manifest'
        src.extractall(RELEASE, filter='data')
    assert not (RELEASE / '.env').exists() and not (RELEASE / 'data').exists()
    (RELEASE / 'SOURCE_COMMIT').write_text(metadata['commit'] + '\n')
    count = verify_source()
    save('app-stage-verified.json', {'commit': metadata['commit'], 'source_files': count,
         'source_manifest_sha256': sha(RECEIPT / 'source-manifest.json'),
         'data_imported': False, 'environment_copied': False, 'existing_venv_reused': str(PYTHON)})
    print(json.dumps({'commit': metadata['commit'], 'source_files': count, 'data_imported': False}))


if __name__ == '__main__':
    main()
