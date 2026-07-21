import datetime
import json
import socket
import sqlite3
import threading

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

#region Socket
#TODO: Creati conexiunea socket

#TODO: dati bind pe 0.0.0.0 si portul 3000, apoi listen
clients = {}  # dictionar pentru clientii conectati {username: {"conn": conn, "lock": Lock, "user_id": id}}
clients_lock = threading.Lock()
#endregion

#region SQL
sql = sqlite3.connect('whatsapp.db', check_same_thread=False)
cursor = sql.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               username TEXT NOT NULL UNIQUE,
               password NOT NULL
               );
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS friendship(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               user1 INTEGER NOT NULL,
               user2 INTEGER NOT NULL,
               sender_id INTEGER NOT NULL,
               status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'accepted', 'blocked'
               UNIQUE (user1, user2),
               FOREIGN KEY (user1) REFERENCES users(id),
               FOREIGN KEY (user2) REFERENCES users(id),
               FOREIGN KEY (sender_id) REFERENCES users(id)
               );''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS messages(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               sender_id INTEGER NOT NULL,
               receiver_id INTEGER NOT NULL,
               content TEXT NOT NULL,
               timestamp DATETIME NOT NULL,
               FOREIGN KEY (sender_id) REFERENCES users(id),
               FOREIGN KEY (receiver_id) REFERENCES users(id)
               )
''')
sql.commit()

# migrare: bazele de date create de versiunea veche a serverului nu aveau
# coloana "kind" (text/image), asa ca o adaugam daca lipseste
cursor.execute("PRAGMA table_info(messages)")
existing_columns = {row[1] for row in cursor.fetchall()}
if "kind" not in existing_columns:
    cursor.execute("ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'text'")
    sql.commit()
#endregion

print("[SERVER] Ascult pe portul 3000...")

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(stored_password: str, password: str) -> bool:
    if not stored_password:
        return False
    if stored_password.startswith("$argon2"):
        try:
            return ph.verify(stored_password, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
    return stored_password == password

def send_json(conn, lock, payload):
    wire = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    with lock:
        conn.sendall(wire)


def recv_packet(conn, buffer):
    """Citeste din socket pana gaseste un mesaj complet (delimitat de \\n)
    si il transforma in dictionar. Clientul trimite pachetele cu un \\n la
    final, deci nu putem sa facem json.loads pe un singur recv() -
    un mesaj poate veni fragmentat, sau doua mesaje pot veni in acelasi recv()."""
    """TODO:    itereaza in buffer cat timp \n nu este in buffer (HINT: \n trebuie sa fie de tip byte). 
                Vei avea o variabila chunk care primeste 4MB.Trateaza cazul daca chunk e gol sa returnezi none si buffer.
                Variabila buffer va contine toate chunk urile"""


    raw_line, buffer = buffer.split(b"\n", 1)
    if not raw_line:
        return {}, buffer

    try:
        return json.loads(raw_line.decode("utf-8")), buffer
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, buffer


def user_pair(id1, id2):
    """TODO: Aranjeaza cele doua id-uri in ordine stabila (user1 < user2), la fel
    ca in baza de date, si returneaza-le ca tuple (user1, user2)"""
    pass


def get_online(username):
    with clients_lock:
        return clients.get(username)


def get_msg(conn):
    current_username = None  # username-ul pentru acest thread/conexiune
    current_user_id = None   # ID-ul utilizatorului pentru acest thread/conexiune
    send_lock = threading.Lock()
    buffer = b""

    while True:
        """#TODO: Preia payload si buffer cu recv_packet. 
        Adauga un break daca nu exista obiectul payload si 
        un continue daca payload e gol"""


        msg_type = str(payload.get("type", "")).upper()
        print(f"Mesaj primit: {msg_type}")

        if msg_type == "AUTH":
            user = payload.get("username", "").strip()
            password = payload.get("password", "")
            #TODO: daca nu exista user sau parola trimite un json de tip ERROR si dupa continua


            cursor.execute("SELECT id, password FROM users WHERE username=?", (user,))
            row = cursor.fetchone()
            """TODO: Daca nu exista acest user (vezi cele 2 linii de mai sus), creaza un try except unde:
                - criptezi parola, inserezi user si parola in DB, dai commit()
                in except vei arunca sqlite3.IntegrityError si vei face in acest caz:
                -selectezi id si parola din username pentru username ul salvat in variabila user
                -preia numai 1 entry si trimite cu json un mesaj de tip ERROR si continua altfel salveaza in user_id si saved_password din row
                -verifica parola
            """
            """TODO: Daca exista o intrare:-
                - salveaza user_id si saved_password din row
                - verifica parola si continua daca e gresita
                - daca parola nu incepe cu argon2, cursor.execute updateaza campul password 
                    din tabelul users unde id ul este user_id cu parola hashed. Da commit
            """
            
            with clients_lock:
                if user in clients:
                    send_json(conn, send_lock, {"type": "ERROR", "message": "Userul este deja logat!"})
                    continue
                clients[user] = {"conn": conn, "lock": send_lock, "user_id": user_id}

            current_username = user
            current_user_id = user_id
            print(f"[SERVER] {user} s-a conectat.")
            send_json(conn, send_lock, {"type": "AUTH_OK", "user_id": user_id, "username": user})

        elif msg_type == "LIST_FRIENDS":
            if not current_user_id:
                continue

            friends = {}
            pending_in = []
            pending_out = []

            query = '''
                SELECT u.username, f.status, f.sender_id
                FROM friendship f
                JOIN users u ON u.id = CASE WHEN f.user1 = ? THEN f.user2 ELSE f.user1 END
                WHERE f.user1 = ? OR f.user2 = ?
            '''
            cursor.execute(query, (current_user_id, current_user_id, current_user_id))
            for friend_username, status, sender_id in cursor.fetchall():
                if status == "accepted":
                    friends[friend_username] = 1 if get_online(friend_username) else 0
                elif status == "pending":
                    if sender_id == current_user_id:
                        pending_out.append(friend_username)
                    else:
                        pending_in.append(friend_username)

            pending_in.sort()
            pending_out.sort()
            send_json(conn, send_lock, {
                "type": "FRIENDS",
                "friends": friends,
                "pending_in": pending_in,
                "pending_out": pending_out,
            })

        elif msg_type == "FRIEND_REQUEST":
            if not current_user_id:
                continue

            target_username = payload.get("username", "").strip()
            if not target_username:
                send_json(conn, send_lock, {"type": "ERROR", "message": "Target username is required."})
                continue

            cursor.execute("SELECT id FROM users WHERE username=?", (target_username,))
            res = cursor.fetchone()
            if not res:
                send_json(conn, send_lock, {"type": "ERROR", "message": "User does not exist."})
                continue

            target_id = res[0]
            if target_id == current_user_id:
                send_json(conn, send_lock, {"type": "ERROR", "message": "You cannot add yourself."})
                continue

            user1, user2 = user_pair(current_user_id, target_id)
            cursor.execute("SELECT status, sender_id FROM friendship WHERE user1=? AND user2=?", (user1, user2))
            existing = cursor.fetchone()

            if existing is None:
                cursor.execute(
                    "INSERT INTO friendship (user1, user2, sender_id) VALUES (?, ?, ?)",
                    (user1, user2, current_user_id),
                )
                sql.commit()
                print(f"Cerere de prietenie de la {current_user_id} la {target_id} salvata.")
                send_json(conn, send_lock, {"type": "INFO", "message": "Friend request sent."})
            else:
                status, sender_id = existing
                if status == "accepted":
                    send_json(conn, send_lock, {"type": "INFO", "message": "Already friends."})
                elif status == "pending" and sender_id == current_user_id:
                    send_json(conn, send_lock, {"type": "INFO", "message": "Friend request already pending."})
                elif status == "pending":
                    # celalalt user a trimis deja o cerere -> asta o accepta
                    cursor.execute(
                        "UPDATE friendship SET status='accepted' WHERE user1=? AND user2=?",
                        (user1, user2),
                    )
                    sql.commit()
                    send_json(conn, send_lock, {"type": "INFO", "message": "Friend request accepted."})
                else:
                    send_json(conn, send_lock, {"type": "ERROR", "message": "Friend request could not be processed."})

        elif msg_type == "SELECT_CONVERSATION":
            if not current_user_id:
                continue

            target_username = payload.get("username", "").strip()
            cursor.execute("SELECT id FROM users WHERE username=?", (target_username,))
            res = cursor.fetchone()
            if not res:
                send_json(conn, send_lock, {"type": "ERROR", "message": "Selected user does not exist."})
                continue

            target_id = res[0]
            user1, user2 = user_pair(current_user_id, target_id)
            cursor.execute("SELECT status FROM friendship WHERE user1=? AND user2=?", (user1, user2))
            row = cursor.fetchone()
            if not row or row[0] != "accepted":
                send_json(conn, send_lock, {"type": "ERROR", "message": "You can only chat with accepted friends."})
                continue

            query = '''
                SELECT su.username, ru.username, m.kind, m.content, m.timestamp
                FROM messages m
                JOIN users su ON su.id = m.sender_id
                JOIN users ru ON ru.id = m.receiver_id
                WHERE (m.sender_id = ? AND m.receiver_id = ?)
                   OR (m.sender_id = ? AND m.receiver_id = ?)
                ORDER BY m.timestamp ASC, m.id ASC
            '''
            cursor.execute(query, (current_user_id, target_id, target_id, current_user_id))
            messages_list = [
                {"from": row[0], "to": row[1], "kind": row[2], "content": row[3], "timestamp": row[4]}
                for row in cursor.fetchall()
            ]
            send_json(conn, send_lock, {"type": "CONVERSATION", "username": target_username, "messages": messages_list})

        elif msg_type == "SEND_MESSAGE":
            if not current_user_id:
                continue

            target_username = payload.get("to", "").strip()
            kind = payload.get("kind", "text")
            content = payload.get("content", "")
            #TODO: daca nu e username sau content, foloseste send_json() cu tip ERROR, apoi continua
            
            #TODO: daca tipul (kind) mesajului nu e text sau image, trimite o eroare, apoi continue

            cursor.execute("SELECT id FROM users WHERE username=?", (target_username,))
            res = cursor.fetchone()

            #TODO: daca nu este res, eroare, apoi continue


            target_id = res[0]
            user1, user2 = user_pair(current_user_id, target_id)
            cursor.execute("SELECT status FROM friendship WHERE user1=? AND user2=?", (user1, user2))
            row = cursor.fetchone()
            if not row or row[0] != "accepted":
                send_json(conn, send_lock, {"type": "ERROR", "message": "You can only chat with accepted friends."})
                continue

            timestamp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
            cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, content, kind, timestamp) VALUES (?, ?, ?, ?, ?)",
                (current_user_id, target_id, content, kind, timestamp),
            )
            sql.commit()

            forwarded = {
                "type": "NEW_MESSAGE",
                "from": current_username,
                "to": target_username,
                "kind": kind,
                "content": content,
                "timestamp": timestamp,
            }
            recipient = get_online(target_username)
            if recipient:
                try:
                    send_json(recipient["conn"], recipient["lock"], forwarded)
                except OSError:
                    with clients_lock:
                        if clients.get(target_username, {}).get("conn") is recipient["conn"]:
                            del clients[target_username]
            #TODO: Trimite cu functia send_json message_sent target_username, kind si timestamp

        elif msg_type == "CLOSE":
            break

        else:
            send_json(conn, send_lock, {"type": "ERROR", "message": "Unknown packet type."})

    if current_username:
        with clients_lock:
            if clients.get(current_username, {}).get("conn") is conn:
                del clients[current_username]  # Stergem userul la deconectare
        print(f"[SERVER] {current_username} s-a deconectat.")


while True:
    pass
    #TODO: accepta o conexiune si saleaza conexiunea si adresa. Creaza un print unde vei scrie cu ce adresa s a efectuat conexiunea
    #TODO: Creaza un thread care are target functia get_msg, args conn si este un daemon. Porneste thread ul