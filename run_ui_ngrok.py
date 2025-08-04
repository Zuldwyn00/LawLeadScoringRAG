#!/usr/bin/env python3
"""
Launch script for the Lead Scoring UI with ngrok ephemeral tunnel.

This script starts the Streamlit web interface and creates an ngrok tunnel
using ephemeral domains for temporary testing purposes.
"""

import subprocess
import sys
import socket
import time
import json
import requests
from pathlib import Path
import threading
import signal
import os




def get_local_ip():
    """Get the local IP address for network access."""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"


def check_ngrok_installed():
    """Check if ngrok is installed and accessible."""
    # Common ngrok executable locations
    possible_paths = [
        "ngrok",  # If in PATH
        "ngrok.exe",  # Windows executable
        r"C:\Users\Justin\Desktop\ngrok.exe",  # User's specific path
        "./ngrok.exe",  # Current directory
        "./ngrok",  # Current directory
    ]
    
    for ngrok_path in possible_paths:
        try:
            result = subprocess.run([ngrok_path, "version"], capture_output=True, text=True)
            if result.returncode == 0:
                return ngrok_path
        except FileNotFoundError:
            continue
    
    return None


def get_ngrok_url(port):
    """Get the ngrok public URL for the given port."""
    try:
        # Try multiple times with increasing delays
        for attempt in range(5):  # More attempts
            try:
                # Get ngrok API info
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                if response.status_code == 200:
                    tunnels = response.json()["tunnels"]
                    print(f"Found {len(tunnels)} tunnel(s)")
                    for tunnel in tunnels:
                        print(f"  Tunnel: {tunnel['config']['addr']} -> {tunnel['public_url']}")
                        # Check for both formats: "localhost:3000" and "http://localhost:3000"
                        if (tunnel["config"]["addr"] == f"localhost:{port}" or 
                            tunnel["config"]["addr"] == f"http://localhost:{port}"):
                            return tunnel["public_url"]
                
                # If we get here, no matching tunnel found
                print(f"Attempt {attempt + 1}: No tunnel found for port {port}")
                
            except requests.exceptions.ConnectionError:
                print(f"Attempt {attempt + 1}: Cannot connect to ngrok API (port 4040)")
            except requests.exceptions.Timeout:
                print(f"Attempt {attempt + 1}: Timeout connecting to ngrok API")
            except Exception as e:
                print(f"Attempt {attempt + 1}: Error: {e}")
            
            # Wait before next attempt
            if attempt < 4:  # Don't wait after last attempt
                time.sleep(3)  # Longer wait
        
        return None
    except Exception as e:
        print(f"Error getting ngrok URL: {e}")
        return None


def start_ngrok_tunnel(port, ngrok_path):
    """Start ngrok tunnel for temporary testing."""
    try:
        print("🔗 Starting ngrok tunnel for temporary testing...")
        
        # Start ngrok with standard tunnel (works with free plan)
        # For stable URLs, use: --domain=your-reserved-domain.ngrok.io (requires paid plan)
        ngrok_process = subprocess.Popen(
            [ngrok_path, "http", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit longer for ngrok to start
        time.sleep(5)
        
        # Check if ngrok process is still running
        if ngrok_process.poll() is not None:
            # Process died, get error output
            stdout, stderr = ngrok_process.communicate()
            print(f"❌ Ngrok process failed to start:")
            if stderr:
                print(f"Error: {stderr}")
            if stdout:
                print(f"Output: {stdout}")
            return None, None
        
        # Try to get the URL
        ngrok_url = get_ngrok_url(port)
        
        if ngrok_url:
            print(f"🌐 Tunnel created: {ngrok_url}")
            return ngrok_process, ngrok_url
        else:
            print("❌ Failed to create tunnel")
            print("💡 Troubleshooting tips:")
            print("   - Make sure ngrok is installed and in PATH")
            print("   - Check if you've set your authtoken: ngrok config add-authtoken YOUR_TOKEN")
            print("   - Try running 'ngrok http 3000' manually to test")
            print("   - Check if port 4040 is available for ngrok API")
            
            # Show ngrok output for debugging
            stdout, stderr = ngrok_process.communicate()
            if stdout:
                print(f"Ngrok stdout: {stdout}")
            if stderr:
                print(f"Ngrok stderr: {stderr}")
                
            ngrok_process.terminate()
            return None, None
            
    except Exception as e:
        print(f"Error starting ngrok: {e}")
        return None, None


def main():
    """Launch the Streamlit UI with ngrok ephemeral tunnel."""
    ui_file = Path(__file__).parent / "lead_scoring_ui.py"

    if not ui_file.exists():
        print(f"Error: UI file not found at {ui_file}")
        sys.exit(1)

    # Check if ngrok is installed
    ngrok_path = check_ngrok_installed()
    if not ngrok_path:
        print("❌ ngrok is not found")
        print("Please install ngrok from https://ngrok.com/download")
        print("Or place ngrok.exe in the current directory")
        print("After installation, make sure to set your authtoken with:")
        print("ngrok config add-authtoken YOUR_TOKEN")
        sys.exit(1)
    
    print(f"✅ Found ngrok at: {ngrok_path}")

    local_ip = get_local_ip()
    port = 3000

    print("🚀 Starting Lead Scoring UI with ngrok tunnel...")
    print("📝 This is for TEMPORARY TESTING only - URL will change each time!")
    print(f"📱 Local Access:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print("\n🔄 To restart just Streamlit with code updates:")
    print("   1. Press Ctrl+C to stop Streamlit")
    print("   2. Run: python -m streamlit run lead_scoring_ui.py --server.address 0.0.0.0 --server.port 3000")
    print("   3. Ngrok URL will remain the same!")
    
    print("\nPress Ctrl+C to stop the server.")

    # Store processes for cleanup
    processes = []
    
    def cleanup(signum=None, frame=None):
        """Clean up processes on exit."""
        print("\n🛑 Shutting down servers...")
        
        # Terminate ngrok
        if ngrok_process:
            ngrok_process.terminate()
            print("✅ Tunnel closed")
        
        # Terminate any other processes
        for proc in processes:
            if proc.poll() is None:  # If still running
                proc.terminate()
        
        sys.exit(0)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # Start Streamlit FIRST
        print("🚀 Starting Streamlit server...")
        streamlit_process = subprocess.Popen(
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
        processes.append(streamlit_process)
        
        # Wait for Streamlit to start
        print("⏳ Waiting for Streamlit to start...")
        time.sleep(5)
        
        # Now start ngrok tunnel AFTER Streamlit is running
        print("🔗 Starting ngrok tunnel...")
        ngrok_process, ngrok_url = start_ngrok_tunnel(port, ngrok_path)
        
        if ngrok_url:
            print(f"🌍 Temporary Public Access: {ngrok_url}")
            print("\n" + "="*60)
            print("🎉 Your app is now accessible from anywhere!")
            print("Share the ngrok URL with others for temporary testing")
            print("⚠️  WARNING: This URL will change when you restart!")
            print("📝 Perfect for quick demos and temporary sharing")
            print("="*60 + "\n")
        else:
            print("⚠️  Running without ngrok tunnel (local access only)")
        
        # Keep the main process running
        while True:
            # Check if Streamlit is still running
            if streamlit_process.poll() is not None:
                print("❌ Streamlit process stopped unexpectedly")
                break
            
            # Check if ngrok is still running
            if ngrok_process and ngrok_process.poll() is not None:
                print("❌ Ngrok process stopped unexpectedly")
                break
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"Error starting UI: {e}")
        cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main() 