# P2P Communication System

## Project Overview

This project implements a Peer-to-Peer (P2P) communication system that enables direct communication between peers on a network. It supports:

- **Text Messaging**: Send and receive text messages between peers.
- **Voice Messaging**: Record and send voice messages.
- **Video Calls**: Initiate and receive video calls.
- **Peer Discovery**: Automatically discover peers on the network.
- **Chat History**: Save chat history to a file.

The system is designed using Python and leverages the following libraries:
- `cv2` (OpenCV)
- `socket`
- `threading`
- `pickle`
- `struct`
- `tkinter`
- `ttkthemes`
- `ttkbootstrap`

## Project Structure

- `working_backend.py`: Contains the `Peer` class, which handles all backend operations including network communication, message handling, and peer discovery.
- `main.py`: Contains the `PeerFrontend` and `PeerWindow` classes, which handle the user interface and integrate with the backend.

## Installation Guide

### Requirements

Make sure you have Python 3.6 or later installed.

### Step-by-Step Guide

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/p2p-communication-system.git
   cd p2p-communication-system
   ```

2. Install the required packages:
   ```bash
   pip install opencv-python ttkthemes ttkbootstrap
   ```

3. Run the application:
   ```bash
   python main.py
   ```

### Packages to Install

| Package       | Command                          |
|---------------|----------------------------------|
| `cv2`         | `pip install opencv-python`       |
| `ttkthemes`   | `pip install ttkthemes`           |
| `ttkbootstrap`| `pip install ttkbootstrap`        |

### Running the Application

After installing the dependencies, run the application using:
```bash
python main.py
```

## Features Explained

### 1. Peer Discovery
The application continuously scans the network for available peers and updates the list in real-time. This functionality is handled by the `update_peer_list` method in the `PeerFrontend` class and backend discovery methods in the `Peer` class.

### 2. Text Messaging
Double-click on a peer in the list to open a chat window. You can type messages in the entry field and send them by clicking the "Send Message" button or pressing Enter.

### 3. Voice Messaging
- **Start Recording**: Click the "Start Recording" button to begin recording a voice message.
- **Stop Recording**: Click the "Stop Recording" button to end the recording.
- **Send Recording**: Click the "Send Recording" button to send the voice message.

### 4. Video Calls
- **Start Call**: Click the "Start Video Call" button to initiate a call.
- **End Call**: Click the "End Call" button to terminate the call.

### 5. Chat History
Save the chat history to your desktop by clicking the "Save History" button. The file will be named with the peer's name and IP address.

## User Guide

### Starting the Application
1. Run the application using the command:
   ```bash
   python main.py
   ```
2. The main window will display the list of peers available on the network.

### Messaging and Calls
- **Text Messages**: Double-click a peer to open a chat window. Type your message and click "Send Message."
- **Voice Messages**: Use the recording buttons to send voice messages.
- **Video Calls**: Click "Start Video Call" to initiate a call, and "End Call" to terminate it.

### Saving Chat History
Click the "Save History" button in the chat window to save the conversation to a text file on your desktop.

## Troubleshooting

- Ensure all peers are on the same network.
- Check firewall settings if peers cannot discover each other.
- Use `pip list` to verify all required packages are installed.

## Contributions
Feel free to contribute by submitting issues, forks, or pull requests.

## License
This project is licensed under the MIT License.

---

✅ **Happy Communicating!** 🌐📱

