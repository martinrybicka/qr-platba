"""Small, stateless local HTTP server for QR Platba."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import io
import json
import os

import qrcode
from PIL import Image, ImageDraw, ImageFont

from spayd import PaymentError, account_to_iban, generate_spayd


ROOT = Path(__file__).parent / "static"
FILES = {"/": ("index.html", "text/html; charset=utf-8"),
         "/style.css": ("style.css", "text/css; charset=utf-8"),
         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
         "/icon.svg": ("icon.svg", "image/svg+xml")}


def qr_png(spayd: str) -> bytes:
    # H provides enough redundancy for the small central logo.
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=12, border=4)
    qr.add_data(spayd, optimize=0)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    width = qr_image.width + 112
    height = qr_image.height + 204
    image = Image.new("RGB", (width, height), "#f0f2f4")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, width - 13, height - 13), radius=24,
                           fill="white", outline="#d9dfe5", width=2)
    def font(size: int, bold: bool = False):
        names = (["DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if bold
                 else ["DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"])
        for name in names:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()
    draw.rounded_rectangle((56, 49, 89, 82), radius=7, fill="#53677b")
    draw.rectangle((64, 57, 72, 65), fill="white")
    draw.rectangle((76, 57, 81, 62), fill="white")
    draw.rectangle((64, 69, 69, 74), fill="white")
    draw.text((103, 48), "QR PLATBA", font=font(27, True), fill="#27313d")
    image.paste(qr_image, (56, 105))
    logo = Image.open(ROOT / "logo-ring.png").convert("RGBA")
    logo_size = round(qr_image.width * 0.12)
    badge_size = round(qr_image.width * 0.155)
    center = (56 + qr_image.width // 2, 105 + qr_image.height // 2)
    half_badge = badge_size // 2
    draw.ellipse((center[0] - half_badge, center[1] - half_badge,
                  center[0] + half_badge, center[1] + half_badge), fill="white")
    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    logo_position = (center[0] - logo_size // 2, center[1] - logo_size // 2)
    image.paste(logo, logo_position, logo)
    draw.line((56, height - 77, width - 56, height - 77), fill="#dce2e8", width=2)
    draw.text((56, height - 61), "Naskenujte v bankovní aplikaci", font=font(17), fill="#5c6875")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        entry = FILES.get(self.path)
        if entry is None:
            self._json(404, {"error": "Stránka nenalezena."})
            return
        filename, content_type = entry
        self._send(200, (ROOT / filename).read_bytes(), content_type)

    def do_POST(self) -> None:
        if self.path not in ("/api/payment", "/api/account"):
            self._json(404, {"error": "Služba nenalezena."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 8192:
                raise PaymentError("Požadavek je příliš velký nebo prázdný.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise PaymentError("Neplatná data požadavku.")
            if self.path == "/api/account":
                self._json(200, {"iban": account_to_iban(str(data.get("account", "")))})
                return
            spayd, iban = generate_spayd(
                str(data.get("account", "")), str(data.get("amount", "")),
                str(data.get("currency", "CZK")), str(data.get("vs", "")),
                str(data.get("message", "")),
            )
            png = qr_png(spayd)
            self._json(200, {"spayd": spayd, "iban": iban,
                             "png": "data:image/png;base64," + base64.b64encode(png).decode("ascii")})
        except (PaymentError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "QR kód se nepodařilo vytvořit."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"QR Platba: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
