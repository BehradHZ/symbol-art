import base64
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
from threading import Thread
import unittest

from PIL import Image

from app import Handler, MAX_BODY_BYTES, process_request
from symbol_art import convert


class PreviewTests(unittest.TestCase):
    def test_demo_matches_cli_engine(self):
        result = process_request({"options": {"width": 40}})
        with Image.open(Path(__file__).parent / "examples/behrad-input.jpg") as source:
            self.assertEqual(result["art"], convert(source))
        self.assertEqual((result["columns"], result["rows"]), (40, 20))
        with Image.open(BytesIO(base64.b64decode(result["preview"].split(",")[1]))) as image:
            image.verify()

    def test_uploaded_image_and_crop(self):
        buffer = BytesIO()
        Image.new("RGB", (80, 100), "black").save(buffer, format="PNG")
        result = process_request({"image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
                                  "options": {"width": 20, "crop": [10, 10, 50, 90], "invert": True}})
        self.assertEqual((result["imageWidth"], result["imageHeight"]), (80, 100))
        self.assertEqual(result["rows"], 20)
        self.assertEqual(set(result["art"]), {" ", "\n"})

    def test_changes_affect_actual_art(self):
        original = process_request({})["art"]
        for options in ({"gamma": 2}, {"contrast": .5}, {"mode": "tone"}, {"invert": True}):
            with self.subTest(options=options):
                self.assertNotEqual(original, process_request({"options": options})["art"])


    def test_default_numeric_controls_are_valid_step_values(self):
        html = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="contrastValue" class="number-input" type="number" min="0.05" max="5" step="0.05" value="1.15"', html)
        self.assertIn('id="gammaValue" class="number-input" type="number" min="0.05" max="5" step="0.05" value="1"', html)

    def test_invalid_payload(self):
        for payload in ([], {"image": "not an image"}, {"options": {"width": 1.5}}, {"options": {"crop": [1, 2]}},
                        {"options": {"font": "../../secret"}}, {"options": {"unknown": 1}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                process_request(payload)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_page_and_http_conversion(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"symbol-art", body)
        status, body = self.request("POST", "/api/convert", json.dumps({"options": {"width": 55}}))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["columns"], 55)

    def test_bad_request_and_origin(self):
        status, _ = self.request("POST", "/api/convert", "bad json")
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/convert", "{}", {"Origin": "https://elsewhere.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/convert", "", {"Content-Length": str(MAX_BODY_BYTES + 1)})
        self.assertEqual(status, 413)


if __name__ == "__main__":
    unittest.main()
