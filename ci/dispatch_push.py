#!/usr/bin/env python3
"""Forward a GitHub push to a token-scoped Jenkins job, one exact SHA per build."""
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from commit_policy import pushed_commits


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    base = os.environ['JENKINS_CI_URL'].rstrip('/')
    if urllib.parse.urlparse(base).scheme != 'https':
        raise ValueError('HTTPS Jenkins URL required')
    opener = urllib.request.build_opener(NoRedirect())
    for commit in pushed_commits(Path.cwd(), event):
        if subprocess.run(['git', 'cat-file', '-e', commit + ':ci/commit_policy.py'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            print('Historical commit before CI version tracking:', commit)
            continue
        data = urllib.parse.urlencode({'job': os.environ['JENKINS_CI_JOB'],
                                      'token': os.environ['JENKINS_BUILD_TOKEN'],
                                      'SOURCE_COMMIT': commit, 'delay': '0sec'}).encode()
        # Token in POST body, never command arguments, URL, or console output.
        try:
            with opener.open(urllib.request.Request(base + '/buildByToken/buildWithParameters', data=data), timeout=60) as r:
                if r.status not in (200, 201, 202):
                    raise RuntimeError('Unexpected dispatch status: ' + str(r.status))
        except urllib.error.HTTPError as e:
            if e.code != 303:  # already queued
                raise RuntimeError('Jenkins dispatch failed: HTTP ' + str(e.code)) from None
        print('Queued exact commit:', commit)


if __name__ == '__main__':
    main()
