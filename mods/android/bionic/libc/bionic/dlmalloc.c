/*
 * Copyright (C) 2012 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "dlmalloc.h"
// ARC MOD BEGIN
// Add an #include.
#include <irt_syscalls.h>
// ARC MOD END

#include "private/bionic_name_mem.h"
#include "private/libc_logging.h"

// Send dlmalloc errors to the log.
static void __bionic_heap_corruption_error(const char* function);
static void __bionic_heap_usage_error(const char* function, void* address);
#define PROCEED_ON_ERROR 0
#define CORRUPTION_ERROR_ACTION(m) __bionic_heap_corruption_error(__FUNCTION__)
#define USAGE_ERROR_ACTION(m,p) __bionic_heap_usage_error(__FUNCTION__, p)

/* Bionic named anonymous memory declarations */
static void* named_anonymous_mmap(size_t length);
#define MMAP(s) named_anonymous_mmap(s)
#define DIRECT_MMAP(s) named_anonymous_mmap(s)

// Ugly inclusion of C file so that bionic specific #defines configure dlmalloc.
#include "../upstream-dlmalloc/malloc.c"

extern void (*__cleanup)();

static void __bionic_heap_corruption_error(const char* function) {
  // ARC MOD BEGIN
  // Add __nacl_irt_write_real because __libc_android_log_write may
  // not work. For unittests, /dev/log/main cannot be opened. When
  // debug malloc is enabled, libc_malloc_debug_leak.so tries to
  // open /dev/log/main in its global initializer before
  // posix_translation is initialized. Even for production ARC,
  // posix_translation may not work well after a heap error as it
  // does a lot of allocations.
  size_t nwrote;
  char buffer[512] = {};
  snprintf(buffer, sizeof(buffer) - 1,
           "heap corruption detected by %s", function);
  __nacl_irt_write_real(STDERR_FILENO, buffer, strlen(buffer), &nwrote);
  // ARC MOD END
  __cleanup = NULL; // The heap is corrupt. We can forget trying to shut down stdio.
  __libc_fatal("heap corruption detected by %s", function);
}

static void __bionic_heap_usage_error(const char* function, void* address) {
  // ARC MOD BEGIN
  // The same as above.
  size_t nwrote;
  char buffer[512] = {};
  snprintf(buffer, sizeof(buffer) - 1,
           "invalid address or address of corrupt block %p passed to %s",
           address, function);
  __nacl_irt_write_real(STDERR_FILENO, buffer, strlen(buffer), &nwrote);
  // ARC MOD END
  __libc_fatal_no_abort("invalid address or address of corrupt block %p passed to %s",
               address, function);
  // So that debuggerd gives us a memory dump around the specific address.
  // TODO: improve the debuggerd protocol so we can tell it to dump an address when we abort.
  *((int**) 0xdeadbaad) = (int*) address;
}

static void* named_anonymous_mmap(size_t length)
{
    void* ret;
    ret = mmap(NULL, length, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (ret == MAP_FAILED)
        return ret;

    __bionic_name_mem(ret, length, "libc_malloc");

    return ret;
}
