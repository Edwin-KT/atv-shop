import random
from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

# The names of everything that can run or launch something; none may stay after cleaning.
ACTIVE_NAMES = [b"/JavaScript", b"/JS", b"/OpenAction", b"/Launch", b"/AA", b"/Annot"]


def _to_bytes(writer: PdfWriter) -> bytes:
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _dict(**items) -> DictionaryObject:
    """DictionaryObject(S="/JavaScript") instead of {NameObject("/S"): NameObject(...)}."""
    return DictionaryObject({NameObject(f"/{key}"): value for key, value in items.items()})


def make_pdf(pages: int = 1) -> bytes:
    """A small, valid, harmless PDF."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    return _to_bytes(writer)


def make_pdf_with_javascript() -> bytes:
    """A valid PDF with active content where an attacker would really put it:
    JavaScript that runs when the file opens (/OpenAction in the catalog),
    JavaScript that runs when the page opens (/AA) and a link that starts a program."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)

    def javascript(code):
        return writer._add_object(_dict(S=NameObject("/JavaScript"), JS=TextStringObject(code)))

    writer._root_object[NameObject("/OpenAction")] = javascript("app.alert('file opened');")
    page[NameObject("/AA")] = writer._add_object(_dict(O=javascript("app.alert('page opened');")))
    launch = writer._add_object(_dict(S=NameObject("/Launch"), F=TextStringObject("calc.exe")))
    link = _dict(
        Type=NameObject("/Annot"),
        Subtype=NameObject("/Link"),
        Rect=ArrayObject([NumberObject(0), NumberObject(0), NumberObject(200), NumberObject(200)]),
        A=launch,
    )
    page[NameObject("/Annots")] = ArrayObject([writer._add_object(link)])
    return _to_bytes(writer)


def make_large_pdf(width: int = 2000, height: int = 2250) -> tuple[bytes, bytes]:
    """A valid PDF of about 4.5 MB: one page with a grey image made of random bytes,
    like a scanned document. Returns (pdf, image_bytes).

    Compressed images look like random bytes and contain names like /JavaScript by
    chance; it is put in on purpose, so a byte search would surely refuse this file."""
    image_bytes = bytearray(random.Random(2024).randbytes(width * height))
    image_bytes[1000:1012] = b"/JavaScript "  # followed by a space, like a real PDF name

    image = DecodedStreamObject()
    image.set_data(bytes(image_bytes))
    image.update(
        _dict(
            Type=NameObject("/XObject"),
            Subtype=NameObject("/Image"),
            Width=NumberObject(width),
            Height=NumberObject(height),
            ColorSpace=NameObject("/DeviceGray"),
            BitsPerComponent=NumberObject(8),
        )
    )
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    page[NameObject("/Resources")] = _dict(XObject=_dict(Im0=writer._add_object(image)))
    return _to_bytes(writer), bytes(image_bytes)


def make_pdf_with_hidden_payload(payload: bytes) -> bytes:
    """A valid PDF with extra bytes hidden after the %%EOF marker."""
    return make_pdf() + b"\n" + payload


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
