import unittest

from payload import parse_telegram_update


class ParseTelegramUpdateTests(unittest.TestCase):
    def test_returns_original_utf8_json_body(self):
        body = b'{ "update_id": 42, "message": {"text": "hello"} }'

        self.assertEqual(parse_telegram_update(body), body.decode("utf-8"))

    def test_rejects_nonstandard_json_constants(self):
        for body in (b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}'):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    parse_telegram_update(body)

    def test_rejects_invalid_utf8_and_non_object_json(self):
        for body in (b'{"text":"\xff"}', b"[]", b"not json"):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    parse_telegram_update(body)


if __name__ == "__main__":
    unittest.main()
