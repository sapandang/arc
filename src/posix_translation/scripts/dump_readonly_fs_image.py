#!src/build/run_python
#
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Dumps a readonly image file generated by create_readonly_fs_image.py.

Usage:

$ src/posix_translation/scripts/dump_readonly_fs_image.py \
    out/target/<target>/posix_translation_gen_sources/readonly_fs_image.img
"""

import argparse
import array
import os
import struct
import sys
import time
import traceback


_PAGE_SIZE = 64 * 1024  # NaCl 64bit uses 64k page.

# File type constants, which should be consistent with ones in
# readonly_fs_reader.h.
_REGULAR_FILE = 0
_SYMBOLIC_LINK = 1
_EMPTY_DIRECTORY = 2


def _read_integer(image, offset):
  # Reads a 4-byte big endian integer from the next word boundary of
  # image[offset] and return a tuple of the integer and new offset.
  offset = _seek_to_next_boundary(image, offset, 4)
  result = struct.unpack_from('>i', image, offset)[0]
  return (result, offset + 4)


def _read_string(image, offset):
  # Reads a zero-terminated string from image[offset] and return a tuple of the
  # string and new offset.
  result = ''
  while image[offset] != 0:
    result += chr(image[offset])
    offset += 1
  return (result, offset + 1)


def _seek_to_next_boundary(image, offset, boundary):
  # Rounds up the offset to a next boundary.
  offset = (offset + boundary - 1) & ~(boundary - 1)
  image[offset]  # validate offset
  return offset


def _format_message(offset, size, mtime, filetype, filename, link_target):
  if filetype == _REGULAR_FILE:
    filetype_name = "file"
  elif filetype == _SYMBOLIC_LINK:
    filetype_name = "symlink"
  elif filetype == _EMPTY_DIRECTORY:
    filetype_name = "empty_dir"
  page_num = offset / _PAGE_SIZE
  message = '[%s] %s %d bytes at 0x%08x (page %d, "%s")' % (
      filetype_name, filename, size, offset, page_num, time.ctime(mtime))
  if link_target:
    message += ' -> %s' % link_target
  return message


def _find_file(image, num_files, index, dump_filename, verbose):
  dump_offset = -1
  dump_size = -1
  dump_mtime = -1
  for i in xrange(num_files):
    if verbose:
      print 'VERBOSE: Reading file #%d at file offset %d.' % (i, index)
    (offset, index) = _read_integer(image, index)
    (size, index) = _read_integer(image, index)
    (mtime, index) = _read_integer(image, index)
    (filetype, index) = _read_integer(image, index)
    (filename, index) = _read_string(image, index)
    link_target = None
    if filetype == _SYMBOLIC_LINK:
      (link_target, index) = _read_string(image, index)
    if not dump_filename or verbose:
      # ls mode or verbose mode.
      print _format_message(offset, size, mtime, filetype, filename,
                            link_target)
    if dump_filename == filename:
      dump_offset = offset
      dump_size = size
      dump_mtime = mtime
      break

  return dump_offset, dump_size, dump_mtime


def _read_image(image_filename, dump_filename, verbose):
  # Parses the metadata part of image_filename. If dump_filename is None, prints
  # the metadata in human-readable form. If dump_filename is not None, prints
  # the content of the dump_filename.
  image = array.array('B')
  with open(image_filename, "r") as f:
    size = os.stat(image_filename).st_size
    image.fromfile(f, size)

    if verbose:
      print 'VERBOSE: Image %s opened (size=%d)' % (image_filename, size)

    try:
      index = 0
      num_files, index = _read_integer(image, index)

      if verbose:
        print 'VERBOSE: Image contains %d files.' % num_files

      dump_offset, dump_size, dump_mtime = _find_file(image, num_files, index,
                                                      dump_filename, verbose)

      if not dump_filename:
        return

      # dump mode.
      if dump_offset == -1:
        print '%s is not in image' % dump_filename
        sys.exit(-1)

      index = _seek_to_next_boundary(image, index, _PAGE_SIZE)
      dump_offset += index  # fix-up the offset
      if verbose:
        print 'VERBOSE: Dumping %s at file offset %d.' % (dump_filename,
                                                          dump_offset)
      image[dump_offset:dump_offset + dump_size].tofile(sys.stdout)
    except IndexError:
      traceback.print_exc()
      sys.exit(-1)


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose', action='store_true', help='Emit '
                      'verbose output.')
  parser.add_argument('-d', '--dump', metavar='FILENAME', help='Instead of '
                      'printing a list of files, dump the list to a file.')
  parser.add_argument(dest='input', metavar=('INPUT'), help='Image file.')
  args = parser.parse_args()

  _read_image(args.input, args.dump, args.verbose)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

# TODO(crbug.com/242315): Remove this script. We can provide the same command
# based on posix_translation/readonly_fs_reader.cc. This way, we can remove
# one of the two readonly fs image decoders.
