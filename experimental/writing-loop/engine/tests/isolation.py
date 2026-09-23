"""The engine's tests run under a throwaway HOME, and a test that opens anything else under the real one fails.

Why: the real home holds the hook registry (~/.awt/loop-workspaces), the notch host's registry, the session
transcripts and the author's workspaces. A test that reads one of them passes or fails with the state of this
machine, and T191 once failed once in a full run and never again. So HOME is replaced before any test runs (engine
code expands `~` when it is called, never at import), subprocesses inherit the replacement, and an audit hook
refuses every open() under the real home that is not this checkout, the interpreter, or a path a runner names in
LOOP_TESTS_ALLOW (os.pathsep-separated). The refusal raises inside the test, so the test that did it is the one
that fails, and every refused path is kept in REFUSED.

Imported first by fixtures.py; a test module that does not use fixtures imports this module itself.
"""
import os
import sys
import tempfile
from pathlib import Path

REAL_HOME = os.path.normpath(os.path.expanduser("~"))
if os.environ.get("LOOP_TESTS_FAKE_HOME") != os.environ.get("HOME"):
    FAKE_HOME = tempfile.mkdtemp(prefix="loop-tests-home-")
    os.environ["LOOP_TESTS_REAL_HOME"] = REAL_HOME
    os.environ["LOOP_TESTS_FAKE_HOME"] = FAKE_HOME
    os.environ["HOME"] = FAKE_HOME
else:
    # A test process started by another test inherits the fake HOME; the real one is the parent's.
    FAKE_HOME = os.environ["HOME"]
    REAL_HOME = os.environ.get("LOOP_TESTS_REAL_HOME", REAL_HOME)

CHECKOUT = Path(__file__).resolve().parents[4]   # engine/tests -> engine -> writing-loop -> experimental -> repo root


def _allowed():
    out = {str(CHECKOUT), os.environ.get("AWT_ROOT") or "", sys.prefix, sys.base_prefix, sys.exec_prefix,
           tempfile.gettempdir(), FAKE_HOME}
    out |= {p for p in sys.path if p}
    out |= set(filter(None, os.environ.get("LOOP_TESTS_ALLOW", "").split(os.pathsep)))
    return tuple(sorted({os.path.normpath(os.path.abspath(p)) for p in out if p}))


ALLOWED = _allowed()
REFUSED = []


def refused(path):
    """Whether opening this path would leave the throwaway home: under the real home and under nothing allowed."""
    p = os.path.normpath(os.path.abspath(os.fsdecode(path)))
    if not (p == REAL_HOME or p.startswith(REAL_HOME + os.sep)):
        return False
    return not any(p == a or p.startswith(a + os.sep) for a in ALLOWED)


def _hook(event, args):
    if event != "open" or not args or isinstance(args[0], int):
        return
    if refused(args[0]):
        p = os.path.normpath(os.path.abspath(os.fsdecode(args[0])))
        REFUSED.append(p)
        raise PermissionError(f"test isolation: a test opened {p}, outside the throwaway HOME ({FAKE_HOME})")


if not getattr(sys, "_loop_tests_isolated", False):
    sys.addaudithook(_hook)
    sys._loop_tests_isolated = True
