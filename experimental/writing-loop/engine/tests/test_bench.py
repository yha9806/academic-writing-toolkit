"""`loop bench` runs end to end through the hook path; the timing targets themselves are not asserted here."""
import unittest

import isolation  # noqa: F401  (a throwaway HOME; see isolation.py)

from loop import bench as B


class BenchTest(unittest.TestCase):
    def test_one_run_measures_three_events_and_reports_save_as_unsupported(self):
        res = B.run(runs=1)
        self.assertEqual({k: len(v) for k, v in res.items()}, {"transcript": 1, "commit": 1, "ledger": 1})
        self.assertTrue(all(v[0] is not None for v in res.values()), res)
        rows, _ = B.report(res)
        save = next(r for r in rows if r[0] == "save")
        self.assertIsNone(save[5])
        self.assertIn("不支持", save[1])


if __name__ == "__main__":
    unittest.main()
