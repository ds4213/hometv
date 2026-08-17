from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from hometv.fetch import FetchError, fetch_config, write_candidate
from hometv.registry import Source


class FakeHeaders:
    def __init__(self, content_type: str):
        self._content_type = content_type

    def get_content_type(self):
        return self._content_type


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str = "application/json"):
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size: int = -1):
        return self.body


def source() -> Source:
    return Source(
        id="example",
        name="Example",
        url="https://example.com/config.json",
        regions=("us",),
        enabled=True,
        stable_regions=(),
    )


class FetchTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fetch_encodes_unicode_hostname_with_idna(self, urlopen):
        idn_source = Source(
            id="fantaiying",
            name="饭太硬",
            url="http://www.饭太硬.com/tv",
            regions=("us", "cn"),
            enabled=True,
            stable_regions=(),
        )
        urlopen.return_value = FakeResponse(b'{"sites": [{"key": "one"}]}')

        fetch_config(idn_source)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://www.xn--sss604efuw.com/tv")

    @patch("urllib.request.urlopen")
    def test_fetches_a_json_object(self, urlopen):
        urlopen.return_value = FakeResponse(b'{"sites": []}')
        fetched = fetch_config(source())
        self.assertEqual(fetched.content, {"sites": []})
        self.assertEqual(
            fetched.sha256,
            "5f2ffd25936b09c11b57ded0344ac12215680f7286c44921e5427f4b3a7ee806",
        )

    @patch("urllib.request.urlopen")
    def test_rejects_an_html_login_page(self, urlopen):
        urlopen.return_value = FakeResponse(b"<!doctype html><title>Login</title>", "text/html")
        with self.assertRaisesRegex(FetchError, "HTML"):
            fetch_config(source())

    @patch("urllib.request.urlopen")
    def test_rejects_non_object_json(self, urlopen):
        urlopen.return_value = FakeResponse(b"[]")
        with self.assertRaisesRegex(FetchError, "top-level JSON object"):
            fetch_config(source())

    @patch("urllib.request.urlopen")
    def test_failed_candidate_write_keeps_existing_file(self, urlopen):
        urlopen.return_value = FakeResponse(b'{"sites": []}')
        fetched = fetch_config(source())
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_candidate(fetched, root)
            original = path.read_bytes()

            broken = fetched.__class__(
                source=fetched.source,
                content={"sites": set()},
                raw=b'{"sites": []}',
                fetched_at=fetched.fetched_at,
                sha256=fetched.sha256,
            )
            with self.assertRaises(TypeError):
                write_candidate(broken, root)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"sites": []})


if __name__ == "__main__":
    unittest.main()
