"""Cross-module job and native-file safety boundaries; no desktop changes."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from studio import jobs, native


class JobBoundaryTests(unittest.TestCase):
    def test_nested_credentials_and_local_paths_are_not_returned(self):
        value = {'id': 'public-id', 'nested': [{'Authorization': 'private',
                 'MODEL_PATH': 'private', 'auth': {'bearer': 'private'},
                 'PASSWORD': 'private', 'text': 'Știință, credință'}]}
        self.assertEqual(jobs.public(value), {'id': 'public-id',
                         'nested': [{'text': 'Știință, credință'}]})

    def test_running_job_cancellation_and_progress_preserve_public_results(self):
        started = threading.Event()
        def operation(event, progress):
            progress(rows=7, token='private')
            started.set()
            event.wait(3)
            return {'records': 7, 'source_path': 'private'}
        item = jobs.submit('boundary-test', operation)
        self.assertTrue(started.wait(2))
        jobs.cancel(item['id'])
        for _ in range(100):
            item = jobs.snapshot(item['id'])
            if item['state'] == 'CANCELLED':
                break
            time.sleep(.01)
        self.assertEqual(item['state'], 'CANCELLED')
        self.assertEqual(item['progress'], {'rows': 7})
        self.assertEqual(item['result'], {'records': 7})


class NativeFileBoundaryTests(unittest.TestCase):
    def test_headless_native_picker_is_explicitly_unavailable(self):
        with patch.object(native, '_active', False):
            with self.assertRaisesRegex(ValueError, 'NATIVE_DIALOG_UNAVAILABLE'):
                native.request('open')

    def test_source_protection_resolves_aliases_without_changing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.sqlite'
            path.write_bytes(b'original source fixture')
            with patch.object(native, '_protected_paths', set()):
                native.protect(path.parent/'.'/path.name)
                self.assertIn(path.resolve(), native._protected_paths)
            self.assertEqual(path.read_bytes(), b'original source fixture')


if __name__ == '__main__':
    unittest.main()
