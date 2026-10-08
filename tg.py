"""Minimal Telegram Bot API helpers (stdlib only). Credentials come from .env."""
import json
import pathlib
import urllib.parse
import urllib.request
import uuid

HERE = pathlib.Path(__file__).parent


def env():
    out = {}
    for line in (HERE / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


ENV = env()
CHAT_ID = int(ENV["TELEGRAM_CHAT_ID"])
BASE = f"https://api.telegram.org/bot{ENV['TELEGRAM_BOT_TOKEN']}"


def api(method, http_timeout=60, **params):
    data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}).encode()
    with urllib.request.urlopen(f"{BASE}/{method}", data=data, timeout=http_timeout) as r:
        return json.load(r)


def send_message(text, buttons=None, html=True, reply_to=None):
    p = dict(chat_id=CHAT_ID, text=text, disable_web_page_preview="true")
    if reply_to:
        p["reply_to_message_id"] = reply_to
    if html:
        p["parse_mode"] = "HTML"
    if buttons:
        p["reply_markup"] = {"inline_keyboard": buttons}
    return api("sendMessage", **p)


def send_document(path, caption="", reply_to=None):
    path = pathlib.Path(path)
    boundary = uuid.uuid4().hex
    body = b""
    fields = [("chat_id", str(CHAT_ID)), ("caption", caption)]
    if reply_to:
        fields.append(("reply_to_message_id", str(reply_to)))
    for name, val in fields:
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{path.name}"\r\n'
             f'Content-Type: application/pdf\r\n\r\n').encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/sendDocument", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)



def pin_only(message_id):
    """Make this the only pinned message, so the pinned bar always jumps to the latest report."""
    try:
        api("unpinAllChatMessages", chat_id=CHAT_ID)
        api("pinChatMessage", chat_id=CHAT_ID, message_id=message_id, disable_notification="true")
    except Exception:
        pass  # pinning is a convenience; never fail a report because of it
