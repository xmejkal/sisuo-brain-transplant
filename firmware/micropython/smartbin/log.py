"""
Minimal levelled logging for a microcontroller.

Deliberately not micropython-lib's `logging`: this costs one integer comparison when a level is
disabled, and — the part that actually matters on a device with ~200 KB of RAM — the `%`
formatting never runs, so no string is allocated.

Always pass arguments rather than pre-formatting:
    log.debug("range %d mm", mm)      # good: formats only if DEBUG is on
    log.debug("range %d mm" % mm)     # bad: allocates every call, even when off

`LEVEL` is a module global so it can be changed live from the REPL:
    >>> import smartbin.log as log; log.LEVEL = log.DEBUG
"""

DEBUG = 10
INFO = 20
WARN = 30
ERROR = 40

LEVEL = INFO

_PREFIX = {DEBUG: "D", INFO: "I", WARN: "W", ERROR: "E"}


def _emit(level, message, args):
    if args:
        message = message % args
    print(_PREFIX[level], message)


def debug(message, *args):
    if LEVEL <= DEBUG:
        _emit(DEBUG, message, args)


def info(message, *args):
    if LEVEL <= INFO:
        _emit(INFO, message, args)


def warn(message, *args):
    if LEVEL <= WARN:
        _emit(WARN, message, args)


def error(message, *args):
    if LEVEL <= ERROR:
        _emit(ERROR, message, args)
