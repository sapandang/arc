# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build libjnigraphics.so."""

from make_to_ninja import MakefileNinjaTranslator
import ninja_generator
import open_source
import staging


def generate_ninjas():
  if open_source.is_open_source_repo():
    # Provide a stub.
    n = ninja_generator.SharedObjectNinjaGenerator('libjnigraphics')
    n.add_notice_sources([staging.as_staging('src/NOTICE')])
    n.link()
    return

  MakefileNinjaTranslator(
      'android/frameworks/base/native/graphics/jni').generate()
