import cv2
import socket
import threading
import pickle
import struct
import tkinter as tk
from tkinter import messagebox
from ttkthemes import ThemedTk
import ttkbootstrap as ttkb
from working_backend import Peer
import os
from datetime import datetime


class PeerFrontend:
    def __init__(self, peer):
        self.peer = peer
        self.is_recording = False
        self.record_thread = None
        self.video_call_active = False
        self.last_saved_position = 1.0
        self.chat_windows = {}  # Track open chat windows
        self.message_queues = {}  # Dictionary to store message queues for each peer

        # Main Window
        self.root = ttkb.Window(themename="darkly")
        self.root.title("P2P Communication")
        self.root.geometry("400x300")

        # Peers List
        self.peers_frame = ttkb.Labelframe(self.root, text="Peers")
        self.peers_frame.pack(fill="both", padx=10, pady=10)

        self.peers_list = ttkb.Treeview(self.peers_frame, columns=("Peer", "IP"), show="headings")
        self.peers_list.heading("Peer", text="Peer Name")
        self.peers_list.heading("IP", text="IP Address")
        self.peers_list.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.peers_list.bind("<Double-1>", self.open_peer_window)

        self.refresh_button = ttkb.Button(self.peers_frame, text="Refresh Peers", command=self.refresh_peers)
        self.refresh_button.pack(side="right", padx=5, pady=5)

        # Start peer discovery thread
        threading.Thread(target=self.update_peer_list, daemon=True).start()

    def refresh_peers(self):
        self.update_peer_list()

    def update_peer_list(self):
        self.peers_list.delete(*self.peers_list.get_children())
        for username, ip in self.peer.peers:
            self.peers_list.insert("", "end", values=(username, ip))

    def open_peer_window(self, event):
        selected_item = self.peers_list.focus()
        if not selected_item:
            return
        peer_name, peer_ip = self.peers_list.item(selected_item, "values")

        # Check if window already exists
        if peer_ip in self.chat_windows:
            self.chat_windows[peer_ip].window.lift()
            return

        # Create new window and store reference
        window = PeerWindow(self.peer, peer_name, peer_ip, self)
        self.chat_windows[peer_ip] = window

        # Register window as active in peer
        self.peer.add_active_window(peer_ip)

        # Get any stored messages for this peer
        stored_messages = self.peer.get_unread_messages(peer_ip)
        for message in stored_messages:
            window.display_message(message)

    def run(self):
        self.root.mainloop()


class PeerWindow:
    def __init__(self, peer, peer_name, peer_ip, frontend):
        self.peer = peer
        self.peer_name = peer_name
        self.peer_ip = peer_ip
        self.frontend = frontend
        self.is_recording = False
        self.record_thread = None
        self.video_call_active = False
        self.last_saved_position = 1.0

        # Peer Window
        self.window = ttkb.Toplevel()
        self.window.title(f"Chat with {peer_name}")
        self.window.geometry("800x600")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # Peer Details
        self.details_frame = ttkb.Labelframe(self.window, text="Peer Details")
        self.details_frame.pack(fill="x", padx=10, pady=10)

        self.details_label = ttkb.Label(self.details_frame, text=f"Name: {peer_name}\nIP: {peer_ip}")
        self.details_label.pack(padx=5, pady=5)

        # Message Display Area
        self.message_display_frame = ttkb.Labelframe(self.window, text="Messages")
        self.message_display_frame.pack(fill="both", padx=10, pady=10)

        self.message_display = tk.Text(self.message_display_frame, height=10, state='disabled')
        self.message_display.pack(fill="both", expand=True, padx=5, pady=5)

        # Save History Button
        self.save_history_button = ttkb.Button(self.window, text="Save History", command=self.save_history)
        self.save_history_button.pack(side="bottom", pady=10)

        # Recording Management
        self.recording_frame = ttkb.Labelframe(self.window, text="Voice Recording")
        self.recording_frame.pack(fill="both", padx=10, pady=10)

        self.record_button = ttkb.Button(self.recording_frame, text="Start Recording", command=self.start_recording)
        self.record_button.pack(side="left", padx=5, pady=5)

        self.stop_record_button = ttkb.Button(self.recording_frame, text="Stop Recording", command=self.stop_recording)
        self.stop_record_button.pack(side="left", padx=5, pady=5)

        self.send_button = ttkb.Button(self.recording_frame, text="Send Recording", command=self.send_recording)
        self.send_button.pack(side="left", padx=5, pady=5)

        # Text Messaging
        self.text_frame = ttkb.Labelframe(self.window, text="Text Messaging")
        self.text_frame.pack(fill="both", padx=10, pady=10)

        self.message_entry = ttkb.Entry(self.text_frame)
        self.message_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.send_text_button = ttkb.Button(self.text_frame, text="Send Message", command=self.send_text_message)
        self.send_text_button.pack(side="right", padx=5, pady=5)

        # Video Call
        self.video_frame = ttkb.Labelframe(self.window, text="Video Call")
        self.video_frame.pack(fill="both", padx=10, pady=10)

        self.call_button = ttkb.Button(self.video_frame, text="Start Video Call", command=self.start_video_call)
        self.call_button.pack(side="left", padx=5, pady=5)

        self.end_call_button = ttkb.Button(self.video_frame, text="End Call", command=self.end_video_call,
                                           state='disabled')
        self.end_call_button.pack(side="left", padx=5, pady=5)

        # Attach callbacks
        self.peer.set_text_message_callback(self.handle_text_message)
        self.peer.set_video_call_callback(self.handle_video_call_request)
        self.peer.set_voice_message_callback(self.handle_voice_message)

    def on_close(self):
        """Handle window closing."""
        # Remove window reference from frontend
        if self.peer_ip in self.frontend.chat_windows:
            del self.frontend.chat_windows[self.peer_ip]
        # Remove from active windows in peer
        self.peer.remove_active_window(self.peer_ip)
        self.window.destroy()

    def handle_text_message(self, message, addr):
        """Handle incoming text messages."""
        if addr[0] == self.peer_ip:
            self.display_message(message)
        else:
            # If message is from another peer, store it
            if addr[0] not in self.frontend.chat_windows:
                self.peer.store_message(addr[0], message)
                # Show notification
                messagebox.showinfo("New Message",
                                    f"You have a new message from {addr[0]}. Open chat to view.")
            else:
                # If window exists, display message
                self.frontend.chat_windows[addr[0]].display_message(message)

    # ... [All other existing methods remain the same] ...
    def start_recording(self):
        if self.is_recording:
            messagebox.showwarning("Already Recording", "Recording is already in progress.")
            return
        try:
            self.is_recording = True
            self.record_thread = threading.Thread(target=self.peer.start_recording)
            self.record_thread.start()
            messagebox.showinfo("Recording", "Recording started.")
            self.display_message("Recording started...")
            self.record_button.config(state='disabled')
            self.stop_record_button.config(state='normal')
        except Exception as e:
            self.is_recording = False
            messagebox.showerror("Recording Error", f"Error starting recording: {e}")

    def stop_recording(self):
        if not self.is_recording:
            messagebox.showwarning("Not Recording", "No recording is currently in progress.")
            return
        try:
            self.peer.stop_recording()
            if self.record_thread:
                self.record_thread.join()
            self.is_recording = False
            messagebox.showinfo("Recording", "Recording stopped.")
            self.display_message("Recording stopped.")
            self.record_button.config(state='normal')
            self.stop_record_button.config(state='disabled')
        except Exception as e:
            messagebox.showerror("Recording Error", f"Error stopping recording: {e}")

    def send_recording(self):
        if self.is_recording:
            messagebox.showwarning("Stop Recording", "Please stop the recording before sending.")
            return
        try:
            self.peer.send_voice_recording(self.peer_ip)
            messagebox.showinfo("Recording", f"Recording sent to {self.peer_ip}.")
            self.display_message(f"Voice message sent to {self.peer_ip}")
        except Exception as e:
            messagebox.showerror("Recording Error", f"Failed to send recording: {e}")

    def handle_voice_message(self, sender_ip):
        def on_dialog_response():
            dialog.destroy()
            if response.get():
                self.peer.accept_voice_message()
                self.display_message(f"Playing voice message from {sender_ip}")
            else:
                self.peer.reject_voice_message()
                self.display_message(f"Rejected voice message from {sender_ip}")

        dialog = ttkb.Toplevel(self.window)
        dialog.title("Incoming Voice Message")
        dialog.geometry("300x150")
        dialog.transient(self.window)
        dialog.grab_set()

        label = ttkb.Label(dialog, text=f"New voice message from {sender_ip}\nDo you want to play it?")
        label.pack(pady=20)

        response = tk.BooleanVar()
        button_frame = ttkb.Frame(dialog)
        button_frame.pack(pady=10)

        play_btn = ttkb.Button(button_frame, text="Play",
                               command=lambda: [response.set(True), on_dialog_response()])
        play_btn.pack(side="left", padx=10)

        reject_btn = ttkb.Button(button_frame, text="Reject",
                                 command=lambda: [response.set(False), on_dialog_response()])
        reject_btn.pack(side="left", padx=10)

        dialog.lift()
        dialog.focus_force()

    def send_text_message(self):
        message = self.message_entry.get()
        if not message:
            messagebox.showwarning("Enter Message", "Please enter a message.")
            return
        self.peer.send_text_message(message, (self.peer_ip, 5007))
        self.display_message(f"You: {message}")
        self.message_entry.delete(0, "end")

    def start_video_call(self):
        if self.video_call_active:
            messagebox.showwarning("Call in Progress", "You are already in a video call.")
            return

        self.peer.start_video_call(self.peer_ip)
        self.display_message(f"Calling {self.peer_ip}...")

    def handle_video_call_request(self, caller_ip):
        def on_dialog_response():
            dialog.destroy()
            if response.get():
                self.accept_video_call(caller_ip)
            else:
                self.reject_video_call(caller_ip)

        dialog = ttkb.Toplevel(self.window)
        dialog.title("Incoming Video Call")
        dialog.geometry("300x150")
        dialog.transient(self.window)
        dialog.grab_set()

        label = ttkb.Label(dialog, text=f"Incoming video call from {caller_ip}")
        label.pack(pady=20)

        response = tk.BooleanVar()
        button_frame = ttkb.Frame(dialog)
        button_frame.pack(pady=10)

        accept_btn = ttkb.Button(button_frame, text="Accept",
                                 command=lambda: [response.set(True), on_dialog_response()])
        accept_btn.pack(side="left", padx=10)

        reject_btn = ttkb.Button(button_frame, text="Reject",
                                 command=lambda: [response.set(False), on_dialog_response()])
        reject_btn.pack(side="left", padx=10)

        dialog.lift()
        dialog.focus_force()

    def accept_video_call(self, caller_ip):
        self.video_call_active = True
        self.call_button.config(state='disabled')
        self.end_call_button.config(state='normal')
        self.display_message(f"Video call accepted with {caller_ip}")

        threading.Thread(target=self.peer.accept_video_call,
                         args=(caller_ip,),
                         daemon=True).start()

    def reject_video_call(self, caller_ip):
        self.peer.reject_video_call(caller_ip)
        self.display_message(f"Video call rejected from {caller_ip}")

    def end_video_call(self):
        if not self.video_call_active:
            return

        self.video_call_active = False
        self.call_button.config(state='normal')
        self.end_call_button.config(state='disabled')

        cv2.destroyAllWindows()

        if hasattr(self.peer, 'video_call_active'):
            self.peer.video_call_active = False

        self.display_message("Video call ended")

    def save_history(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        chat_file_path = os.path.join(desktop_path, f"Chat_{self.peer_name}_{self.peer_ip}.txt")

        # Get new messages from the last saved position
        new_messages = self.message_display.get(f"{self.last_saved_position}", "end").strip()

        # Update last saved position
        self.last_saved_position = self.message_display.index("end-1c")

        if new_messages:
            with open(chat_file_path, "a") as file:
                file.write(new_messages + "\n")
            messagebox.showinfo("Save History", f"New chat history saved to {chat_file_path}")
        else:
            messagebox.showinfo("Save History", "No new messages to save.")

    def handle_text_message(self, message, addr):
        """Handle incoming text messages."""
        if addr[0] == self.peer_ip:
            self.display_message(message)
        else:
            # If message is from another peer, store it
            if addr[0] not in self.frontend.chat_windows:
                self.peer.store_message(addr[0], message)
                # Show notification
                messagebox.showinfo("New Message",
                    f"You have a new message from {addr[0]}. Open chat to view.")
            else:
                # If window exists, display message
                self.frontend.chat_windows[addr[0]].display_message(message)

    def display_message(self, message):
        if not self.message_display.winfo_exists():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.message_display.config(state='normal')
        self.message_display.insert(tk.END, f"[{timestamp}] {message}\n")
        self.message_display.config(state='disabled')
        self.message_display.see(tk.END)

if __name__ == "__main__":
    peer = Peer()
    frontend = PeerFrontend(peer)

    threading.Thread(target=peer.broadcast_presence, daemon=True).start()
    threading.Thread(target=peer.listen_for_peers, daemon=True).start()
    threading.Thread(target=peer.listen_for_video_calls, daemon=True).start()
    threading.Thread(target=peer.listen_for_control_messages, daemon=True).start()
    threading.Thread(target=peer.listen_for_text_messages, daemon=True).start()
    threading.Thread(target=peer.listen_for_voice_messages, daemon=True).start()

    frontend.run()