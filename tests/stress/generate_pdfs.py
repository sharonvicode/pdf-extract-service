"""Generate the PDF set used by the load tests (tests/stress/pdfs).

The TP asks for PDFs of varying size and density, from light documents up to
~9 MB with graphics. They are generated instead of taken from real documents so
the set is reproducible and free of copyright issues.

Usage (from the repo root):
    uv run python tests/stress/generate_pdfs.py
"""
import random
from dataclasses import dataclass
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "pdfs"

PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 in points
LINES_PER_PAGE = 45
LINES_PER_IMAGE_PAGE = 15
IMAGE_SIDE_PX = 512  # 512 x 512 RGB pixels = 768 KB per image
SEED = 42  # fixed seed: every run produces identical files

SENTENCES = [
    "El microservicio de extraccion recibe un PDF y devuelve su contenido.",
    "Cada replica corre en su propio contenedor con limites de CPU y memoria.",
    "El reverse proxy reparte los pedidos entre las replicas disponibles.",
    "Las pruebas de carga miden throughput, latencia y tasa de errores.",
    "Un modelo abierto inyecta pedidos a tasa constante sin esperar respuestas.",
    "El backpressure rechaza trabajo que no se podra terminar a tiempo.",
]


@dataclass(frozen=True)
class PdfSpec:
    name: str
    page_count: int
    with_images: bool = False


SPECS = [
    PdfSpec("liviano.pdf", page_count=2),
    PdfSpec("mediano.pdf", page_count=30),
    PdfSpec("largo.pdf", page_count=300),
    PdfSpec("pesado.pdf", page_count=12, with_images=True),
]


class PdfBuilder:
    """Assembles a minimal, valid PDF (Helvetica text and optional RGB images) with a correct xref table."""

    CATALOG_ID, PAGES_ID, FONT_ID = 1, 2, 3

    def __init__(self) -> None:
        self._objects: dict[int, bytes] = {
            self.FONT_ID: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
        self._page_ids: list[int] = []
        self._next_id = self.FONT_ID + 1

    def add_page(self, lines: list[str], image_pixels: bytes | None = None) -> None:
        resources = f"/Font << /F1 {self.FONT_ID} 0 R >>"
        drawing = ""
        if image_pixels is not None:
            image_id = self._add(_image_object(image_pixels))
            resources += f" /XObject << /Im1 {image_id} 0 R >>"
            drawing = "q 495 0 0 495 50 50 cm /Im1 Do Q\n"  # image on the lower part, text above it
        content = (drawing + _text_block(lines)).encode("ascii")
        content_id = self._add(_stream_object(b"", content))
        page = (
            f"<< /Type /Page /Parent {self.PAGES_ID} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}]"
            f" /Resources << {resources} >> /Contents {content_id} 0 R >>"
        )
        self._page_ids.append(self._add(page.encode("ascii")))

    def build(self) -> bytes:
        kids = " ".join(f"{page_id} 0 R" for page_id in self._page_ids)
        self._objects[self.PAGES_ID] = f"<< /Type /Pages /Kids [{kids}] /Count {len(self._page_ids)} >>".encode()
        self._objects[self.CATALOG_ID] = f"<< /Type /Catalog /Pages {self.PAGES_ID} 0 R >>".encode()

        buffer = bytearray(b"%PDF-1.4\n")
        offsets = {}
        for object_id in sorted(self._objects):
            offsets[object_id] = len(buffer)
            buffer += f"{object_id} 0 obj\n".encode() + self._objects[object_id] + b"\nendobj\n"

        size = max(self._objects) + 1
        xref_offset = len(buffer)
        buffer += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
        buffer += b"".join(f"{offsets[object_id]:010d} 00000 n \n".encode() for object_id in range(1, size))
        buffer += f"trailer\n<< /Size {size} /Root {self.CATALOG_ID} 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
        return bytes(buffer)

    def _add(self, body: bytes) -> int:
        object_id = self._next_id
        self._objects[object_id] = body
        self._next_id += 1
        return object_id


def _stream_object(dictionary_entries: bytes, data: bytes) -> bytes:
    header = b"<< " + dictionary_entries + b" /Length " + str(len(data)).encode() + b" >>"
    return header + b"\nstream\n" + data + b"\nendstream"


def _image_object(pixels: bytes) -> bytes:
    entries = (
        f"/Type /XObject /Subtype /Image /Width {IMAGE_SIDE_PX} /Height {IMAGE_SIDE_PX}"
        " /ColorSpace /DeviceRGB /BitsPerComponent 8"
    ).encode()
    return _stream_object(entries, pixels)


def _text_block(lines: list[str]) -> str:
    escaped = (line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines)
    shown = " T* ".join(f"({line}) Tj" for line in escaped)
    return f"BT /F1 10 Tf 14 TL 50 {PAGE_HEIGHT - 50} Td {shown} ET"


def _page_lines(page_number: int, line_count: int) -> list[str]:
    return [
        f"Pagina {page_number}, linea {line}: {SENTENCES[(page_number + line) % len(SENTENCES)]}"
        for line in range(1, line_count + 1)
    ]


def build_pdf(spec: PdfSpec, rng: random.Random) -> bytes:
    builder = PdfBuilder()
    for page_number in range(1, spec.page_count + 1):
        if spec.with_images:
            pixels = rng.randbytes(IMAGE_SIDE_PX * IMAGE_SIDE_PX * 3)
            builder.add_page(_page_lines(page_number, LINES_PER_IMAGE_PAGE), pixels)
        else:
            builder.add_page(_page_lines(page_number, LINES_PER_PAGE))
    return builder.build()


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    rng = random.Random(SEED)
    for spec in SPECS:
        path = OUTPUT_DIR / spec.name
        path.write_bytes(build_pdf(spec, rng))
        print(f"{spec.name}: {spec.page_count} paginas, {path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
