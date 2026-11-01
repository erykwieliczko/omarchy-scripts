#!/usr/bin/env python3
"""Compile the actual policy function and check opt-in/board/external isolation."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source=Path(sys.argv[1]).read_text()
match=re.search(r'bool dcp_v14_board_stamps_swaps\([^\n]*\)\n\{.*?\n\}',source,re.S)
assert match, 'Policy function not found'
harness='''
#include <stdbool.h>
#include <stddef.h>
#include <assert.h>
#define READ_ONCE(x) (x)
struct dcp_v14_board { bool swap_timestamps; };
static const struct dcp_v14_board dcp_v14_board_t6030 = { false };
static const struct dcp_v14_board stamped = { true }, unstamped = { false };
static bool t6030_swap_timestamps;
'''+match[0]+'''
int main(void) {
    for (int enabled=0;enabled<2;enabled++) {
        t6030_swap_timestamps=enabled;
        assert(!dcp_v14_board_stamps_swaps(NULL,false));
        assert(dcp_v14_board_stamps_swaps(&dcp_v14_board_t6030,false)==enabled);
        assert(!dcp_v14_board_stamps_swaps(&dcp_v14_board_t6030,true));
        assert(dcp_v14_board_stamps_swaps(&stamped,false));
        assert(!dcp_v14_board_stamps_swaps(&stamped,true));
        assert(!dcp_v14_board_stamps_swaps(&unstamped,false));
        assert(!dcp_v14_board_stamps_swaps(&unstamped,true));
    }
}
'''
with tempfile.TemporaryDirectory(prefix='aoe2-panel-policy-') as directory:
    path=Path(directory)
    (path/'test.c').write_text(harness)
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',str(path/'test.c'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
print('PASS: default path, T6030 opt-in, other boards and external processors')
