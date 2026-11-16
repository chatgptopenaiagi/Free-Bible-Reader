"""Actual loopback asset-burst regression for the local browser server."""
import concurrent.futures
import http.client
import threading
import unittest
from workbench import server as application


class StartupHTTPTests(unittest.TestCase):
    def test_pending_queue_handles_parallel_real_module_fetches(self):
        self.assertEqual(application.ThreadingHTTPServer.request_queue_size, 128)
        expected = (application.ROOT / 'ui-core/index.js').read_bytes()
        server = application.ThreadingHTTPServer(('127.0.0.1', 0), application.Handler)
        server.allowed_engine = 'all'
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .3}, daemon=True)
        worker.start()
        try:
            for round_number in range(3):
                barrier = threading.Barrier(32)

                def fetch(index):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    try:
                        barrier.wait(timeout=5)
                        connection.request('GET', f'/ui-core/index.js?startup={round_number}-{index}', headers={'Connection': 'close'})
                        response = connection.getresponse()
                        return response.status, response.read()
                    finally:
                        connection.close()

                with concurrent.futures.ThreadPoolExecutor(max_workers=32) as clients:
                    results = list(clients.map(fetch, range(32)))
                for status, body in results:
                    self.assertEqual(status, 200)
                    self.assertEqual(body, expected)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
