import socket

HOST="127.0.0.1"
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

        #message="Hello"
        while True:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as client_socket:
                client_socket.connect((HOST, PORT))
            #Input mesaj client
                message = input("Enter message (or 'quit' to exit): ")
                if not message or message.lower() == "quit":
                    print("Closing connection...")
                    break
                #Send
                client_socket.sendall(encrypt(message, KEY))
                print(f"Sent: {message}")
                #Listen
                encrypted_response = client_socket.recv(4096)
                if not encrypted_response:
                    print("Server closed the connection.")
                    break
                decrypted_response = decrypt(encrypted_response, KEY)
                print(f"Decoded message from server: {decrypted_response}\n")

if __name__ == "__main__":
    main()