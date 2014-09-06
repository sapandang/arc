#!/usr/bin/env python
# ARC MOD TRACK "third_party/tools/depot_tools/tests/owners_unittest.py"
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for owners.py."""

import os
import sys
import unittest

# ARC MOD BEGIN
# Add import path of third_party/tools/depot_tools which allows us to import
# testing support.
import owners

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'tools/depot_tools'))

from testing_support import filesystem_mock
# ARC MOD END

ben = 'ben@example.com'
brett = 'brett@example.com'
darin = 'darin@example.com'
john = 'john@example.com'
ken = 'ken@example.com'
peter = 'peter@example.com'
tom = 'tom@example.com'


def owners_file(*email_addresses, **kwargs):
  s = ''
  if kwargs.get('comment'):
    s += '# %s\n' % kwargs.get('comment')
  if kwargs.get('noparent'):
    s += 'set noparent\n'
  s += '\n'.join(kwargs.get('lines', [])) + '\n'
  return s + '\n'.join(email_addresses) + '\n'


def test_repo():
  return filesystem_mock.MockFileSystem(files={
    '/DEPS' : '',
    '/OWNERS': owners_file(owners.EVERYONE),
    '/base/vlog.h': '',
    '/chrome/OWNERS': owners_file(ben, brett),
    '/chrome/browser/OWNERS': owners_file(brett),
    '/chrome/browser/defaults.h': '',
    '/chrome/gpu/OWNERS': owners_file(ken),
    '/chrome/gpu/gpu_channel.h': '',
    '/chrome/renderer/OWNERS': owners_file(peter),
    '/chrome/renderer/gpu/gpu_channel_host.h': '',
    '/chrome/renderer/safe_browsing/scorer.h': '',
    '/content/OWNERS': owners_file(john, darin, comment='foo', noparent=True),
    '/content/content.gyp': '',
    '/content/bar/foo.cc': '',
    '/content/baz/OWNERS': owners_file(brett),
    '/content/baz/froboz.h': '',
    '/content/baz/ugly.cc': '',
    '/content/baz/ugly.h': '',
    '/content/views/OWNERS': owners_file(ben, john, owners.EVERYONE,
                                         noparent=True),
    '/content/views/pie.h': '',
  })


class _BaseTestCase(unittest.TestCase):
  def setUp(self):
    self.repo = test_repo()
    self.files = self.repo.files
    self.root = '/'
    self.fopen = self.repo.open_for_reading
    self.glob = self.repo.glob

  def db(self, root=None, fopen=None, os_path=None, glob=None):
    root = root or self.root
    fopen = fopen or self.fopen
    os_path = os_path or self.repo
    glob = glob or self.glob
    return owners.Database(root, fopen, os_path, glob)


class OwnersDatabaseTest(_BaseTestCase):
  def test_constructor(self):
    self.assertNotEquals(self.db(), None)

  def test_files_not_covered_by__valid_inputs(self):
    db = self.db()

    # Check that we're passed in a sequence that isn't a string.
    self.assertRaises(AssertionError, db.files_not_covered_by, 'foo', [])
    if hasattr(owners.collections, 'Iterable'):
      self.assertRaises(AssertionError, db.files_not_covered_by,
                        (f for f in ['x', 'y']), [])

    # Check that the files are under the root.
    db.root = '/checkout'
    self.assertRaises(AssertionError, db.files_not_covered_by,
                      ['/OWNERS'], [])
    db.root = '/'

    # Check invalid email address.
    self.assertRaises(AssertionError, db.files_not_covered_by,
                      ['OWNERS'], ['foo'])

  def assert_files_not_covered_by(self, files, reviewers, unreviewed_files):
    db = self.db()
    self.assertEquals(db.files_not_covered_by(set(files), set(reviewers)),
                      set(unreviewed_files))

  def test_files_not_covered_by__owners_propagates_down(self):
    self.assert_files_not_covered_by(
      ['chrome/gpu/gpu_channel.h', 'chrome/renderer/gpu/gpu_channel_host.h'],
      [ben], [])

  def test_files_not_covered_by__partial_covering(self):
    self.assert_files_not_covered_by(
      ['content/content.gyp', 'chrome/renderer/gpu/gpu_channel_host.h'],
      [peter], ['content/content.gyp'])

  def test_files_not_covered_by__set_noparent_works(self):
    self.assert_files_not_covered_by(['content/content.gyp'], [ben],
                                    ['content/content.gyp'])

  def test_files_not_covered_by__no_reviewer(self):
    self.assert_files_not_covered_by(
      ['content/content.gyp', 'chrome/renderer/gpu/gpu_channel_host.h'],
      [], ['content/content.gyp'])

  def test_files_not_covered_by__combines_directories(self):
    self.assert_files_not_covered_by(['content/content.gyp',
                                     'content/bar/foo.cc',
                                     'chrome/renderer/gpu/gpu_channel_host.h'],
                                    [peter],
                                    ['content/content.gyp',
                                     'content/bar/foo.cc'])

  def test_files_not_covered_by__multiple_directories(self):
    self.assert_files_not_covered_by(
        ['content/content.gyp',                    # Not covered
         'content/bar/foo.cc',                     # Not covered (combines in)
         'content/baz/froboz.h',                   # Not covered
         'chrome/gpu/gpu_channel.h',               # Owned by ken
         'chrome/renderer/gpu/gpu_channel_host.h'  # Owned by * via parent
        ],
        [ken],
        ['content/content.gyp', 'content/bar/foo.cc', 'content/baz/froboz.h'])

  def test_per_file(self):
    # brett isn't allowed to approve ugly.cc
    self.files['/content/baz/OWNERS'] = owners_file(brett,
        lines=['per-file ugly.*=tom@example.com'])
    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [brett],
                                    [])

    # tom is allowed to approve ugly.cc, but not froboz.h
    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [tom],
                                    [])
    self.assert_files_not_covered_by(['content/baz/froboz.h'],
                                    [tom],
                                    ['content/baz/froboz.h'])

  def test_per_file_with_spaces(self):
    # This is the same as test_per_file(), except that we include spaces
    # on the per-file line. brett isn't allowed to approve ugly.cc;
    # tom is allowed to approve ugly.cc, but not froboz.h
    self.files['/content/baz/OWNERS'] = owners_file(brett,
        lines=['per-file ugly.* = tom@example.com'])
    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [brett],
                                    [])

    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [tom],
                                    [])
    self.assert_files_not_covered_by(['content/baz/froboz.h'],
                                    [tom],
                                    ['content/baz/froboz.h'])

  def test_per_file__set_noparent(self):
    self.files['/content/baz/OWNERS'] = owners_file(brett,
        lines=['per-file ugly.*=tom@example.com',
               'per-file ugly.*=set noparent'])

    # brett isn't allowed to approve ugly.cc
    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [brett],
                                    ['content/baz/ugly.cc'])

    # tom is allowed to approve ugly.cc, but not froboz.h
    self.assert_files_not_covered_by(['content/baz/ugly.cc'],
                                    [tom],
                                    [])

    self.assert_files_not_covered_by(['content/baz/froboz.h'],
                                    [tom],
                                    ['content/baz/froboz.h'])

  def test_per_file_wildcard(self):
    self.files['/OWNERS'] = 'per-file DEPS=*\n'
    self.assert_files_not_covered_by(['DEPS'], [brett], [])

  def test_mock_relpath(self):
    # This test ensures the mock relpath has the arguments in the right
    # order; this should probably live someplace else.
    self.assertEquals(self.repo.relpath('foo/bar.c', 'foo/'), 'bar.c')
    self.assertEquals(self.repo.relpath('/bar.c', '/'), 'bar.c')

  def test_per_file_glob_across_dirs_not_allowed(self):
    self.files['/OWNERS'] = 'per-file content/*=john@example.org\n'
    self.assertRaises(owners.SyntaxErrorInOwnersFile,
        self.db().files_not_covered_by, ['DEPS'], [brett])

  def assert_syntax_error(self, owners_file_contents):
    db = self.db()
    self.files['/foo/OWNERS'] = owners_file_contents
    self.files['/foo/DEPS'] = ''
    try:
      db.reviewers_for(['foo/DEPS'], None)
      self.fail()  # pragma: no cover
    except owners.SyntaxErrorInOwnersFile, e:
      self.assertTrue(str(e).startswith('/foo/OWNERS:1'))

  def test_syntax_error__unknown_token(self):
    self.assert_syntax_error('{}\n')

  def test_syntax_error__unknown_set(self):
    self.assert_syntax_error('set myfatherisbillgates\n')

  def test_syntax_error__bad_email(self):
    self.assert_syntax_error('ben\n')


class ReviewersForTest(_BaseTestCase):
  def assert_reviewers_for(self, files, potential_suggested_reviewers,
                           author=None):
    db = self.db()
    suggested_reviewers = db.reviewers_for(set(files), author)
    self.assertTrue(suggested_reviewers in
        [set(suggestion) for suggestion in potential_suggested_reviewers])

  def test_reviewers_for__basic_functionality(self):
    self.assert_reviewers_for(['chrome/gpu/gpu_channel.h'],
                              [[ken]])

  def test_reviewers_for__set_noparent_works(self):
    self.assert_reviewers_for(['content/content.gyp'],
                              [[john],
                               [darin]])

  def test_reviewers_for__valid_inputs(self):
    db = self.db()

    # Check that we're passed in a sequence that isn't a string.
    self.assertRaises(AssertionError, db.reviewers_for, 'foo', None)
    if hasattr(owners.collections, 'Iterable'):
      self.assertRaises(AssertionError, db.reviewers_for,
                        (f for f in ['x', 'y']), None)

    # Check that the files are under the root.
    db.root = '/checkout'
    self.assertRaises(AssertionError, db.reviewers_for, ['/OWNERS'], None)

  def test_reviewers_for__wildcard_dir(self):
    self.assert_reviewers_for(['DEPS'], [['<anyone>']])
    self.assert_reviewers_for(['DEPS', 'chrome/gpu/gpu_channel.h'], [[ken]])

  def test_reviewers_for__one_owner(self):
    self.assert_reviewers_for([
        'chrome/gpu/gpu_channel.h',
        'content/baz/froboz.h',
        'chrome/renderer/gpu/gpu_channel_host.h'],
        [[brett]])

  def test_reviewers_for__two_owners(self):
    self.assert_reviewers_for([
        'chrome/gpu/gpu_channel.h',
        'content/content.gyp',
        'content/baz/froboz.h',
        'content/views/pie.h'],
        [[ken, john]])

  def test_reviewers_for__all_files(self):
    self.assert_reviewers_for([
        'chrome/gpu/gpu_channel.h',
        'chrome/renderer/gpu/gpu_channel_host.h',
        'chrome/renderer/safe_browsing/scorer.h',
        'content/content.gyp',
        'content/bar/foo.cc',
        'content/baz/froboz.h',
        'content/views/pie.h'],
        [[peter, ken, john]])

  def test_reviewers_for__per_file_owners_file(self):
    self.files['/content/baz/OWNERS'] = owners_file(lines=[
        'per-file ugly.*=tom@example.com'])
    self.assert_reviewers_for(['content/baz/OWNERS'],
                              [[john],
                               [darin]])

  def test_reviewers_for__per_file(self):
    self.files['/content/baz/OWNERS'] = owners_file(lines=[
        'per-file ugly.*=tom@example.com'])
    self.assert_reviewers_for(['content/baz/ugly.cc'],
                              [[tom]])

  def test_reviewers_for__two_nested_dirs(self):
    # The same owner is listed in two directories (one above the other)
    self.assert_reviewers_for(['chrome/browser/defaults.h'],
                              [[brett]])

    # Here, although either ben or brett could review both files,
    # someone closer to the gpu_channel_host.h should also be suggested.
    # This also tests that we can handle two suggested reviewers
    # with overlapping sets of directories properly.
    self.files['/chrome/renderer/gpu/OWNERS'] = owners_file(ken)
    self.assert_reviewers_for(['chrome/OWNERS',
                               'chrome/renderer/gpu/gpu_channel_host.h'],
                              [[ben, ken],
                               [brett, ken]])

  def test_reviewers_for__author_is_known(self):
    # We should never suggest ken as a reviewer for his own changes.
    self.assert_reviewers_for(['chrome/gpu/gpu_channel.h'],
                              [[ben], [brett]], author=ken)


class LowestCostOwnersTest(_BaseTestCase):
  # Keep the data in the test_lowest_cost_owner* methods as consistent with
  # test_repo() where possible to minimize confusion.

  def check(self, possible_owners, dirs, *possible_lowest_cost_owners):
    suggested_owner = owners.Database.lowest_cost_owner(possible_owners, dirs)
    self.assertTrue(suggested_owner in possible_lowest_cost_owners)

  def test_one_dir_with_owner(self):
    # brett is the only immediate owner for stuff in baz; john is also
    # an owner, but further removed. We should always get brett.
    self.check({brett: [('content/baz', 1)],
                john:  [('content/baz', 2)]},
               ['content/baz'],
               brett)

    # john and darin are owners for content; the suggestion could be either.
  def test_one_dir_with_two_owners(self):
    self.check({john:  [('content', 1)],
                darin: [('content', 1)]},
               ['content'],
               john, darin)

  def test_one_dir_with_two_owners_in_parent(self):
    # As long as the distance is the same, it shouldn't matter (brett isn't
    # listed in this case).
    self.check({john:  [('content/baz', 2)],
                darin: [('content/baz', 2)]},
               ['content/baz'],
               john, darin)

  def test_two_dirs_two_owners(self):
    # If they both match both dirs, they should be treated equally.
    self.check({john:  [('content/baz', 2), ('content/bar', 2)],
                darin: [('content/baz', 2), ('content/bar', 2)]},
               ['content/baz', 'content/bar'],
               john, darin)

    # Here brett is better since he's closer for one of the two dirs.
    self.check({brett: [('content/baz', 1), ('content/views', 1)],
                darin: [('content/baz', 2), ('content/views', 1)]},
               ['content/baz', 'content/views'],
               brett)

  def test_hierarchy(self):
    # the choices in these tests are more arbitrary value judgements;
    # also, here we drift away from test_repo() to cover more cases.

    # Here ben isn't picked, even though he can review both; we prefer
    # closer reviewers.
    self.check({ben: [('chrome/gpu', 2), ('chrome/renderer', 2)],
                ken: [('chrome/gpu', 1)],
                peter: [('chrome/renderer', 1)]},
               ['chrome/gpu', 'chrome/renderer'],
               ken, peter)

    # Here we always pick ben since he can review either dir as well as
    # the others but can review both (giving us fewer total reviewers).
    self.check({ben: [('chrome/gpu', 1), ('chrome/renderer', 1)],
                ken: [('chrome/gpu', 1)],
                peter: [('chrome/renderer', 1)]},
               ['chrome/gpu', 'chrome/renderer'],
               ben)

    # However, three reviewers is too many, so ben gets this one.
    self.check({ben: [('chrome/gpu', 2), ('chrome/renderer', 2),
                      ('chrome/browser', 2)],
                ken: [('chrome/gpu', 1)],
                peter: [('chrome/renderer', 1)],
                brett: [('chrome/browser', 1)]},
               ['chrome/gpu', 'chrome/renderer',
                'chrome/browser'],
               ben)
# ARC MOD BEGIN
# Add ReviewerSet tests

elijah = 'elijah@example.com'
evgeny = 'evgeny@example.com'
hamaji = 'hamaji@example.com'
lloyd = 'lloyd@example.com'
nikolay = 'nikolay@example.com'
satoru = 'satoru@example.com'
yusuke = 'yusuke@example.com'

def arc_test_repo():
  return filesystem_mock.MockFileSystem(files={
    '/OWNERS': owners_file(hamaji, yusuke, comment='misc'),
    '/mods/android/random.c': '',
    '/src/build/cts/OWNERS': owners_file(lloyd, lines=
        ['per-file cts_run_configuration.py=*']),
    '/src/build/cts/cts_run_configuration.py': '',
    '/src/build/cts/random.c': '',
    '/src/ndk_translation/OWNERS': owners_file(evgeny, nikolay),
    '/src/packaging/OWNERS': owners_file(elijah, comment='packaging'),
    '/src/packaging/runtime/filesystem.js': '',
    '/src/plugin/OWNERS': owners_file(ken),
    '/src/plugin/file_system_manager.cc': '',
    '/src/posix_translation/OWNERS': owners_file(satoru),
    '/src/posix_translation/external_file.cc': ''
  })


class _ArcTestCase(_BaseTestCase):
  def setUp(self):
    self.repo = arc_test_repo()
    self.files = self.repo.files
    self.root = '/'
    self.fopen = self.repo.open_for_reading
    self.glob = self.repo.glob


class ReviewerSetTest(_ArcTestCase):
  def get_reviewer_set(self, files, author=None):
    db = self.db()
    if author is None:
      author = 'unknown'
    return db.reviewer_set_for(set(files), author)

  def test_simple_alternate(self):
    rs = self.get_reviewer_set(['mods/android/random.c'])
    chosen = None
    if hamaji in rs.reviewers:
      chosen = hamaji
      other = yusuke
    else:
      chosen = yusuke
      other = hamaji
    self.assertFalse(other in rs.reviewers)
    self.assertTrue(rs.reviewers[chosen].alternates == set([other]))

  def test_no_alternates(self):
    rs = self.get_reviewer_set(['src/packaging/runtime/filesystem.js',
                                'src/plugin/file_system_manager.cc',
                                'src/posix_translation/external_file.cc'])
    for r in [elijah, ken, satoru]:
      self.assertTrue(r in rs.reviewers)
      self.assertTrue(len(rs.reviewers[r].alternates) == 0)
    self.assertTrue('packaging' in rs.reviewers[elijah].comments)
    l = rs.reviewers[elijah].comments['packaging']
    self.assertTrue(len(l) == 1)
    self.assertTrue(l[0] == 'src/packaging/runtime/filesystem.js')

  def test_reduced_alternates(self):
    rs = self.get_reviewer_set(['src/build/cts/cts_run_configuration.py',
                                'src/ndk_translation/trampolines.cc'])
    # There should be only an owner for trampolines.cc because
    # cts_run_configuration.py has no owner.
    self.assertTrue(len(rs.reviewers) == 1)
    # And alternates listed for trampolines.cc
    primary = evgeny
    alternate = nikolay
    if not evgeny in rs.reviewers:
      primary = nikolay
      alternate = evgeny
    self.assertTrue(rs.reviewers[primary].alternates == set([alternate]))

# ARC MOD END

if __name__ == '__main__':
  unittest.main()
