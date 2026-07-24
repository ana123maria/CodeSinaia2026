# -*- coding: utf-8 -*-
"""
Conversation state: in-memory cache of messages per friend, image
saving/preview, formatting lines for the UI to render. Lifted as-is
from GUI.py, just split into its own file.
"""

import base64
import datetime
import hashlib
import json
import os

from network_client import decrypt_text

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
PREVIEW_MAX_WIDTH = 380
PREVIEW_MAX_HEIGHT = 260

os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def decode_text_for_display(raw_value: str) -> str:
    try:
        # TODO: use the decrypt_text() function here to decrypt the raw_value
        # and return the decrypted text instead of the raw_value.
        return decrypt_text(raw_value)
    except Exception:
        # If decryption fails, we don't want to crash the app. Just return the raw value.
        return raw_value


def save_image_from_payload(encrypted_payload: str) -> dict:
    try:
        # TODO: use the decrypt_text() function here to decrypt the encrypted_payload
        decoded_json = decrypt_text(encrypted_payload)
        image_payload = json.loads(decoded_json)
        image_bytes = base64.b64decode(image_payload["data"].encode("utf-8"), validate=True)

        original_name = os.path.basename(image_payload.get("name", "image.bin")) or "image.bin"
        digest = hashlib.sha1(image_bytes).hexdigest()[:12]
        saved_name = f"{digest}_{original_name}"
        saved_path = os.path.join(DOWNLOADS_DIR, saved_name)

        if not os.path.exists(saved_path):
            with open(saved_path, "wb") as image_file:
                image_file.write(image_bytes)

        return {"ok": True, "path": saved_path, "name": original_name}
    except Exception as exc:
        return {"ok": False, "error": f"unable to decode image: {exc}"}


def build_image_preview(image_path: str):
    if PIL_AVAILABLE:
        try:
            image = Image.open(image_path)
            image.thumbnail((PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT))
            return ImageTk.PhotoImage(image)
        except Exception:
            pass
    return None


def format_timestamp_for_display(raw_timestamp: str) -> str:
    """
    Storage stays UTC ISO ("2026-06-18T16:48:00") so sorting in the
    database (ORDER BY timestamp) keeps working correctly regardless
    of which timezone each user's machine is in. Only the chat
    transcript converts that UTC instant to this computer's local
    timezone before showing the short "day-month hour:minute" form.
    """
    try:
        parsed = datetime.datetime.fromisoformat(raw_timestamp).replace(tzinfo=datetime.timezone.utc)
        local_time = parsed.astimezone()  # converts to this machine's local timezone
        return local_time.strftime("%d-%m %H:%M")
    except ValueError:
        return raw_timestamp


class ConversationStore:
    def __init__(self, current_username_getter):
        self._cache = {}
        self._get_current_username = current_username_getter

    def append_message(self, message: dict):
        current_username = self._get_current_username()
        friend = message.get("from") if message.get("from") != current_username else message.get("to")
        if not friend:
            return None

        entry = {
            "from": message.get("from", ""),
            "to": message.get("to", ""),
            "kind": message.get("kind", "text"),
            "content": message.get("content", ""),
            "timestamp": message.get("timestamp", ""),
        }
        if entry["kind"] == "text":
            entry["decoded_text"] = decode_text_for_display(entry["content"])
        elif entry["kind"] == "image":
            entry["image_info"] = save_image_from_payload(entry["content"])

        conversation = self._cache.setdefault(friend, [])
        conversation.append(entry)
        if len(conversation) > 500:
            del conversation[: len(conversation) - 500]
        return friend

    def reset_conversation(self, friend: str) -> None:
        self._cache[friend] = []

    def render_into(self, text_widget, friend, tk_module, clear_first=True):
        """
        Writes the conversation for `friend` straight into a tkinter
        Text widget (the same widget the gui.py canvas already has
        room for) - mirrors render_conversation() from GUI.py.

        clear_first=False lets the caller pre-write something (like a
        "Chat with: X" header) before this appends the transcript.
        """
        text_widget.configure(state=tk_module.NORMAL)
        if clear_first:
            text_widget.delete("1.0", tk_module.END)

        if not friend:
            text_widget.insert(tk_module.END, "Select a friend to open a conversation.\n")
            text_widget.configure(state=tk_module.DISABLED)
            return []

        preview_images = []
        for message in self._cache.get(friend, []):
            timestamp = format_timestamp_for_display(message.get("timestamp", ""))
            author = message.get("from", "?")
            kind = message.get("kind", "text")

            if kind == "text":
                text_value = message.get("decoded_text")
                if text_value is None:
                    text_value = decode_text_for_display(message.get("content", ""))
                    message["decoded_text"] = text_value
                text_widget.insert(tk_module.END, f"[{timestamp}] {author}: {text_value}\n")
                continue

            if kind == "image":
                image_info = message.get("image_info")
                if image_info is None:
                    image_info = save_image_from_payload(message.get("content", ""))
                    message["image_info"] = image_info

                if image_info.get("ok"):
                    image_path = image_info["path"]
                    image_name = image_info.get("name", os.path.basename(image_path))
                    text_widget.insert(tk_module.END, f"[{timestamp}] {author} sent image: {image_name}\n")
                    preview = build_image_preview(image_path)
                    if preview is not None:
                        text_widget.image_create(tk_module.END, image=preview)
                        preview_images.append(preview)
                        text_widget.insert(tk_module.END, "\n\n")
                    else:
                        text_widget.insert(tk_module.END, f"Preview unavailable. File saved at: {image_path}\n\n")
                else:
                    text_widget.insert(
                        tk_module.END,
                        f"[{timestamp}] {author} sent image but could not be loaded: "
                        f"{image_info.get('error', 'unknown error')}\n",
                    )
                continue

            text_widget.insert(tk_module.END, f"[{timestamp}] {author}: [unsupported message type]\n")

        text_widget.see(tk_module.END)
        text_widget.configure(state=tk_module.DISABLED)
        return preview_images


def utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")