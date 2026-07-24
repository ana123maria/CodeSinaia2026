# -*- coding: utf-8 -*-
"""
main.py - the only file that "knows" about all three screens.

login/build/gui.py, signup/build/gui.py and main/build/gui.py are
never edited. Each one is loaded as an isolated module (importlib),
which runs its top-level code (builds `window`, `canvas`, every
`button_N`) but - because each file guards its own `mainloop()` call
behind `if __name__ == "__main__":` - does NOT start its own event
loop or block anything. This script owns the single real mainloop.

Button -> function map:
    main/build/gui.py   button_1  ->  Trimite      (send_text_message)
    main/build/gui.py   button_2  ->  Lupa         (add_friend, reads the search box)
    main/build/gui.py   button_3  ->  Agrafa       (send_image_message)
    main/build/gui.py   button_4  ->  GitHub       (opens repo link in browser)
    login/build/gui.py  button_1  ->  Login        (login_or_register)
    signup/build/gui.py button_1  ->  Register     (login_or_register, same AUTH packet -
                                                     the server auto-registers unknown usernames)

Layout map for main/build/gui.py:
    search bar   (X -> Y)    + button_2  -> type a username here, press the magnifier to add them
    "Chats"      (X -> Y)  -> accepted friends list, click = open conversation
    "Friends"    (X -> Y)  -> pending INCOMING requests only, each with an Accept button
    user panel   (X -> Y)  -> "{username}\nID: {user_id}"
    conversation (X -> Y) -> Text widget (the chat transcript)
    message box  (X -> Y) -> Entry widget (what you type to send)
"""

import base64
import importlib.util
import json
import mimetypes
import os
import sys
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog

from network_client import ChatClient, encrypt_text, MAX_IMAGE_BYTES
from conversation_store import ConversationStore, utc_timestamp

ROOT_DIR = Path(__file__).parent
GITHUB_URL = "https://github.com/ana123maria/CodeSinaia2026"  # placeholder


# ----------------------------------------------------------------------
# Loading each gui.py as an isolated module, without editing it
# ----------------------------------------------------------------------
def load_screen_module(module_name: str, gui_py_path: Path):
    """
    Imports a Tkinter-Designer gui.py file under a private module name
    so the three files (all literally named gui.py) don't collide in
    sys.modules. Running it executes everything up to (but not
    including) mainloop(), since that call is guarded by
    `if __name__ == "__main__":` inside the original file.
    """
    spec = importlib.util.spec_from_file_location(module_name, gui_py_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------------
# App: holds all state, wires each screen's buttons to real behaviour
# ----------------------------------------------------------------------
class App:
    def __init__(self):
        self.client = ChatClient()
        self.user_id = 0
        self.current_username = ""
        self.current_chat = None
        self.store = ConversationStore(current_username_getter=lambda: self.current_username)

        self.login_module = None
        self.signup_module = None
        self.main_module = None

        # Widgets we create ourselves and place on top of each canvas
        # (the gui.py files only draw rectangles - they don't create
        # Entry/Text widgets, since Tkinter Designer doesn't know which
        # rectangles are meant to be interactive).
        self.login_username_entry = None
        self.login_password_entry = None
        self.login_error_label = None

        self.signup_username_entry = None
        self.signup_password_entry = None
        self.signup_repeat_entry = None
        self.signup_error_label = None

        self.search_entry = None
        self.user_panel_label = None
        self.chats_frame = None
        self.friends_frame = None
        self.conversation_text = None
        self.message_entry = None
        self.status_text = "Connected."
        self.chat_with_text = "none selected"

        self.rendered_preview_images = []

    # ------------------------------------------------------------------
    # Step 1: Login screen
    # ------------------------------------------------------------------
    def show_login(self):
        self.login_module = load_screen_module(
            "screen_login", ROOT_DIR / "login" / "build" / "gui.py"
        )
        window = self.login_module.window

        # Username field sits on the rectangle at (x1, y1 -> x2, y2)
        self.login_username_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5")
        self.login_username_entry.place(x=16, y=65, width=370, height=16)  # TODO: replace x1, y1, x2, y2 with actual coordinates

        # Password field sits on the rectangle at (x1, y1 -> x2, y2)
        self.login_password_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5", show="*")
        self.login_password_entry.place(x=16, y=117, width=370, height=16)  # TODO: replace x1, y1, x2, y2 with actual coordinates

        # Small error label between the password field and the footer
        self.login_error_label = tk.Label(window, text="", fg="#D33A3A", bg="#D9D9D9", font=("Inter", 11))
        self.login_error_label.place(x=16.0, y=136.0, width=370.0, height=16.0)

        # button_1 = Login (submit). button_2 = Register (navigate to signup screen).
        # Both already exist in gui.py - we only swap their commands.
        self.login_module.button_1.configure(command=self._handle_login_submit)
        self.login_module.button_2.configure(command=self._handle_go_to_signup)

        window.bind("<Return>", lambda _event: self._handle_login_submit()) #enter=submit
        self.login_username_entry.focus_set()
        window.protocol("WM_DELETE_WINDOW", lambda: sys.exit())

        # quit() (called from a button command) only stops mainloop() - it
        # does not destroy the window. We do the destroy + "which screen
        # comes next" decision here, AFTER mainloop() has actually
        # returned control to this function. Building a brand-new Tk()
        # root from inside the still-unwinding callback that called
        # quit() is what was causing main/build's mainloop to hang.
        self._next_screen = None
        window.mainloop()
        window.destroy()

        if self._next_screen == "signup":
            self.show_signup()
        elif self._next_screen == "main":
            self.show_main()

    def _handle_login_submit(self):
        window = self.login_module.window
        username = self.login_username_entry.get().strip()
        password = self.login_password_entry.get()

        if not username or not password:
            self.login_error_label.config(text="Username and password are required.")
            return

        self.client.connect()
        try:
            self.client.send_packet({"type": "AUTH", "username": username, "password": password})
            response = self.client.recv_packet_blocking(timeout_seconds=3.0)
        except Exception as exc:
            self.login_error_label.config(text=f"Login failed: {exc}")
            return

        if response is None:
            self.login_error_label.config(text="Server closed the connection.")
            return
        if str(response.get("type", "")).upper() == "ERROR":
            self.login_error_label.config(text=str(response.get("message", "Unknown login error")))
            return
        if str(response.get("type", "")).upper() != "AUTH_OK":
            self.login_error_label.config(text="Unexpected login response.")
            return

        self.user_id = int(response.get("user_id", 0))
        self.current_username = str(response.get("username", username))
        self._next_screen = "main" #TODO: main screen
        window.quit()

    def _handle_go_to_signup(self):
        self._next_screen = "signup" #TODO: signup screen
        self.login_module.window.quit()

    # ------------------------------------------------------------------
    # Signup screen
    # ------------------------------------------------------------------
    def show_signup(self):
        self.signup_module = load_screen_module(
            "screen_signup", ROOT_DIR / "signup" / "build" / "gui.py"
        )
        window = self.signup_module.window

        self.signup_username_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5")
        self.signup_username_entry.place(x=16, y=60, width=370, height=16) #TODO: replace with actual coordinates

        self.signup_password_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5", show="*")
        self.signup_password_entry.place(x=16, y=100, width=370, height=16) #TODO: replace with actual coordinates

        self.signup_repeat_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5", show="*")
        self.signup_repeat_entry.place(x=16, y=141, width=370, height=16) #TODO: replace with actual coordinates

        self.signup_error_label = tk.Label(window, text="", fg="#D33A3A", bg="#D9D9D9", font=("Inter", 11))
        self.signup_error_label.place(x=16.0, y=143.0, width=370.0, height=0.0)

        # button_1 = Register (submit). button_2 = Login (navigate back to login screen).
        self.signup_module.button_1.configure(command=self._handle_signup_submit)
        self.signup_module.button_2.configure(command=self._handle_go_to_login)

        window.bind("<Return>", lambda _event: self._handle_signup_submit())
        self.signup_username_entry.focus_set()
        window.protocol("WM_DELETE_WINDOW", lambda: sys.exit())

        self._next_screen = None
        window.mainloop()
        window.destroy()

        if self._next_screen == "login":
            #TODO show login screen
            self.show_login()
        #TODO altfel dacă e main, show main
        elif self._next_screen == "main":
            self.show_main()
        

    def _handle_go_to_login(self):
        self._next_screen = "login"
        self.signup_module.window.quit()

    def _handle_signup_submit(self):
        username = self.signup_username_entry.get().strip()
        password = self.signup_password_entry.get()
        repeat_password = self.signup_repeat_entry.get()

        if not username or not password or not repeat_password:
            self.signup_error_label.config(text="All fields are required.")
            return
        if password != repeat_password:
            self.signup_error_label.config(text="Passwords do not match.")
            return
        
        self.client.connect()
        try:
            self.client.send_packet({"type": "AUTH", "username": username, "password": password})
            response = self.client.recv_packet_blocking(timeout_seconds=3.0)
        except Exception as exc:
            self.signup_error_label.config(text=f"Registration failed: {exc}")
            return

        if response is None or str(response.get("type", "")).upper() != "AUTH_OK":
            message = "Server closed the connection." if response is None else str(response.get("message", "Unknown error"))
            self.signup_error_label.config(text=message)
            return

        self.user_id = int(response.get("user_id", 0))
        self.current_username = str(response.get("username", username))
        self._next_screen = "main"
        self.signup_module.window.quit()

    # ------------------------------------------------------------------
    # Step 2: Main chat screen
    # ------------------------------------------------------------------
    def show_main(self):
        self.main_module = load_screen_module(
            "screen_main", ROOT_DIR / "main" / "build" / "gui.py"
        )
        window = self.main_module.window

        # --- Search bar (X1, Y1 -> X2, Y2): type a username, press the magnifier (button_2) ---
        self.search_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5")
        self.search_entry.place(x=7, y=22, width=165, height=50)  # TODO: replace x1, y1, x2, y2 with actual coordinates
        self.main_module.button_2.configure(command=self._handle_add_friend)

        # --- User panel (X1, Y1 -> X2, Y2): "{username}\nID: {id}" ---
        self.user_panel_label = tk.Label(
            window,
            text=f"{self.current_username}\nID: {self.user_id}",
            bg="#C5C5C5",
            justify="center",
        )
        self.user_panel_label.place(x=663, y=22, width=121, height=50)  # TODO: replace x1, y1, x2, y2 with actual coordinates

        # --- "Chats" list (X1, Y1 -> X2, Y2): accepted friends, click = open conversation ---
        self.chats_frame = tk.Frame(window, bg="#C5C5C5")
        self.chats_frame.place(x=7, y=118, width=121, height=242)  # TODO: replace x1, y1, x2, y2 with actual coordinates

        # --- "Friends" list (X1, Y1 -> X2, Y2): pending incoming requests only ---
        self.friends_frame = tk.Frame(window, bg="#C5C5C5")
        self.friends_frame.place(x=7, y=391, width=121, height=159)  # TODO: replace x1, y1, x2, y2 with actual coordinates

        # --- Conversation (X1,Y1 -> X2,Y2) ---
        self.conversation_text = tk.Text(window, bd=0, highlightthickness=0)
        self.conversation_text.place(x=154, y=118, width=630, height=385)  # TODO: replace x1, y1, x2, y2 with actual coordinates
        self.conversation_text.bind("<Key>", lambda _e: "break")
        self.conversation_text.bind("<<Paste>>", lambda _e: "break")
        self.conversation_text.configure(state=tk.DISABLED)

        # --- Message entry (X1,Y1 -> X2,Y2) ---
        self.message_entry = tk.Entry(window, bd=0, highlightthickness=0, bg="#C5C5C5")
        self.message_entry.place(x=154, y=512, width=509, height=33)  # TODO: replace x1, y1, x2, y2 with actual coordinates
        window.bind("<Return>", lambda _event: self._handle_send_text())

        # --- button_1 = Trimite, button_3 = Agrafa, button_4 = GitHub ---
        self.main_module.button_1.configure(command=self._handle_send_text)
        self.main_module.button_3.configure(command=self._handle_send_image)
        self.main_module.button_4.configure(command=lambda: webbrowser.open(GITHUB_URL))

        self.client.start_recv_loop(
            on_packet=lambda packet: window.after(0, self._handle_server_packet, packet),
            on_disconnect=lambda: window.after(0, self._set_status, "Disconnected.", True),
        )

        self._poll_friends()
        self._render_conversation()

        window.protocol("WM_DELETE_WINDOW", self._handle_close)
        window.mainloop()

    def _poll_friends(self):
        if self.client.stop_event.is_set():
            return
        try:
            self.client.send_packet({"type": "LIST_FRIENDS"})
        except OSError:
            return
        self.main_module.window.after(10000, self._poll_friends)

    # ------------------------------------------------------------------
    # "Chats" (accepted friends) + "Friends" (pending incoming) rendering
    # ------------------------------------------------------------------
    def _update_friends_ui(self, friends_data: dict, pending_in: list) -> None:
        for widget in self.chats_frame.winfo_children():
            widget.destroy()
        for widget in self.friends_frame.winfo_children():
            widget.destroy()

        for name in sorted(friends_data.keys()):
            is_online = bool(friends_data[name])
            
            #TODO if is_online then color = green else color = red
            color = None
            if is_online():
                color = "#3AD360"
            else:
                color = "#D33A3A"
            
            status_text = "Online" if is_online else "Offline"
            tk.Button(
                self.chats_frame,
                text=f"{name} ({status_text})",
                fg=color,
                command=lambda friend=name: self._handle_select_conversation(friend),
            ).pack(fill="x", pady=2)

        if not friends_data:
            tk.Label(self.chats_frame, text="No friends yet.", bg="#C5C5C5", anchor="w").pack(fill="x", pady=2)

        if pending_in:
            for pending_username in pending_in:
                row = tk.Frame(self.friends_frame, bg="#C5C5C5")
                row.pack(fill="x", pady=1)
                tk.Label(row, text=pending_username, bg="#C5C5C5", anchor="w").pack(side="left", fill="x", expand=True)
                tk.Button(
                    row,
                    text="Accept",
                    command=lambda friend=pending_username: self._handle_accept_friend(friend),
                ).pack(side="right")
        else:
            tk.Label(self.friends_frame, text="No requests.", bg="#C5C5C5", anchor="w").pack(fill="x", pady=2)

    def _handle_add_friend(self):
        friend_username = self.search_entry.get().strip()
        if not friend_username:
            return
        self.client.send_packet({"type": "FRIEND_REQUEST", "username": friend_username})
        self.search_entry.delete(0, tk.END)

    def _handle_accept_friend(self, friend_username: str):
        self.client.send_packet({"type": "FRIEND_REQUEST", "username": friend_username})
        self.client.send_packet({"type": "LIST_FRIENDS"})

    def _handle_select_conversation(self, friend: str):
        self.current_chat = friend
        self.chat_with_text = friend
        self._render_conversation()
        self.client.send_packet({"type": "SELECT_CONVERSATION", "username": friend})

    def _handle_send_text(self):
        if not self.current_chat:
            self._set_status("Select a friend before sending a message.", True)
            return

        message_text = self.message_entry.get().strip()
        if not message_text:
            return

        #TODO ecrypted = use encrypt_text function to encrypt message_text
        encrypted = None
        self.client.send_packet({"type": "SEND_MESSAGE", "to": self.current_chat, "kind": "text", "content": encrypted})

        self.store.append_message(
            {
                "from": self.current_username,
                "to": self.current_chat,
                "kind": "text",
                "content": encrypted,
                "timestamp": utc_timestamp(),
            }
        )
        self._render_conversation()
        self.message_entry.delete(0, tk.END)

    def _handle_send_image(self):
        if not self.current_chat:
            self._set_status("Select a friend before sending an image.", True)
            return

        image_path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.webp *.bmp")],
        )
        if not image_path:
            return

        try:
            with open(image_path, "rb") as image_file:
                raw_bytes = image_file.read()
        except OSError as exc:
            self._set_status(f"Could not read image: {exc}", True)
            return

        if len(raw_bytes) > MAX_IMAGE_BYTES:
            self._set_status("Image too large (max 2MB).", True)
            return

        image_payload = {
            "name": os.path.basename(image_path),
            "mime": mimetypes.guess_type(image_path)[0] or "application/octet-stream",
            "data": base64.b64encode(raw_bytes).decode("utf-8"),
        }
        encrypted_payload = encrypt_text(json.dumps(image_payload, separators=(",", ":")))

        self.client.send_packet({"type": "SEND_MESSAGE", "to": self.current_chat, "kind": "image", "content": encrypted_payload})

        self.store.append_message(
            {
                "from": self.current_username,
                "to": self.current_chat,
                "kind": "image",
                "content": encrypted_payload,
                "timestamp": utc_timestamp(),
            }
        )
        self._render_conversation()

    def _render_conversation(self):
        self.conversation_text.configure(state=tk.NORMAL)
        self.conversation_text.delete("1.0", tk.END)
        self.conversation_text.insert(tk.END, f"Chat with: {self.chat_with_text}\n\n")
        self.rendered_preview_images = self.store.render_into(self.conversation_text, self.current_chat, tk, clear_first=False)

    def _set_status(self, text: str, is_error: bool = False):
        self.status_text = text
        prefix = "[!] " if is_error else "[i] "
        print(prefix + text)

    # ------------------------------------------------------------------
    # Server -> UI
    # ------------------------------------------------------------------
    def _handle_server_packet(self, packet: dict):
        packet_type = str(packet.get("type", "")).upper()

        if packet_type == "FRIENDS":
            friends_data = packet.get("friends", {})
            pending_in = packet.get("pending_in", [])
            self._update_friends_ui(friends_data, pending_in)
            self._set_status("Friends list updated.")
            return

        if packet_type == "CONVERSATION":
            friend = packet.get("username", "")
            if not friend:
                return
            self.store.reset_conversation(friend)
            for message in packet.get("messages", []):
                self.store.append_message(message)
            if self.current_chat == friend:
                self._render_conversation()
            return

        if packet_type == "NEW_MESSAGE":
            self.store.append_message(packet)
            if self.current_chat == packet.get("from"):
                self._render_conversation()
            else:
                self._set_status(f"New message from {packet.get('from', 'unknown')}")
            return

        if packet_type == "INFO":
            self._set_status(str(packet.get("message", "")))
            self.client.send_packet({"type": "LIST_FRIENDS"})
            return

        if packet_type == "ERROR":
            self._set_status(str(packet.get("message", "Unknown error")), True)
            return

    def _handle_close(self):
        self.client.close()
        sys.exit()


if __name__ == "__main__":
    App().show_login()