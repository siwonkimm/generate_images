#!/usr/bin/env python3
import base64
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1")
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 6 * 1024 * 1024
SUPPORTED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key or key == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        return None
    return key


def load_local_env():
    # Accept both the documented .env filename and the workspace's existing env file.
    for env_path in (ROOT / ".env", ROOT / "env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip("\"'")
            if name and value and name not in os.environ:
                os.environ[name] = value


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalGeminiImage/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/health":
            key = get_api_key()
            return self.send_json(200, {
                "ready": bool(key),
                "model": MODEL,
                "message": "API key configured" if key else "Set GEMINI_API_KEY in .env"
            })
        if self.path not in ("/", "/image.html"):
            return self.send_json(404, {"error": "Not found"})

        try:
            body = (ROOT / "image.html").read_bytes()
        except OSError:
            return self.send_json(500, {"error": "image.html could not be read"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/generate":
            return self.send_json(404, {"error": "Not found"})
        if self.headers.get("Host") not in ("127.0.0.1:8765", "localhost:8765"):
            return self.send_json(403, {"error": "요청 호스트가 허용되지 않았습니다."})
        if self.headers.get("Origin") != "http://127.0.0.1:8765":
            return self.send_json(403, {"error": "이 로컬 페이지에서 보낸 요청만 허용됩니다."})
        if self.headers.get_content_type() != "application/json":
            return self.send_json(415, {"error": "Content-Type은 application/json이어야 합니다."})

        api_key = get_api_key()
        if not api_key:
            return self.send_json(503, {
                "error": "Gemini API 키가 없습니다. .env 파일에 GEMINI_API_KEY를 설정하고 서버를 다시 시작하세요."
            })

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "Invalid Content-Length"})
        if length <= 0 or length > MAX_REQUEST_BYTES:
            return self.send_json(413, {"error": "요청 크기가 허용 범위를 벗어났습니다."})

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.send_json(400, {"error": "유효한 JSON 요청이 아닙니다."})

        prompt = payload.get("prompt")
        source_image = payload.get("sourceImage")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
            return self.send_json(400, {"error": "프롬프트가 비어 있거나 너무 깁니다."})
        if not isinstance(source_image, str):
            return self.send_json(400, {"error": "편집할 원본 이미지가 없습니다."})

        match = re.match(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$", source_image)
        if not match or match.group(1) not in SUPPORTED_MIME_TYPES:
            return self.send_json(400, {"error": "원본은 JPEG, PNG 또는 WebP 이미지여야 합니다."})
        try:
            image_bytes = base64.b64decode(match.group(2), validate=True)
        except (ValueError, TypeError):
            return self.send_json(400, {"error": "원본 이미지 데이터가 손상되었습니다."})
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return self.send_json(413, {"error": "원본 이미지가 너무 큽니다."})

        request_body = json.dumps({
            "model": MODEL,
            "input": [
                {"type": "text", "text": prompt.strip()},
                {
                    "type": "image",
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                    "mime_type": match.group(1)
                }
            ]
        }).encode("utf-8")
        request = Request(
            API_URL,
            data=request_body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            method="POST"
        )

        try:
            with urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            detail = detail.replace(api_key, "[redacted]")[:1200]
            return self.send_json(502, {
                "error": "Gemini API 오류 (HTTP {}). {}".format(error.code, detail)
            })
        except URLError as error:
            return self.send_json(502, {"error": "Gemini API에 연결할 수 없습니다: {}".format(error.reason)})
        except (ValueError, OSError) as error:
            return self.send_json(502, {"error": "Gemini 응답을 처리하지 못했습니다: {}".format(error)})

        image_result = result.get("output_image")
        image_data = image_result.get("data") if isinstance(image_result, dict) else None
        if not image_data or not isinstance(image_data, str):
            return self.send_json(502, {
                "error": "Gemini 응답에 이미지가 없습니다. 이미지 생성 모델 접근 권한과 API 할당량을 확인하세요."
            })
        image_mime = image_result.get("mime_type", "image/png")
        if image_mime not in SUPPORTED_MIME_TYPES:
            image_mime = "image/png"
        try:
            decoded_result = base64.b64decode(image_data, validate=True)
        except (ValueError, TypeError):
            return self.send_json(502, {"error": "Gemini가 유효하지 않은 이미지 데이터를 반환했습니다."})
        if len(decoded_result) > MAX_IMAGE_BYTES:
            return self.send_json(502, {"error": "Gemini 결과 이미지가 허용 크기를 초과했습니다."})

        self.send_json(200, {
            "image": "data:{};base64,{}".format(image_mime, image_data)
        })

    def log_message(self, fmt, *args):
        print("{} - {}".format(self.address_string(), fmt % args))


if __name__ == "__main__":
    load_local_env()
    MODEL = os.environ.get("GEMINI_IMAGE_MODEL", MODEL)
    print("Open http://{}:{}/image.html".format(HOST, PORT))
    print("Image model: {}".format(MODEL))
    print("GEMINI_API_KEY: {}".format("configured" if get_api_key() else "not configured"))
    HTTPServer((HOST, PORT), Handler).serve_forever()
