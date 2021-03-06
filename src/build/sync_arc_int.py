#!src/build/run_python
#
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Syncs our code in internal/ and the Android internal repos to DEPS.*."""

import logging
import os
import subprocess
import sys

from src.build.build_options import OPTIONS
from src.build.util import git

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ARC_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_ARC_INTERNAL_DIR = os.path.join(_ARC_ROOT, 'internal')
_DEPS_FILE = os.path.join(_ARC_ROOT, 'src/build/DEPS.arc-int')


def _get_current_arc_int_revision():
  return git.get_last_landed_commit(cwd=_ARC_INTERNAL_DIR)


def _git_has_local_modification():
  if git.get_current_branch_name(cwd=_ARC_INTERNAL_DIR) != 'master':
    return True  # not on master
  if git.get_uncommitted_files(cwd=_ARC_INTERNAL_DIR):
    return True  # found modified or staged file(s)
  return False


def sync_repo(target_revision):
  logging.info('Resetting %s to %s' % (_ARC_INTERNAL_DIR, target_revision))
  git.reset_to_revision(target_revision, cwd=_ARC_INTERNAL_DIR)


def run():
  OPTIONS.parse_configure_file()

  # Check if internal/ exists. Run git-clone if not.
  if not os.path.isdir(_ARC_INTERNAL_DIR):
    # TODO(tandrii): Move this nacl-x86_64-bionic-internal recipe's botupdate
    # step.
    url = 'https://chrome-internal.googlesource.com/arc/internal-packages.git'
    logging.info('Cloning %s' % url)
    subprocess.check_call('git clone %s internal' % url,
                          cwd=_ARC_ROOT, shell=True)

  # On 'internal' mode, sync the HEAD to the DEPS revision.
  # On 'internal-dev', just use the current HEAD.
  if OPTIONS.internal_apks_source() == 'internal':
    # Check if internal/ is clean and on master.
    if _git_has_local_modification():
      logging.error('%s has local modification' % _ARC_INTERNAL_DIR)
      sys.exit(-1)

    # Check if internal/ is up to date. Run git-reset if not.
    with open(_DEPS_FILE) as f:
      target_revision = f.read().rstrip()
    logging.info('%s has %s' % (_DEPS_FILE, target_revision))
    if target_revision != _get_current_arc_int_revision():
      sync_repo(target_revision)

  # Run the configuration for the current HEAD revision. This steps includes
  # syncing internal/third_party/ repositories when needed.
  subprocess.check_call(os.path.join(_ARC_INTERNAL_DIR, 'build/configure.py'))

  return 0


if __name__ == '__main__':
  sys.exit(run())
