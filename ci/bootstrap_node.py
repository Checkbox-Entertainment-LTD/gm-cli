#!/usr/bin/env python3
"""Provision the CLI build job's declared Node version without worker edits."""
from pathlib import Path
import re
import urllib.request
from cli_distribution import install_node, ROOT

version = Path('.node-version').read_text().strip()
if not re.fullmatch(r'\d+\.\d+\.\d+', version): raise ValueError('Invalid Node version')
with urllib.request.urlopen('https://nodejs.org/dist/v' + version + '/SHASUMS256.txt', timeout=60) as r:
    hashes = dict((name.lstrip('*'), sha) for sha, name in (line.split() for line in r.read().decode().splitlines()))
artifacts = {}
for host in ['linux-x64', 'darwin-arm64']:
    name = 'node-v' + version + '-' + host + '.tar.gz'
    artifacts[host] = {'name': name, 'sha256': hashes[name]}
print(install_node({'version': version, 'artifacts': artifacts}, ROOT / 'node').parent)
