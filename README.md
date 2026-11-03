# big5_extended_decoder

Decodes Big5 byte sequences, including the ETEN extension block and the
Unicode-at-on four-byte escape that some fonts use to carry arbitrary
Unicode code points inside a Big5 stream.

## Usage

```python
from big5_extended_decoder import decode, decode_bytes, encode_string

# Plain ASCII passes through.
assert decode(b"hello") == "hello"

# A Unicode-at-on escape: 0x81 0x40 followed by a big-endian code point.
assert decode(b"\x81\x40\x4e\x2d") == "\u4e2d"

# The alternate 0x7E marker is accepted too.
assert decode(b"\x81\x7e\x4e\x2d") == "\u4e2d"

# Non-strict mode replaces unmapped pairs and reports how many it saw.
result = decode_bytes(b"\xa4\x40", errors="replace")
assert result.text == "\ufffd"
assert result.errors == 1

# Encoding round-trips the escapes we emit.
assert decode(encode_string("\u4e2d")) == "\u4e2d"
```

Exported names: `decode`, `decode_bytes`, `encode`, `encode_string`,
`DecodeResult`, `DecodeError`, `is_lead_byte`, `is_trail_byte`.

## Why this exists

Big5 documents in the wild are not always pure Big5.  The ETEN extension
fills lead bytes 0x81..0xA0 and 0xC6..0xC8 with vendor-specific glyphs, and
the Unicode-at-on convention encodes a full Unicode code point in four
bytes (`0x81`, a marker, then the code point big-endian).  A decoder that
only knows the base table either rejects these bytes or silently mangles
them.

This library makes a deliberate trade-off: it ships **no** Big5 mapping
table.  It handles ASCII, the structural rules of lead and trail bytes, and
the Unicode-at-on escape, and it treats every other structurally valid pair
as "unmapped".  That keeps the module standard-library-only and small
enough to audit, at the cost of not decoding ordinary Chinese text.  If you
need the full table, plug one in on top of `decode_bytes` by catching
`DecodeError` and looking the pair up yourself.

## The awkward edge

When `errors="replace"` meets an invalid trail byte, the decoder does
**not** consume that byte.  The byte might itself be a valid lead byte for
the following sequence, and eating it would swallow a real code point.  So
`decode_bytes(b"\xa4\x81\x40\x4e\x2d", errors="replace")` yields
`"\ufffd\u4e2d"`, not `"\ufffd\ufffd\u4e2d"`.

A second edge: the Unicode-at-on escape is only recognised when `uao=True`
(the default).  With `uao=False`, the four bytes are an ordinary unmapped
pair followed by two more bytes, and strict mode will raise.
