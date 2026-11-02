"""Big5 Extended Decoder.

Decodes Big5 byte sequences, including the ETEN extension block (0x81-0xFE
lead bytes paired with 0x40-0x7E / 0xA1-0xFE trail bytes) and the
Unicode-at-on extension used by some fonts to carry Unicode code points
inline in the Big5 stream.
"""

from .core import (
    DecodeError,
    DecodeResult,
    decode,
    decode_bytes,
    encode,
    encode_string,
    is_lead_byte,
    is_trail_byte,
)

__all__ = [
    "DecodeError",
    "DecodeResult",
    "decode",
    "decode_bytes",
    "encode",
    "encode_string",
    "is_lead_byte",
    "is_trail_byte",
]

__version__ = "1.0.0"
