#!/usr/bin/env python3
"""Run Wine's actual set_focus/recovery functions against an isolated X server.
Usage: python3 test-focus-retry.py PATH/TO/dlls/winex11.drv/event.c
Wine/Win32 plumbing is stubbed; timestamp rejection and focus changes use Xlib.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def function(source, signature):
    start = source.index(signature)
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


prefix = r'''
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
typedef uintptr_t HWND;
typedef struct {int cbSize; HWND hwndFocus, hwndActive;} GUITHREADINFO;
#define TRACE(...) ((void)0)
#define GA_ROOT 2
static Atom atom_active, atom_time;
#define x11drv_atom(n) atom_##n
#define atom__NET_ACTIVE_WINDOW atom_active
#define atom_TIMESTAMP atom_time
static Window target, other;
static int supported=1, get_calls, switch_during_retry;
static struct {int ignore_focus_hack;} td;
static void *x11drv_thread_data_unused;
#define x11drv_thread_data() (&td)
static void NtUserSetForegroundWindowInternal(HWND w){}
static void NtUserGetGUIThreadInfo(int i, GUITHREADINFO *t){t->hwndFocus=target;t->hwndActive=target;}
static HWND NtUserGetAncestor(HWND w,int i){return w;}
static Window X11DRV_get_whole_window(HWND w){return w;}
static int is_net_supported(Atom a){return supported;}
static void select_window(Display*d,Window w){
 XChangeProperty(d,DefaultRootWindow(d),atom_active,XA_WINDOW,32,PropModeReplace,(unsigned char*)&w,1);
 XSync(d,False);
}
static Window get_net_active_window(Display*d){
 if(++get_calls==2 && switch_during_retry){
  select_window(d,other);XSetInputFocus(d,other,RevertToParent,CurrentTime);XSync(d,False);
 }
 Atom type;int fmt;unsigned long n,left;unsigned char *v=NULL;Window w=None;
 XGetWindowProperty(d,DefaultRootWindow(d),atom_active,0,1,False,XA_WINDOW,&type,&fmt,&n,&left,&v);
 if(v&&n)memcpy(&w,v,sizeof(w));if(v)XFree(v);return w;
}
static void wait_grab_pointer(Display*d){
 /* Reproduce another client advancing last-focus-change while Wine waits. */
 usleep(20000);XSetInputFocus(d,other,RevertToParent,CurrentTime);XSync(d,False);
}
static Time server_time(Display*d){
 XSetWindowAttributes a={.event_mask=PropertyChangeMask};XEvent e;
 Window w=XCreateWindow(d,DefaultRootWindow(d),0,0,1,1,0,0,InputOnly,CopyFromParent,CWEventMask,&a);
 XChangeProperty(d,w,atom_time,XA_INTEGER,8,PropModeAppend,NULL,0);
 XWindowEvent(d,w,PropertyChangeMask,&e);XDestroyWindow(d,w);XSync(d,False);return e.xproperty.time;
}
'''
suffix = r'''
int main(){
 Display*d=XOpenDisplay(NULL);if(!d)return 2;
 atom_active=XInternAtom(d,"_NET_ACTIVE_WINDOW",False);atom_time=XInternAtom(d,"TIMESTAMP",False);
 target=XCreateSimpleWindow(d,DefaultRootWindow(d),0,0,50,50,0,0,0);
 other=XCreateSimpleWindow(d,DefaultRootWindow(d),60,0,50,50,0,0,0);
 XMapWindow(d,target);XMapWindow(d,other);XSync(d,False);
 int failures=0;
 for(int test=0;test<5;test++){
  supported=test!=2; switch_during_retry=test==3;get_calls=0;
  select_window(d,test==1?other:target);
  Time t=server_time(d);if(test==4)t=CurrentTime;
  set_focus(d,target,t);
  Window f;int r;XGetInputFocus(d,&f,&r);
  int should_focus=test==0||test==4;
  int ok=(f==target)==should_focus;
  const char*names[]={"stale offer, WM still selects target", "user switched away", "no WM active-window support", "user switches during retry", "CurrentTime request"};
  printf("%s: %s\n",ok?"PASS":"FAIL",names[test]);failures+=!ok;
 }
 XCloseDisplay(d);return !!failures;
}
'''
source = Path(sys.argv[1]).read_text()
helper = ''
if 'static void retry_rejected_focus(' in source:
    helper = function(source, 'static void retry_rejected_focus(')
body = function(source, 'static void set_focus(')
with tempfile.TemporaryDirectory(prefix='wine-focus-test-') as directory:
    path = Path(directory)
    (path/'test.c').write_text(prefix + helper + '\n' + body + '\n' + suffix)
    subprocess.run(['cc', '-O2', str(path/'test.c'), '-lX11', '-o', str(path/'test')], check=True)
    with (path/'xvfb.log').open('w') as log:
        server = subprocess.Popen(['Xvfb', '-displayfd', '1', '-screen', '0', '640x480x24', '-nolisten', 'tcp'],
                                  stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            display = server.stdout.readline().strip()
            if not display.isdecimal():
                raise SystemExit('Xvfb did not start')
            result = subprocess.run([str(path/'test')], env=dict(os.environ, DISPLAY=':'+display), timeout=10)
        finally:
            server.terminate()
            server.wait(timeout=5)
    raise SystemExit(result.returncode)
