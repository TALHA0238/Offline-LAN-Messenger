import os
import socket
import threading
import pickle
import struct
import cv2
import pyaudio
import numpy as np
import noisereduce as nr

# Constants
BROADCAST_PORT = 5001
VIDEO_PORT = 5003
CONTROL_PORT = 5005
TEXT_PORT = 5007
VOICE_PORT = 5009
BUFFER_SIZE = 4096
FRAME_WIDTH, FRAME_HEIGHT = 640, 480
CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class Peer:
    def __init__(self, username=None):
        self.active_windows = set()
        self.message_queues = {}
        self.username = username if username else socket.gethostname()
        self.peers = set()
        self.running = True
        self.is_recording = False
        self.audio_frames = []
        self.video_call_callback = None
        self.voice_message_callback = None
        self.text_message_callback = None
        self.call_end_callback = None
        self.current_voice_conn = None
        self.current_voice_addr = None
        self.video_call_active = False
        self.current_video_conn = None
        self.video_send_socket = None
        self.video_recv_socket = None
        self.current_call_peer = None

        # Initialize all sockets
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.bind(("", BROADCAST_PORT))

        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.video_socket.bind(("", VIDEO_PORT))
        self.video_socket.listen(5)

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", CONTROL_PORT))

        self.text_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.text_socket.bind(("", TEXT_PORT))

        self.voice_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.voice_socket.bind(("", VOICE_PORT))
        self.voice_socket.listen(1)

        self.audio = pyaudio.PyAudio()

    def set_call_end_callback(self, callback):
        """Sets callback for handling call end events."""
        self.call_end_callback = callback

    # Callback setters
    def set_video_call_callback(self, callback):
        """Sets callback for handling video call requests."""
        self.video_call_callback = callback

    def set_voice_message_callback(self, callback):
        """Set callback function for incoming voice messages."""
        self.voice_message_callback = callback

    def set_text_message_callback(self, callback):
        """Set callback function for incoming text messages."""
        self.text_message_callback = callback

    # Peer Discovery Methods
    def broadcast_presence(self):
        """Broadcasts presence to network."""
        while self.running:
            try:
                message = pickle.dumps({"username": self.username})
                self.broadcast_socket.sendto(message, ("255.255.255.255", BROADCAST_PORT))
            except Exception as e:
                print(f"[ERROR] Broadcast failed: {e}")
            threading.Event().wait(5)

    def listen_for_peers(self):
        """Listens for other peers on the network."""
        while self.running:
            try:
                data, addr = self.broadcast_socket.recvfrom(BUFFER_SIZE)
                peer_info = pickle.loads(data)
                if addr[0] != socket.gethostbyname(socket.gethostname()):
                    self.peers.add((peer_info["username"], addr[0]))
            except Exception as e:
                print(f"[ERROR] Peer discovery failed: {e}")

    # Control Communication Methods
    def send_control_message(self, message, addr):
        """Sends control message to specified address."""
        try:
            self.control_socket.sendto(pickle.dumps(message), addr)
        except Exception as e:
            print(f"[ERROR] Failed to send control message: {e}")

    def listen_for_control_messages(self):
        """Listens for control messages."""
        while self.running:
            try:
                data, addr = self.control_socket.recvfrom(BUFFER_SIZE)
                message = pickle.loads(data)
                self.handle_control_message(message, addr)
            except Exception as e:
                print(f"[ERROR] Control message handling failed: {e}")

    def handle_control_message(self, message, addr):
        """Handles received control messages."""
        try:
            if message.get("type") == "call_request":
                print(f"Incoming call request from {addr[0]}")
                if self.video_call_callback:
                    self.video_call_callback(addr[0])
            elif message.get("type") == "call_accept":
                threading.Thread(target=self.establish_video_call, args=(addr[0],), daemon=True).start()
            elif message.get("type") == "call_decline":
                print(f"Call request to {addr[0]} was declined")
            elif message.get("type") == "call_end":
                print(f"Call ended by {addr[0]}")
                self.video_call_active = False
                cv2.destroyAllWindows()
                # Notify frontend about call end
                if self.call_end_callback:
                    self.call_end_callback(addr[0])
                # Close any active video connections
                if hasattr(self, 'video_socket'):
                    try:
                        self.video_socket.close()
                    except:
                        pass
        except Exception as e:
            print(f"[ERROR] Failed to handle control message: {e}")

    # Video Call Methods
    def start_video_call(self, recipient_ip):
        """Initiates a video call with specified IP."""
        try:
            self.send_control_message({"type": "call_request"}, (recipient_ip, CONTROL_PORT))
        except Exception as e:
            print(f"[ERROR] Could not start video call: {e}")

    def accept_video_call(self, caller_ip):
        """Accepts an incoming video call."""
        try:
            self.send_control_message({"type": "call_accept"}, (caller_ip, CONTROL_PORT))
            threading.Thread(target=self.establish_video_call, args=(caller_ip,), daemon=True).start()
        except Exception as e:
            print(f"[ERROR] Could not accept video call: {e}")

    def reject_video_call(self, caller_ip):
        """Rejects an incoming video call."""
        try:
            self.send_control_message({"type": "call_decline"}, (caller_ip, CONTROL_PORT))
        except Exception as e:
            print(f"[ERROR] Could not reject video call: {e}")

    def end_video_call(self):
        """Ends the current video call and cleans up resources."""
        try:
            self.video_call_active = False

            # Close video connections
            if self.video_send_socket:
                try:
                    self.video_send_socket.close()
                except:
                    pass
                self.video_send_socket = None

            if self.video_recv_socket:
                try:
                    self.video_recv_socket.close()
                except:
                    pass
                self.video_recv_socket = None

            # Close any active video windows
            cv2.destroyAllWindows()

            # Reset current call peer
            self.current_call_peer = None

        except Exception as e:
            print(f"[ERROR] Error ending video call: {e}")

    def establish_video_call(self, recipient_ip):
        """Establishes video call connection."""
        try:
            self.video_call_active = True
            send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            send_socket.connect((recipient_ip, VIDEO_PORT))
            threading.Thread(target=self.send_video_stream, args=(send_socket,), daemon=True).start()

            recv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            recv_socket.bind(("", VIDEO_PORT + 1))
            recv_socket.listen(1)
            conn, addr = recv_socket.accept()
            threading.Thread(target=self.receive_video_stream, args=(conn,), daemon=True).start()
        except Exception as e:
            print(f"[ERROR] Could not establish video call: {e}")
            self.video_call_active = False

    def listen_for_video_calls(self):
        """Listens for incoming video calls."""
        while self.running:
            try:
                conn, addr = self.video_socket.accept()
                if self.video_call_active:
                    threading.Thread(target=self.receive_video_stream, args=(conn,), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Video call listener failed: {e}")

    def send_video_stream(self, conn):
        """Sends video stream to connected peer."""
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        try:
            while self.running and self.video_call_active and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                _, jpeg_frame = cv2.imencode('.jpg', frame)
                video_data = pickle.dumps(jpeg_frame)

                conn.sendall(struct.pack('>I', len(video_data)))
                conn.sendall(video_data)

                audio_data = stream.read(CHUNK)
                conn.sendall(struct.pack('>I', len(audio_data)))
                conn.sendall(audio_data)
        except Exception as e:
            print(f"[ERROR] Video stream sending failed: {e}")
        finally:
            cap.release()
            stream.stop_stream()
            stream.close()
            conn.close()

    def receive_video_stream(self, conn):
        """Receives and displays video stream from connected peer."""
        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

        try:
            while self.running and self.video_call_active:
                data = conn.recv(4)
                if not data:
                    break
                video_length = struct.unpack('>I', data)[0]
                video_data = self.receive_all(conn, video_length)

                if video_data:
                    frame = pickle.loads(video_data)
                    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                    if frame is not None:
                        cv2.imshow('Remote Video', frame)

                data = conn.recv(4)
                if not data:
                    break
                audio_length = struct.unpack('>I', data)[0]
                audio_data = self.receive_all(conn, audio_length)

                if audio_data:
                    stream.write(audio_data)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except Exception as e:
            print(f"[ERROR] Video stream receiving failed: {e}")
        finally:
            conn.close()
            cv2.destroyAllWindows()
            stream.stop_stream()
            stream.close()

    # Voice Message Methods
    def start_recording(self):
        """Starts voice recording."""
        self.is_recording = True
        self.audio_frames = []
        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        while self.is_recording:
            try:
                data = stream.read(CHUNK)
                self.audio_frames.append(data)
            except Exception as e:
                print(f"[ERROR] Recording failed: {e}")
                break

        stream.stop_stream()
        stream.close()

    def stop_recording(self):
        """Stops voice recording."""
        self.is_recording = False

    def send_voice_recording(self, recipient_ip):
        """Sends recorded voice message to specified IP."""
        if not self.audio_frames:
            print("[ERROR] No recorded audio to send.")
            return

        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(10)
            conn.connect((recipient_ip, VOICE_PORT))

            for frame in self.audio_frames:
                conn.sendall(frame)
            conn.close()
            print("[INFO] Voice recording sent successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to send voice recording: {e}")

    def listen_for_voice_messages(self):
        """Listens for incoming voice messages."""
        while self.running:
            try:
                conn, addr = self.voice_socket.accept()
                print(f"[INFO] Receiving voice message from {addr[0]}...")

                self.current_voice_conn = conn
                self.current_voice_addr = addr

                if self.voice_message_callback:
                    self.voice_message_callback(addr[0])
                else:
                    self.play_voice_message(conn)
            except Exception as e:
                print(f"[ERROR] Voice message reception failed: {e}")

    def play_voice_message(self, conn):
        """Plays received voice message."""
        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        try:
            while self.running:
                data = conn.recv(CHUNK)
                if not data:
                    break
                stream.write(data)
        finally:
            stream.stop_stream()
            stream.close()
            conn.close()

    def accept_voice_message(self):
        """Accepts and plays current voice message."""
        if hasattr(self, 'current_voice_conn'):
            self.play_voice_message(self.current_voice_conn)
            delattr(self, 'current_voice_conn')
            delattr(self, 'current_voice_addr')

    def reject_voice_message(self):
        """Rejects current voice message."""
        if hasattr(self, 'current_voice_conn'):
            self.current_voice_conn.close()
            delattr(self, 'current_voice_conn')
            delattr(self, 'current_voice_addr')

    # Text Message Methods
    def send_text_message(self, message, addr):
        """Sends text message to specified address."""
        try:
            message_with_sender = f"{self.username}: {message}"
            self.text_socket.sendto(message_with_sender.encode(), addr)

            # Save message to history
            self.save_file(self.username, message)

            # Store message if recipient window isn't open
            if addr[0] not in self.active_windows:
                self.store_message(addr[0], message_with_sender)
        except Exception as e:
            print(f"[ERROR] Text message sending failed: {e}")

    def listen_for_text_messages(self):
        """Listens for incoming text messages."""
        while self.running:
            try:
                data, addr = self.text_socket.recvfrom(BUFFER_SIZE)
                message = data.decode()

                # If sender's window is open, deliver immediately
                if addr[0] in self.active_windows:
                    if self.text_message_callback:
                        self.text_message_callback(message, addr)
                else:
                    # Store message for later delivery
                    self.store_message(addr[0], message)

                # Always save to file
                self.save_file(addr[0], message)
            except Exception as e:
                print(f"[ERROR] Text message reception failed: {e}")

    def handle_text_message(self, message_data, addr):
        """Handles incoming text messages."""
        try:
            if message_data["type"] == "text_message":
                sender_username = message_data["username"]
                message = message_data["message"]
                print(f"[{sender_username}]: {message}")
                if self.text_message_callback:
                    self.text_message_callback(sender_username, message)
                self.save_file(sender_username, message)
        except Exception as e:
            print(f"[ERROR] Text message handling failed: {e}")

    def save_file(self, sender, message):
        """Saves all text messages between sender and receiver in a Chat.txt file on the PC desktop."""
        try:
            desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
            file_path = os.path.join(desktop_path, 'Chat.txt')
            with open(file_path, 'a') as f:
                f.write(f"{sender}: {message}\n")
        except Exception as e:
            print(f"[ERROR] Saving chat to file failed: {e}")

    # Utility Methods
    def receive_all(self, conn, length):
        """Receives all data of specified length from connection."""
        data = b""
        while len(data) < length:
            packet = conn.recv(min(BUFFER_SIZE, length - len(data)))
            if not packet:
                return None
            data += packet
        return data

    def stop(self):
        """Stops all peer activities and closes connections."""
        self.running = False
        try:
            # Close all sockets
            self.broadcast_socket.close()
            self.video_socket.close()
            self.control_socket.close()
            self.text_socket.close()
            self.voice_socket.close()

            # Clean up audio
            self.audio.terminate()

            # Close any OpenCV windows
            cv2.destroyAllWindows()

            print("[INFO] Peer stopped successfully")
        except Exception as e:
            print(f"[ERROR] Error during peer shutdown: {e}")

if __name__ == "__main__":
    peer = Peer()
    threading.Thread(target=peer.broadcast_presence, daemon=True).start()
    threading.Thread(target=peer.listen_for_peers, daemon=True).start()
    threading.Thread(target=peer.listen_for_video_calls, daemon=True).start()
    threading.Thread(target=peer.listen_for_control_messages, daemon=True).start()
    threading.Thread(target=peer.listen_for_text_messages, daemon=True).start()
    threading.Thread(target=peer.listen_for_voice_messages, daemon=True).start()

    def video_call_request_handler(ip):
        print(f"Incoming video call from {ip}. Accept? (yes/no)")
        response = input().strip().lower()
        if response == "yes":
            peer.accept_video_call(ip)
        else:
            peer.reject_video_call(ip)

    peer.set_video_call_callback(video_call_request_handler)
    print("Peer started and ready for video calls.")

    try:
        while True:
            command = input("Enter command (call <ip>/exit): ").strip()
            if command.startswith("call"):
                _, ip = command.split()
                peer.start_video_call(ip)
            elif command == "exit":
                break
    finally:
        peer.stop()
        print("Peer stopped.")

    print("Peer started. Use the following options:")

    while True:
        print("\nOptions:")
        print("1. List peers")
        print("2. Start video call")
        print("3. Send text message")
        print("4. Start voice recording")
        print("5. Stop voice recording")
        print("6. Send voice recording")
        print("7. Exit")

        choice = input("Enter choice: ")

        if choice == "1":
            print("Discovered peers:")
            for username, ip in peer.peers:
                print(f"- {username} ({ip})")
        elif choice == "2":
            recipient_ip = input("Enter recipient IP: ")
            peer.start_video_call(recipient_ip)
        elif choice == "3":
            recipient_ip = input("Enter recipient IP: ")
            message = input("Enter your message: ")
            peer.send_text_message(message, (recipient_ip, TEXT_PORT))
        elif choice == "4":
            peer.start_recording()
        elif choice == "5":
            peer.stop_recording()
        elif choice == "6":
            recipient_ip = input("Enter recipient IP: ")
            peer.send_voice_recording(recipient_ip)
        elif choice == "7":
            peer.stop()
            print("Peer stopped.")
            break
        else:
            print("Invalid choice. Pleasetryagain.")