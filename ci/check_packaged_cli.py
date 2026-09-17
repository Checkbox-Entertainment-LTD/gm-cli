#!/usr/bin/env python3
"""Run the actual packaged CLI twice and ensure its installed files stay immutable."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from cli_distribution import digest, safe_extract, verify_files


def main():
    with tempfile.TemporaryDirectory(prefix='checkbox-cli-package-check-') as tmp:
        root = Path(tmp)
        subprocess.run(['npm', 'pack', '--ignore-scripts', '--pack-destination', str(root)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        package, = root.glob('*.tgz')
        safe_extract(package, root, 'package')
        inventory = {str(p.relative_to(root)): digest(p)
                     for p in (root / 'package').rglob('*') if p.is_file()}
        env = dict(os.environ)
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        env.pop('PYTHONPYCACHEPREFIX', None)
        # Stock resolution exercises Python imports without credentials or downloads.
        for attempt in range(2):
            output = root / ('resolution-' + str(attempt))
            subprocess.run(['node', str(root / 'package/dist/cli.js'), 'runtime', 'resolve',
                            '--version', '2024.14.4.268', '--platforms', 'ios,android',
                            '--output', str(output)], env=env, check=True)
            lock = json.loads((output / 'lock.json').read_text())
            assert lock['version'] == '2024.14.4.268'
            verify_files(root, inventory)
        print('Packaged CLI repeated invocation and immutable file inventory: passed')


if __name__ == '__main__':
    main()
