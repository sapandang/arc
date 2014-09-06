#!/usr/bin/python
#
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Naclize *.S files.

import sys


class RewriterBase(object):
  """Converts a .S file to a NaCl compatible one."""

  def __init__(self, file_name):
    self.__file_name = file_name
    self._result = ['// Generated by %s from' % sys.argv[0],
                    '// %s. Do not edit.' % file_name]

  def _rewriter(self, line):
    """Tries to rewrite the line.

    Returns True if the line is actually rewritten. A derived class must
    override the method."""
    raise NotImplementedError('Please implement this in a derived class.')

  def rewrite(self):
    with open(self.__file_name) as f:
      for line in f.readlines():
        if self._rewriter(line):
          continue
        # If neither of them consumes the line, just add it to _result.
        self._result.append(line.rstrip('\n'))

  def print_result(self):
    """Prints the _result to stdout."""
    print('\n'.join(self._result))
