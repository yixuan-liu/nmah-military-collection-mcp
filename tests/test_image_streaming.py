import http.client
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from threading import Event, Thread
from unittest.mock import patch

import httpx

from playground import server as playground


class ImageStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    def __iter__(self):
        yield from self.chunks


@contextmanager
def image_request(chunks, headers=None):
    @contextmanager
    def upstream(method, url, **kwargs):
        response = httpx.Response(
            200,
            headers=headers,
            stream=ImageStream(chunks),
            request=httpx.Request(method, url),
        )
        try:
            yield response
        finally:
            response.close()

    with (
        patch.object(playground.httpx, "stream", upstream),
        ThreadingHTTPServer(("127.0.0.1", 0), playground.Handler) as server,
    ):
        worker = Thread(target=server.serve_forever)
        worker.start()
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=2
        )
        try:
            connection.request("GET", "/api/image-preview?id=NMAH-TEST&kind=iiif")
            yield connection
        finally:
            connection.close()
            server.shutdown()
            worker.join()


class ImageStreamingTests(unittest.TestCase):
    def test_iiif_sends_first_bytes_before_the_upstream_finishes(self):
        release = Event()
        first = b"\xff\xd8\xfffirst"
        last = b"last\xff\xd9"

        def chunks():
            yield first[:2]
            yield first[2:]
            if release.wait(timeout=4):
                yield last

        with image_request(chunks()) as connection:
            try:
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "image/jpeg")
                self.assertEqual(response.read(len(first)), first)
            finally:
                release.set()
            self.assertEqual(response.read(), last)

    def test_rejects_non_jpeg_before_starting_the_image_response(self):
        with image_request([b"<html>Request rejected</html>"]) as connection:
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn(b"did not return a JPEG", response.read())

    def test_rejects_an_oversized_content_length_before_streaming(self):
        with image_request(
            [b"\xff\xd8\xfffirst"],
            {"Content-Length": str(24 * 1024 * 1024 + 1)},
        ) as connection:
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn(b"too large", response.read())

    def test_closes_an_oversized_stream_without_sending_the_excess_chunk(self):
        first = b"\xff\xd8\xfffirst"
        with (
            patch.object(playground, "MAX_IMAGE_BYTES", len(first)),
            image_request([first, b"one byte over"]) as connection,
        ):
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(len(first)), first)
            with self.assertRaises(http.client.IncompleteRead) as error:
                response.read()
            self.assertEqual(error.exception.partial, b"")
