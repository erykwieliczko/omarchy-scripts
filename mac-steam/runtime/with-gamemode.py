#!/usr/bin/env python3
"""Hold a native GameMode request while muvm runs, without guest LD_PRELOAD."""
import ctypes
import errno
import signal
import subprocess
import sys


def warn(message):
    print(f'Steam Ultimate: {message}', file=sys.stderr, flush=True)


def acquire():
    try:
        client = ctypes.CDLL('libgamemode.so.0')
        for name in ('real_gamemode_request_start', 'real_gamemode_request_end'):
            function = getattr(client, name)
            function.argtypes = []
            function.restype = ctypes.c_int
        client.real_gamemode_error_string.argtypes = []
        client.real_gamemode_error_string.restype = ctypes.c_char_p
        if client.real_gamemode_request_start() == 0:
            return client
        detail = client.real_gamemode_error_string()
        warn('GameMode unavailable; continuing normally: ' +
             (detail.decode(errors='replace') if detail else 'request refused'))
    except (OSError, AttributeError) as error:
        warn(f'GameMode unavailable; continuing normally: {error}')
    return None


def main(command):
    if not command:
        warn('with-gamemode.py needs a command')
        return 2
    client = acquire()
    child = None
    pending_signal = None

    def forward(signum, frame):
        nonlocal pending_signal
        pending_signal = signum
        if child is not None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    previous = {sig: signal.signal(sig, forward)
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        child = subprocess.Popen(command)
        if pending_signal is not None:
            forward(pending_signal, None)
        result = child.wait()
        return result if result >= 0 else 128 - result
    except OSError as error:
        warn(f'Could not start {command[0]}: {error}')
        return 127 if error.errno == errno.ENOENT else 126
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if client is not None and client.real_gamemode_request_end() != 0:
            warn('Could not release GameMode; its daemon will reap this request on exit')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
