import unittest

from big5_extended_decoder import (
    DecodeError,
    DecodeResult,
    decode,
    decode_bytes,
    encode,
    encode_string,
    is_lead_byte,
    is_trail_byte,
)


class TestByteClassification(unittest.TestCase):
    def test_lead_byte_bounds(self):
        self.assertFalse(is_lead_byte(0x80))
        self.assertTrue(is_lead_byte(0x81))
        self.assertTrue(is_lead_byte(0xFE))
        self.assertFalse(is_lead_byte(0xFF))

    def test_trail_byte_bounds(self):
        self.assertFalse(is_trail_byte(0x3F))
        self.assertTrue(is_trail_byte(0x40))
        self.assertTrue(is_trail_byte(0x7E))
        self.assertFalse(is_trail_byte(0x7F))
        self.assertFalse(is_trail_byte(0xA0))
        self.assertTrue(is_trail_byte(0xA1))
        self.assertTrue(is_trail_byte(0xFE))
        self.assertFalse(is_trail_byte(0xFF))


class TestAsciiDecoding(unittest.TestCase):
    def test_plain_ascii(self):
        self.assertEqual(decode(b"hello"), "hello")

    def test_empty_input(self):
        result = decode_bytes(b"")
        self.assertEqual(result.text, "")
        self.assertEqual(result.consumed, 0)
        self.assertEqual(result.errors, 0)

    def test_ascii_around_escape(self):
        self.assertEqual(decode(b"a\x81\x40\x4e\x2db"), "a\u4e2db")


class TestUnicodeAtOn(unittest.TestCase):
    def test_basic_escape(self):
        # U+4E2D ("middle") via the 0x81 0x40 marker.
        self.assertEqual(decode(b"\x81\x40\x4e\x2d"), "\u4e2d")

    def test_alternate_marker(self):
        # Some producers use 0x7E as the second byte of the marker.
        self.assertEqual(decode(b"\x81\x7e\x4e\x2d"), "\u4e2d")

    def test_escape_can_be_disabled(self):
        # With uao=False the four bytes are just an unmapped pair plus
        # two more bytes; strict mode must reject the pair.
        with self.assertRaises(DecodeError):
            decode(b"\x81\x40\x4e\x2d", uao=False)

    def test_surrogate_escape_is_not_accepted(self):
        # 0xD800 is a surrogate and must not be produced as a character.
        with self.assertRaises(DecodeError):
            decode(b"\x81\x40\xd8\x00")

    def test_truncated_escape_is_not_accepted(self):
        # Only three bytes: not a complete escape, and the trailing bytes
        # form no valid pair either.
        with self.assertRaises(DecodeError):
            decode(b"\x81\x40\x4e")

    def test_escape_at_end_of_input(self):
        self.assertEqual(decode(b"x\x81\x40\x00\x41"), "xA")


class TestErrorModes(unittest.TestCase):
    def test_strict_rejects_unmapped_pair(self):
        with self.assertRaises(DecodeError):
            decode(b"\xa4\x40")

    def test_replace_unmapped_pair(self):
        result = decode_bytes(b"\xa4\x40", errors="replace")
        self.assertEqual(result.text, "\ufffd")
        self.assertEqual(result.errors, 1)
        self.assertEqual(result.consumed, 2)

    def test_strict_rejects_invalid_lead(self):
        with self.assertRaises(DecodeError):
            decode(b"\x80")

    def test_replace_invalid_lead(self):
        result = decode_bytes(b"\x80", errors="replace")
        self.assertEqual(result.text, "\ufffd")
        self.assertEqual(result.errors, 1)
        self.assertEqual(result.consumed, 1)

    def test_strict_rejects_truncated_pair(self):
        with self.assertRaises(DecodeError):
            decode(b"\xa4")

    def test_replace_truncated_pair(self):
        result = decode_bytes(b"\xa4", errors="replace")
        self.assertEqual(result.text, "\ufffd")
        self.assertEqual(result.errors, 1)
        self.assertEqual(result.consumed, 1)

    def test_strict_rejects_invalid_trail(self):
        with self.assertRaises(DecodeError):
            decode(b"\xa4\x20")

    def test_replace_invalid_trail_does_not_eat_trail(self):
        # The invalid trail byte 0x20 is ASCII and must survive.
        result = decode_bytes(b"\xa4\x20", errors="replace")
        self.assertEqual(result.text, "\ufffd ")
        self.assertEqual(result.errors, 1)
        self.assertEqual(result.consumed, 2)

    def test_replace_invalid_trail_that_is_a_lead(self):
        # 0x81 is a valid lead byte; it must be reprocessed, not swallowed.
        result = decode_bytes(
            b"\xa4\x81\x40\x4e\x2d", errors="replace"
        )
        self.assertEqual(result.text, "\ufffd\u4e2d")
        self.assertEqual(result.errors, 1)

    def test_unknown_errors_mode(self):
        with self.assertRaises(ValueError):
            decode_bytes(b"abc", errors="ignore")


class TestEncoding(unittest.TestCase):
    def test_ascii_roundtrip(self):
        self.assertEqual(encode_string("hello"), b"hello")

    def test_uao_roundtrip(self):
        original = "\u4e2d\u6587"
        self.assertEqual(decode(encode_string(original)), original)

    def test_encode_rejects_unmapped(self):
        with self.assertRaises(DecodeError):
            encode_string("\U0001F600")

    def test_encode_can_disable_uao(self):
        with self.assertRaises(DecodeError):
            encode_string("\u4e2d", uao=False)

    def test_encode_alias(self):
        self.assertEqual(encode("abc"), b"abc")


class TestDecodeResultType(unittest.TestCase):
    def test_returns_dataclass(self):
        result = decode_bytes(b"abc")
        self.assertIsInstance(result, DecodeResult)
        self.assertEqual(result.text, "abc")
        self.assertEqual(result.consumed, 3)
        self.assertEqual(result.errors, 0)


if __name__ == "__main__":
    unittest.main()
