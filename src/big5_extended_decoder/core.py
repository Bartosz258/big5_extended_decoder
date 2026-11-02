"""Core decoding and encoding routines for the Big5 extended decoder.

Design notes
------------

Big5 is a double-byte encoding.  Lead bytes live in 0x81..0xFE and trail
bytes in 0x40..0x7E or 0xA1..0xFE.  Bytes below 0x80 are treated as ASCII.

On top of that base:

* The ETEN extension occupies lead bytes 0x81..0xA0 and 0xC6..0xC8 (and a
  few others depending on the vendor) and maps to a private range.  We do
  not ship a full ETEN table because it is large and vendor-specific;
  instead we expose the structural rules so callers can decide what to do
  with an unmapped pair.  When ``strict=False`` an unmapped pair is
  replaced with U+FFFD.

* The Unicode-at-on extension encodes a Unicode code point directly in the
  byte stream using the sequence ``0x81 0x40 0xXX 0xYY`` (four bytes total,
  the first two being the lead pair for the marker and the last two the
  big-endian code point).  Some producers use ``0x81 0x7E`` as the marker
  instead.  We accept both, because real-world documents use both and the
  distinction is not observable otherwise.

The decoder is deliberately table-light: we only carry the ASCII range and
the structural rules, and treat everything else as either a Unicode-at-on
escape or an unmapped pair.  That keeps the module dependency free and
small enough to audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


class DecodeError(ValueError):
    """Raised when a Big5 byte sequence cannot be decoded in strict mode."""


@dataclass(frozen=True)
class DecodeResult:
    """Result of a decode operation.

    Attributes
    ----------
    text:
        The decoded string.
    consumed:
        Number of input bytes consumed.  Equal to the input length on a
        clean decode; less if ``errors="replace"`` stopped early, which
        never happens in this implementation -- it is always the full
        length.  Kept for API symmetry with future streaming decoders.
    errors:
        Number of replacement characters inserted.
    """

    text: str
    consumed: int
    errors: int


# Unicode-at-on markers.  The first byte is always 0x81; the second byte
# distinguishes the two variants seen in the wild.
_UAO_MARKERS = (0x40, 0x7E)


def is_lead_byte(byte: int) -> bool:
    """Return True if *byte* can start a double-byte Big5 sequence."""
    return 0x81 <= byte <= 0xFE


def is_trail_byte(byte: int) -> bool:
    """Return True if *byte* can follow a lead byte."""
    return 0x40 <= byte <= 0x7E or 0xA1 <= byte <= 0xFE


def _decode_uao(data: bytes, index: int) -> Tuple[str, int] | None:
    """Try to decode a Unicode-at-on escape starting at *index*.

    Returns ``(text, consumed)`` on success, ``None`` if the bytes at
    *index* are not a well-formed escape.  A well-formed escape is four
    bytes: ``0x81``, a marker byte, then a big-endian code point in the
    BMP range (0x0000..0xFFFF, excluding surrogates).
    """
    if index + 4 > len(data):
        return None
    if data[index] != 0x81:
        return None
    if data[index + 1] not in _UAO_MARKERS:
        return None
    code_point = (data[index + 2] << 8) | data[index + 3]
    if 0xD800 <= code_point <= 0xDFFF:
        # Surrogates are not valid standalone code points; treat the
        # sequence as unmapped rather than fabricating a lone surrogate.
        return None
    return chr(code_point), 4


def decode_bytes(
    data: bytes,
    *,
    errors: str = "strict",
    uao: bool = True,
) -> DecodeResult:
    """Decode *data* as Big5 with extensions.

    Parameters
    ----------
    data:
        The byte string to decode.
    errors:
        ``"strict"`` raises :class:`DecodeError` on an unmapped pair;
        ``"replace"`` substitutes U+FFFD and counts the substitution.
    uao:
        When True, recognise the Unicode-at-on four-byte escape.

    Returns
    -------
    DecodeResult
    """
    if errors not in ("strict", "replace"):
        raise ValueError(f"unsupported errors mode: {errors!r}")

    out: List[str] = []
    error_count = 0
    i = 0
    n = len(data)

    while i < n:
        byte = data[i]

        if byte < 0x80:
            out.append(chr(byte))
            i += 1
            continue

        if not is_lead_byte(byte):
            # 0x80 and 0xFF are not valid lead bytes.
            if errors == "strict":
                raise DecodeError(
                    f"invalid lead byte 0x{byte:02X} at offset {i}"
                )
            out.append("\ufffd")
            error_count += 1
            i += 1
            continue

        if uao:
            uao_result = _decode_uao(data, i)
            if uao_result is not None:
                text, consumed = uao_result
                out.append(text)
                i += consumed
                continue

        if i + 1 >= n:
            if errors == "strict":
                raise DecodeError(
                    f"truncated sequence at offset {i}: lead byte 0x{byte:02X} "
                    "without trail byte"
                )
            out.append("\ufffd")
            error_count += 1
            i += 1
            continue

        trail = data[i + 1]
        if not is_trail_byte(trail):
            if errors == "strict":
                raise DecodeError(
                    f"invalid trail byte 0x{trail:02X} at offset {i + 1} "
                    f"after lead byte 0x{byte:02X}"
                )
            out.append("\ufffd")
            error_count += 1
            # Do not consume the trail byte: it may itself be a lead byte
            # for a following sequence, and eating it would silently
            # swallow a valid code point.
            i += 1
            continue

        # A structurally valid Big5 pair that we do not have a table entry
        # for.  We cannot fabricate a mapping.
        if errors == "strict":
            raise DecodeError(
                f"unmapped Big5 pair 0x{byte:02X} 0x{trail:02X} at offset {i}"
            )
        out.append("\ufffd")
        error_count += 1
        i += 2

    return DecodeResult(text="".join(out), consumed=n, errors=error_count)


def decode(data: bytes, *, errors: str = "strict", uao: bool = True) -> str:
    """Decode *data* and return only the resulting string.

    Convenience wrapper around :func:`decode_bytes` for the common case
    where the caller does not need the error count.
    """
    return decode_bytes(data, errors=errors, uao=uao).text


def encode_string(text: str, *, uao: bool = True) -> bytes:
    """Encode *text* as Big5 bytes.

    Only ASCII and the Unicode-at-on escape are supported.  Any other
    character raises :class:`DecodeError`, because we do not ship a Big5
    mapping table and guessing would be worse than failing.  The function
    is named ``encode_string`` rather than ``encode`` to leave room for a
    future table-backed encoder.
    """
    out = bytearray()
    for ch in text:
        code = ord(ch)
        if code < 0x80:
            out.append(code)
            continue
        if uao and code <= 0xFFFF and not (0xD800 <= code <= 0xDFFF):
            out.append(0x81)
            out.append(0x40)
            out.append((code >> 8) & 0xFF)
            out.append(code & 0xFF)
            continue
        raise DecodeError(f"cannot encode U+{code:04X} without a Big5 table")
    return bytes(out)


def encode(text: str, *, uao: bool = True) -> bytes:
    """Alias for :func:`encode_string`."""
    return encode_string(text, uao=uao)
