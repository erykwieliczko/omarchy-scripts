#!/usr/bin/env python3
"""Exercise the actual plane prepare/cleanup functions with mocked DRM objects.

Usage: panel-retirement.py /path/to/kernel/drivers/gpu/drm/apple/plane.c
This checks reference ownership and the allocation/error paths; it does not
emulate display firmware or replace a kernel boot test.
"""
import pathlib
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()


def function(name, text=source):
    start = text.index("static ", text.index(name) - 20)
    end = text.index("\n}", start) + 2
    return text[start:end]


helper_source = pathlib.Path(sys.argv[1]).with_name('dcp-internal.h').read_text()


prefix = r"""
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
struct drm_framebuffer { int refs; };
struct platform_device { void *data; };
enum { DCP_FIRMWARE_V_13_5=2, DCP_FIRMWARE_V_14_7=3 };
struct apple_dcp { unsigned fw_compat; bool external; };
struct drm_crtc { struct platform_device *dcp; };
struct drm_plane {};
struct drm_plane_state {
    struct drm_crtc *crtc;
    struct drm_framebuffer *fb;
    struct drm_plane_state *state;
};
struct dcp_fb_reference { struct drm_framebuffer *fb; };
struct apple_plane_state {
    struct drm_plane_state base;
    struct dcp_fb_reference *retirement;
};
#define to_apple_plane_state(p) ((struct apple_plane_state *)(p))
#define to_apple_crtc(p) (p)
static int helper_result, allocation_failure;
static void *platform_get_drvdata(struct platform_device *p) { return p->data; }
static int drm_gem_plane_helper_prepare_fb(struct drm_plane *p, struct drm_plane_state *s)
{ (void)p; (void)s; return helper_result; }
static struct drm_plane_state *drm_atomic_get_old_plane_state(struct drm_plane_state *s, struct drm_plane *p)
{ (void)p; return s; }
static void *allocate(size_t n) { return allocation_failure ? NULL : calloc(1, n); }
#define kzalloc_obj(x) allocate(sizeof(x))
#define kfree(p) free(p)
static void drm_framebuffer_get(struct drm_framebuffer *p) { assert(p->refs > 0); p->refs++; }
static void drm_framebuffer_put(struct drm_framebuffer *p) { assert(p->refs > 0); p->refs--; }
"""

tests = r"""
int main(void) {
    struct apple_dcp dcp = {.fw_compat = DCP_FIRMWARE_V_14_7};
    struct platform_device dev = {.data = &dcp};
    struct drm_crtc crtc = {.dcp = &dev};
    struct drm_framebuffer a = {.refs = 1}, b = {.refs = 1};
    struct drm_plane plane = {};
    struct drm_plane_state old = {.crtc = &crtc, .fb = &a};
    struct apple_plane_state next = {.base = {.crtc = &crtc, .fb = &b, .state = &old}};

    /* Reusing a native swapchain must not grow the legacy retirement list. */
    for (int i = 0; i < 100000; i++) {
        assert(apple_plane_prepare_fb(&plane, &next.base) == 0);
        if (next.retirement || a.refs != 1) {
            fprintf(stderr, "FAIL: native swap queued an unretirable framebuffer reference\n");
            return 1;
        }
        apple_plane_cleanup_fb(&plane, &next.base);
    }
    puts("PASS: 100000 native swaps, no legacy entries or reference growth");

    /* Legacy asynchronous presenters still need the displaced buffer pinned.
     * Cleanup also covers an aborted commit before the entry is handed off. */
    dcp.fw_compat = DCP_FIRMWARE_V_13_5;
    for (int i = 0; i < 1000; i++) {
        assert(apple_plane_prepare_fb(&plane, &next.base) == 0);
        assert(next.retirement && next.retirement->fb == &a && a.refs == 2);
        apple_plane_cleanup_fb(&plane, &next.base);
        assert(!next.retirement && a.refs == 1);
    }
    puts("PASS: legacy references retained, aborted commits cleaned up");

    /* The 14.7 external role keeps its existing retirement behavior. */
    dcp.fw_compat = DCP_FIRMWARE_V_14_7;
    dcp.external = true;
    assert(apple_plane_prepare_fb(&plane, &next.base) == 0);
    assert(next.retirement && a.refs == 2);
    apple_plane_cleanup_fb(&plane, &next.base);
    assert(a.refs == 1);
    puts("PASS: 14.7 external display behavior preserved");

    helper_result = -EIO;
    assert(apple_plane_prepare_fb(&plane, &next.base) == -EIO);
    assert(!next.retirement && a.refs == 1);
    helper_result = 0;
    allocation_failure = 1;
    assert(apple_plane_prepare_fb(&plane, &next.base) == -ENOMEM);
    assert(!next.retirement && a.refs == 1);
    allocation_failure = 0;
    next.base.fb = &a;
    assert(apple_plane_prepare_fb(&plane, &next.base) == 0 && !next.retirement);
    next.base.fb = &b;
    old.crtc = NULL;
    assert(apple_plane_prepare_fb(&plane, &next.base) == 0 && !next.retirement);
    old.crtc = &crtc;
    old.fb = NULL;
    assert(apple_plane_prepare_fb(&plane, &next.base) == 0 && !next.retirement);
    next.base.state = NULL;
    assert(apple_plane_prepare_fb(&plane, &next.base) == 0 && !next.retirement);
    puts("PASS: preparation errors, allocation failure, unchanged and inactive planes");
    return 0;
}
"""

with tempfile.TemporaryDirectory(prefix="aoe-panel-retirement-") as tmp:
    c = pathlib.Path(tmp, "test.c")
    c.write_text(prefix + function('dcp_is_v14_7_panel', helper_source) + '\n' +
                 function("apple_plane_cleanup_fb") + "\n" +
                 function("apple_plane_prepare_fb") + tests)
    binary = pathlib.Path(tmp, "test")
    subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-Wno-unused-parameter", "-Wno-unused-function",
                    str(c), "-o", str(binary)], check=True)
    sys.exit(subprocess.run([str(binary)]).returncode)
