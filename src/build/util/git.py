# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Some basic git functionality."""

import logging
import subprocess
import os


# TODO(lpique) This and util.rebase.quiet_subprocess_call are the same thing.
# Move them to a common utility module. Also rewrite more of the subprocess
# calls here in terms of this function (rather than using subprocess directly).
def _subprocess_check_output(cmd, cwd=None):
  """Equivalent of subprocess.check_output, but logs output on error."""
  try:
    return subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError as e:
    logging.error('While running %s%s', cmd, (' in ' + cwd) if cwd else '')
    if e.output:
      logging.error(e.output)
    raise


class Submodule(object):
  """Class representing information for a single submodule."""
  def __init__(self, url, path, head):
    self.url = url
    self.path = path
    self.head = head

  def __repr__(self):
    return '(%s, %s, %s)' % (self.url, self.path, self.head)


def _read_submodule_head(base_path, submodule_path):
  head_path = os.path.join(base_path, '.git', 'modules', submodule_path,
                           'HEAD')
  if not os.path.exists(head_path):
    return None
  with open(head_path, 'r') as f:
    return f.readlines()[0].rstrip()


def get_submodules(base_path, use_gitmodules):
  """Read out all the submodules paths and HEAD revisions.

  Submodules are stored in two places.  .gitmodules is a repository resident
  file that is used for transferring submodule info between different users/
  repositories.  When git submodule sync is called though, its values are
  stored into the repository-local configuration. So use_gitmodules lets us
  switch between these."""
  extra_args = []
  if use_gitmodules:
    if not os.path.exists(os.path.join(base_path, '.gitmodules')):
      return []
    extra_args.extend(['-f', '.gitmodules'])
  p = subprocess.Popen(['git', 'config'] + extra_args + ['--get-regexp',
                       '^submodule\\..*\\.url$'],
                       cwd=base_path,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
  out, _ = p.communicate()
  if p.returncode != 0:
    # There were no matching keys and thus no submodules.
    return []
  submodules = []
  for line in out.splitlines():
    url = line.split()[1]
    url_key = line.split()[0]
    # The url_key looks like it has the path in it, but be careful, that is the
    # original path it was added at.  Any moves will not be reflected.
    orig_path = '.'.join(url_key.split('.')[1:-1])
    # As for the submodule's path in the internal modules directory for it.
    config_path = os.path.join('.git', 'modules', orig_path, 'config')
    try:
      worktree = subprocess.check_output(['git', 'config', '-f', config_path,
                                          '--get', 'core.worktree'],
                                         cwd=base_path,
                                         stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
      continue
    path = os.path.normpath(os.path.join(os.path.dirname(config_path),
                            worktree.rstrip()))
    # Read the submodule's HEAD commit.
    head = _read_submodule_head(base_path, orig_path)
    submodules.append(Submodule(url, path, head))
  return submodules


def has_initial_commit(cwd=None):
  return subprocess.call(
      ['git', 'rev-parse', '--verify', '-q', 'HEAD'],
      cwd=cwd,
      stdout=subprocess.PIPE) == 0


class GitIgnoreChecker():
  """This class indicates which paths are ignored by git.  It uses a
  persistent git child process to answer such questions as quickly and
  accurately as possible."""
  def __init__(self):
    self._processes = {}

  def _get_process(self, cwd):
    if cwd is None:
      cwd = os.getcwd()
    if cwd not in self._processes:
      self._processes[cwd] = subprocess.Popen(
          ['git', 'check-ignore', '-v', '-n', '--stdin'],
          stdout=subprocess.PIPE,
          stdin=subprocess.PIPE)
      assert self._processes[cwd], 'git check-ignore server failed'
    return self._processes[cwd]

  def matches(self, path, cwd=None):
    """Returns whether or not the path matches git repository rooted at cwd."""
    p = self._get_process(cwd)
    p.stdin.write(path + '\n')
    result = p.stdout.readline()
    return not result.startswith('::')


def get_current_email(cwd=None):
  return subprocess.check_output(
      ['git', 'config', 'user.email'], cwd=cwd).rstrip()


def get_current_branch_name(cwd=None):
  return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref=loose',
                                 'HEAD'], cwd=cwd).rstrip()


def set_branch_specific_config(name, value, cwd=None):
  subprocess.check_call(['git', 'config',
                         'branch.%s.%s' % (get_current_branch_name(), name),
                         value], cwd=cwd)


def get_branch_specific_config(name, cwd=None):
  try:
    return subprocess.check_output(
        ['git', 'config',
         'branch.%s.%s' % (get_current_branch_name(), name)], cwd=cwd).rstrip()
  except subprocess.CalledProcessError:
    return None


def canonicalize_commit(commit, cwd=None):
  return subprocess.check_output(['git', 'rev-parse', commit], cwd=cwd).rstrip()


def get_last_landed_commit(cwd=None):
  return subprocess.check_output(['git', 'log', '--first-parent',
                                  '--grep=Reviewed-on:', '-1',
                                  '--pretty=format:%H'], cwd=cwd).rstrip()


def get_oneline_for_commit(commit, cwd=None):
  line = subprocess.check_output(['git', 'rev-list', commit, '--pretty=oneline',
                                  '-n', '1'], cwd=cwd).rstrip()
  return line[line.index(' ') + 1:]


def get_in_flight_commits(cwd=None):
  return subprocess.check_output(
      ['git', 'log', '--first-parent', '--pretty=format:%H',
       '%s..' % get_last_landed_commit()], cwd=cwd).splitlines()


def get_uncommitted_files(cwd=None):
  cmd = ['git', 'diff', '--name-only', '--ignore-submodules', 'HEAD']
  return subprocess.check_output(cmd, cwd=cwd).splitlines()


def get_commit_message(commit, cwd=None):
  cmd = ['git', 'log', '--pretty=format:%B', '-1', commit]
  return subprocess.check_output(cmd, cwd=cwd).splitlines()


def get_remote_branch(treeish, cwd=None):
  cmd = ['git', 'branch', '-r', '--contains', treeish]
  output = subprocess.check_output(cmd, cwd=cwd).splitlines()
  branches = []
  for line in output:
    if '/HEAD' in line:
      continue
    branch = line.strip().split('/')[-1]
    branches.append(branch)
  assert len(branches) == 1, '%s exists in multiple remote branches' % treeish
  return branches[0]


def has_remote_branch(branch, cwd=None):
  remote_head = 'refs/heads/' + branch
  cmd = ['git', 'ls-remote', '--heads']
  output = subprocess.check_output(cmd, cwd=cwd).splitlines()
  for line in output:
    if remote_head in line:
      return True
  return False


def _get_git_dir(cwd):
  try:
    output = subprocess.check_output(['git', 'rev-parse', '--git-dir'],
                                     stderr=subprocess.PIPE, cwd=cwd)
    return os.path.abspath(os.path.join(cwd, output))
  except subprocess.CalledProcessError:
    return None


def is_git_dir(cwd=None):
  # Allow cwd=None as a parameter to match subprocess expectations, but override
  # to os.path.curdir here so that calls to os.path functions can use |cwd|.
  if cwd is None:
    cwd = os.path.curdir
  git_dir = _get_git_dir(cwd)
  parent_git_dir = _get_git_dir(os.path.dirname(os.path.abspath(cwd)))
  if git_dir and git_dir != parent_git_dir:
    return True
  return False


def is_file_git_controlled(path, cwd=None):
  cmd = ['git', 'ls-files', path, '--error-unmatch']
  with open(os.devnull, 'wb') as devnull:
    return subprocess.call(cmd, cwd=cwd,
                           stdout=devnull,
                           stderr=devnull) == 0


def get_file_at_revision(revision, path, cwd=None):
  try:
    return subprocess.check_output(
        ['git', 'show', '%s:%s' % (revision, path)], cwd=cwd,
        stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError, e:
    if e.output:
      if ('exists on disk, but not in' in e.output or
          'does not exist in' in e.output):
        return ''
      logging.error(e.output)
    raise


def get_branch_tracked_remote_url(cwd=None):
  remote_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref',
                                         '--symbolic-full-name', '@{u}'],
                                        cwd=cwd)
  if '/' in remote_name:
    remote_name = remote_name.split('/', 1)[0]
  url = subprocess.check_output(['git', 'config',
                                 'remote.%s.url' % remote_name], cwd=cwd)
  return url.strip()


def reset_to_revision(revision, cwd=None):
  subprocess.check_call(['git', 'fetch'], cwd=cwd)
  subprocess.check_call(['git', 'reset', '--hard', revision], cwd=cwd)


def force_checkout_revision(revision, cwd=None):
  _subprocess_check_output(['git', 'fetch'], cwd=cwd)
  _subprocess_check_output(['git', 'checkout', '-f', revision], cwd=cwd)


def get_head_revision(cwd=None):
  return _subprocess_check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd).strip()


def get_ref_hash(ref, cwd=None):
  """Converts/canonicalizes a reference (tag or hash) into a hash."""
  try:
    output = subprocess.check_output(
        ['git', 'rev-parse', '--verify', '%s^{commit}' % ref], cwd=cwd,
        stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError:
    # Retry the command, but do a more expensive "git fetch" first.
    _subprocess_check_output(['git', 'fetch'], cwd=cwd)
    output = _subprocess_check_output(
        ['git', 'rev-parse', '--verify', '%s^{commit}' % ref], cwd=cwd)

  return output.strip()


def add_to_staging(path, cwd=None):
  """Issue a "git add" command to add |path| to staging."""
  _subprocess_check_output(['git', 'add', path], cwd=cwd)


def add_submodule(url, path):
  subprocess.check_call(['git', 'submodule', 'add', '-f', url, path])


def remove_submodule(path):
  subprocess.check_call(['git', 'submodule', 'deinit', path])
  subprocess.check_call(['git', 'rm', path])


def get_origin_url(cwd=None):
  return subprocess.check_output(['git', 'config', '--get',
                                  'remote.origin.url'], cwd=cwd)
