import socket

HOST="0.0.0.0"
PORT=5000
KEY="cheie"

def xor_transform(data:bytes,key:str) -> bytes: #returneaza bytes
    key_bytes = key.encode("utf-8") #transforma cheia in biti
    return bytes(byte ^ key_bytes[i % len(key_bytes)] for i,byte in enumerate(data))

def encrypt(text:str,key:str) -> bytes:
    return xor_transform(text.encode("utf-8"),key)

def decrypt(data:bytes, key:str) -> str: #returneaza string
    return xor_transform(data,key).decode("utf-8")

def main() -> None:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server_socket.bind((HOST,PORT))
        server_socket.listen(1)
        print(f"Server is listening on {HOST}:{PORT}")

        conn, addr = server_socket.accept() #a,b=b,a <=> swap(a,b)
        print(f"Connection from {addr}")

            while True:
                with conn:
                    # Listen
                    encrypted_data = conn.recv(4096)
                    # Primeste ceva?
                    if not encrypted_data:
                        print(f"Client {addr} disconnected.")
                        break
                    # Decripteaza mesajul de la client
                    message = decrypt(encrypted_data, KEY)
                    print(f"Received from client: {message}")
                    # Send answer
                    response = f"Echo: {message}"
                    conn.sendall(encrypt(response, KEY))
                    print("Sent encrypted message back to client\n")

if __name__ == "__main__":
    main()