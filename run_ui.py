#!/usr/bin/env python3
"""
Launch script for the Lead Scoring UI.

This script starts the Streamlit web interface for the lead scoring system.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch the Streamlit UI."""
    ui_file = Path(__file__).parent / "lead_scoring_ui.py"
    
    if not ui_file.exists():
        print(f"Error: UI file not found at {ui_file}")
        sys.exit(1)
    
    print("Starting Lead Scoring UI...")
    print("The UI will open in your default web browser.")
    print("Press Ctrl+C to stop the server.")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(ui_file),
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.serverAddress", "localhost"
        ])
    except KeyboardInterrupt:
        print("\nShutting down UI server...")
    except Exception as e:
        print(f"Error starting UI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 