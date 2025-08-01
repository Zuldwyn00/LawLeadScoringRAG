#!/usr/bin/env python3
"""
Launch script for the Lead Scoring UI.

This script starts the Streamlit web interface for the lead scoring system.
"""

import subprocess
import sys
import socket
from pathlib import Path


def get_local_ip():
    """Get the local IP address for network access."""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"


def main():
    """Launch the Streamlit UI."""
    ui_file = Path(__file__).parent / "lead_scoring_ui.py"

    if not ui_file.exists():
        print(f"Error: UI file not found at {ui_file}")
        sys.exit(1)

    local_ip = get_local_ip()
    port = 3000

    print("Starting Lead Scoring UI...")
    print(f"🌐 Network Access:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print("Press Ctrl+C to stop the server.")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ui_file),
                "--server.address",
                "0.0.0.0",
                "--server.port",
                str(port),
                "--browser.serverAddress",
                local_ip,
                "--browser.serverPort",
                str(port),
            ]
        )
    except KeyboardInterrupt:
        print("\nShutting down UI server...")
    except Exception as e:
        print(f"Error starting UI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
