"""Timeout-free optimizer transport against a held local HTTP stream; no inference."""
import http.client
import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from optimization.runtime import GeneratorBackend
from workbench.workflows import Cancelled


class HeldGenerationHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.close_connection = True
        self.server.active_socket = self.connection
        self.server.body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.arrived.set()
        if self.server.hold_headers:
            self.server.release.wait(5)
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            chunk = {'choices': [{'delta': {'content': 'partial prompt', 'reasoning_content': 'partial reasoning'}, 'finish_reason': None}]}
            self.wfile.write(b'data: ' + json.dumps(chunk).encode() + b'\n\n')
            self.wfile.flush()
            self.server.release.wait(5)
            self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
            self.wfile.flush()
        except OSError:
            # Cancellation deliberately closes this connection while the fixture is held.
            pass


class OptimizerGenerationTransportTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), HeldGenerationHandler)
        self.server.daemon_threads = True
        self.server.arrived = threading.Event()
        self.server.release = threading.Event()
        self.server.hold_headers = False
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.backend = GeneratorBackend({'backend': 'llamacpp'}, {}, lambda *args: None)
        self.backend.owned_id = 'fixture'
        self.backend.transport.port = self.server.server_port
        self.cancel = threading.Event()
        self.partial_read = threading.Event()
        self.result = None
        self.error = None
        self.worker = None
        self.socket_timeouts = []
        original_connect = http.client.HTTPConnection.connect
        original_readline = http.client.HTTPResponse.readline

        def connect(connection):
            original_connect(connection)
            self.socket_timeouts.append(connection.sock.gettimeout())

        def readline(response, *args):
            line = original_readline(response, *args)
            if line == b'\n':
                self.partial_read.set()
            return line

        self.reader_patch = patch.object(http.client.HTTPResponse, 'readline', readline)
        self.connection_patch = patch.object(http.client.HTTPConnection, 'connect', connect)
        self.reader_patch.start()
        self.connection_patch.start()
        self.addCleanup(self.close)

    def close(self):
        self.cancel.set()
        self.backend.cancel()
        self.server.release.set()
        if self.worker:
            self.worker.join(5)
        self.reader_patch.stop()
        self.connection_patch.stop()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(5)

    def start(self):
        def generate():
            try:
                self.result = self.backend.propose([{'role': 'user', 'content': 'fixture request'}], {'temperature': .7}, 1234, self.cancel)
            except Exception as error:
                self.error = error

        self.worker = threading.Thread(target=generate, daemon=True)
        self.worker.start()
        self.assertTrue(self.server.arrived.wait(2), 'Fixture did not receive generation request')
        connection = self.backend.transport.connection
        self.assertIsNone(connection.timeout)
        self.assertEqual(self.socket_timeouts, [None])
        self.assertEqual(self.server.body['max_tokens'], 1234)

    def stop(self):
        # Native Stop terminates its owned llama-server after cancelling the request.
        # Simulate that process termination by closing the fixture's server-side socket.
        terminated = []

        def terminate():
            terminated.append(True)
            try:
                self.server.active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                # Request cancellation may have closed the fixture connection already.
                pass
            self.server.active_socket.close()
            self.server.release.set()

        self.backend.process = SimpleNamespace(poll=lambda: 0 if terminated else None, terminate=terminate)
        self.cancel.set()
        self.backend.cancel()
        self.worker.join(1)
        self.assertFalse(self.worker.is_alive(), 'Manual Stop must interrupt an unlimited socket read')
        self.assertIsInstance(self.error, Cancelled)
        self.assertFalse(self.backend.timed_out)
        self.assertEqual(terminated, [True])

    def test_completion_uses_unlimited_socket_and_preserves_text_and_reasoning(self):
        self.start()
        self.assertTrue(self.partial_read.wait(2))
        self.assertTrue(self.worker.is_alive())
        self.server.release.set()
        self.worker.join(2)
        self.assertFalse(self.worker.is_alive())
        self.assertIsNone(self.error)
        self.assertEqual(self.result['text'], 'partial prompt')
        self.assertEqual(self.result['reasoning_text'], 'partial reasoning')
        self.assertEqual(self.result['finish_reason'], 'stop')

    def test_manual_stop_interrupts_wait_before_response_headers(self):
        self.server.hold_headers = True
        self.start()
        self.stop()
        self.assertEqual(self.error.partial_response['text'], '')

    def test_manual_stop_interrupts_stream_and_preserves_partial_output(self):
        self.start()
        self.assertTrue(self.partial_read.wait(2))
        self.stop()
        self.assertEqual(self.error.partial_response['text'], 'partial prompt')
        self.assertEqual(self.error.partial_response['reasoning_text'], 'partial reasoning')
        self.assertTrue(self.error.partial_response['incomplete'])


if __name__ == '__main__':
    unittest.main()
