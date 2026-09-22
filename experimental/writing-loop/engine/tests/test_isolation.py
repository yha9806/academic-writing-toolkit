"""The tests cannot see this machine's home: HOME is a throwaway directory and opening the real one fails."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

import isolation as I


class IsolationTest(unittest.TestCase):
    def test_home_is_a_throwaway_directory(self):
        self.assertNotEqual(os.path.normpath(os.path.expanduser("~")), I.REAL_HOME)
        self.assertTrue(os.path.expanduser("~/.awt/loop-workspaces").startswith(I.FAKE_HOME + os.sep))
        out = subprocess.run([sys.executable, "-c", "import os; print(os.path.expanduser('~'))"],
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, I.FAKE_HOME, "a subprocess inherits the throwaway HOME")

    def test_opening_the_real_home_fails_in_the_test_that_did_it(self):
        # A path that does not exist: the hook refuses before the file system is touched, and a probe never aims
        # at real data.
        probe = os.path.join(I.REAL_HOME, ".loop-tests-isolation-probe-does-not-exist")
        with self.assertRaises(PermissionError):
            open(probe, encoding="utf-8")
        self.assertIn(probe, I.REFUSED)

    def test_this_checkout_the_interpreter_and_named_paths_stay_readable(self):
        self.assertFalse(I.refused(Path(__file__).resolve()))
        self.assertFalse(I.refused(os.path.join(sys.prefix, "lib")))
        self.assertTrue(I.refused(os.path.join(I.REAL_HOME, ".awt", "loop-workspaces")))
        self.assertTrue(I.refused(os.path.join(I.REAL_HOME, ".claude", "projects", "x.jsonl")))


if __name__ == "__main__":
    unittest.main()
