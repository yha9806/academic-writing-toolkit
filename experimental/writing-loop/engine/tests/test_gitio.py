import subprocess
import unittest
from unittest import mock

from loop import gitio

from fixtures import TempDir, make_repo


def spawned_git(calls):
    """The git subcommands started while a block ran, e.g. ["show", "rev-parse"]."""
    return [c[0][0][3] for c in calls if c[0][0][:1] == ["git"]]


class BatchTest(unittest.TestCase):
    def setup_repo(self, root):
        return make_repo(root, [({"a.md": "One.\n", "sub dir/b é.md": "Two.\n", "d/c.md": "Three.\n"}, "v1", 1_700_000_000),
                                ({"a.md": "One, changed.\n"}, "v2", 1_700_000_100)])

    def test_batch_answers_exactly_what_single_calls_answer(self):
        with TempDir() as root:
            repo = self.setup_repo(root)
            head = gitio.rev_parse(repo, "main")
            first = gitio.parent(repo, head)
            asks = [(c, p) for c in (head, first, "0" * 40) for p in ("a.md", "sub dir/b é.md", "d", "d/c.md", "missing.md")]
            single = [(gitio.show(repo, c, p), gitio.blob_id(repo, c, p)) for c, p in asks]
            with gitio.batch(repo):
                batched = [(gitio.show(repo, c, p), gitio.blob_id(repo, c, p)) for c, p in asks]
            self.assertEqual(batched, single)
            self.assertEqual(single[0][0], "One, changed.\n")
            self.assertIsNone(single[4][0])

    def test_inside_a_batch_reading_objects_starts_no_process(self):
        """Load report F3 (2026-09-18): 86 git processes took 0.79 s of a 1.2 s update, most of them one per file read."""
        with TempDir() as root:
            repo = self.setup_repo(root)
            head = gitio.rev_parse(repo, "main")
            real = subprocess.run
            with gitio.batch(repo), mock.patch("subprocess.run", side_effect=real) as run:
                for p in ("a.md", "d/c.md", "missing.md"):
                    gitio.show(repo, head, p)
                    gitio.blob_id(repo, head, p)
            self.assertEqual(spawned_git(run.call_args_list), [])

    def test_the_batch_process_ends_with_the_block(self):
        with TempDir() as root:
            repo = self.setup_repo(root)
            with gitio.batch(repo) as b:
                gitio.show(repo, "main", "a.md")
            self.assertIsNotNone(b.proc.poll())
            with mock.patch("subprocess.run", side_effect=subprocess.run) as run:
                self.assertEqual(gitio.show(repo, "main", "a.md"), "One, changed.\n")
            self.assertEqual(spawned_git(run.call_args_list), ["show"])

    def test_a_batch_that_dies_falls_back_to_single_calls(self):
        with TempDir() as root:
            repo = self.setup_repo(root)
            with gitio.batch(repo) as b:
                b.proc.kill()
                b.proc.wait()
                self.assertEqual(gitio.show(repo, "main", "a.md"), "One, changed.\n")
                self.assertIsNone(gitio.blob_id(repo, "main", "missing.md"))


if __name__ == "__main__":
    unittest.main()
