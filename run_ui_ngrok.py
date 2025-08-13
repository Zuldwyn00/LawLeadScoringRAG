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
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import smtplib
from email.message import EmailMessage

# Load environment variables from .env as early as possible so subprocesses inherit them
try:
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()
except Exception as _e:
    print(f"⚠️  Could not load .env automatically: {_e}")



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


def restart_ngrok_tunnel(ngrok_process, port, ngrok_path):
    """Restart the ngrok tunnel while keeping Streamlit running."""
    try:
        print("🔄 Restarting ngrok tunnel (2-hour session limit)...")
        
        # Close current tunnel
        if ngrok_process:
            ngrok_process.terminate()
            try:
                ngrok_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ngrok_process.kill()
            print("✅ Old tunnel closed")
        
        # Wait a moment before starting new tunnel
        time.sleep(2)
        
        # Start new tunnel
        return start_ngrok_tunnel(port, ngrok_path)
        
    except Exception as e:
        print(f"Error restarting ngrok tunnel: {e}")
        return None, None


def format_time_remaining(seconds):
    """Format seconds into a human-readable time string."""
    if seconds == float('inf'):
        return "∞"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def send_instance_email(ngrok_url: str) -> bool:
    """Send an email with the new instance link and password via Gmail SMTP.

    Args:
        ngrok_url (str): The public ngrok URL for the running instance.
 
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    # Read credentials and target from the environment
    user_email = os.getenv("USER_EMAIL")
    user_email_send = ['justin@o2law.com', 'hsevak@o2law.com']
    user_email_password = os.getenv("USER_EMAIL_PASSWORD")
    streamlit_password = os.getenv("STREAMLIT_PASSWORD")

    if not user_email or not user_email_password:
        print("⚠️  USER_EMAIL or USER_EMAIL_PASSWORD not set; skipping email notification.")
        return False

    subject = "LEAD SCORE - NEW INSTANCE"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    body = (
        "A new Lead Scoring UI instance is available.\n\n"
        f"URL: {ngrok_url}\n"
        f"Password: {streamlit_password}\n\n"
        f"Time Started: {timestamp}\n"
    )

    message = EmailMessage()
    message["From"] = user_email
    message["To"] = ", ".join(user_email_send)  # Join list into comma-separated string
    message["Subject"] = subject
    message.set_content(body)

    try:
        # Gmail SMTP settings
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user_email, user_email_password)
            smtp.send_message(message)
        print(f"✉️  Email notification sent to {', '.join(user_email_send)}")
        return True
    except Exception as exc:
        print(f"❌ Failed to send email notification: {exc}")
        return False


def main():
    """Launch the Streamlit UI with ngrok ephemeral tunnel."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Launch Lead Scoring UI with ngrok tunnel and automatic session management"
    )
    parser.add_argument(
        "--total-hours",
        type=float,
        default=float('inf'),
        help="Total hours to run the service (default: infinite). Use decimals for fractional hours (e.g., 1.5 for 90 minutes)"
    )
    args = parser.parse_args()
    
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
    port = 8080

    # Session and runtime management
    session_duration_hours = 6  # Restart tunnel every 6 hours (less aggressive)
    total_start_time = time.time()
    session_start_time = total_start_time
    
    total_runtime_str = format_time_remaining(args.total_hours * 3600) if args.total_hours != float('inf') else "∞"

    print("🚀 Starting Lead Scoring UI with ngrok tunnel...")
    print("📝 Features: Automatic tunnel restart every 2 hours for free ngrok accounts")
    print(f"⏱️  Total runtime: {total_runtime_str}")
    print(f"📱 Local Access:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print("\n🔄 Session Management:")
    print("   • Ngrok tunnel restarts automatically every 2 hours")
    print("   • Streamlit stays running during tunnel restarts")
    print("   • New public URL will be displayed after each restart")
    
    print("\nPress Ctrl+C to stop the server.")

    # Store processes for cleanup
    processes = []
    ngrok_process = None  # Initialize for cleanup function
    
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
        # Prepare environment for the Streamlit subprocess so the UI can render timers
        # based on the overall service start time, session (ngrok) duration, and total end time.
        env = os.environ.copy()
        env["SERVICE_START_EPOCH"] = str(int(total_start_time))
        env["SESSION_DURATION_SECONDS"] = str(int(session_duration_hours * 3600))
        if args.total_hours != float('inf'):
            total_end_epoch = int(total_start_time + (args.total_hours * 3600))
            env["TOTAL_END_EPOCH"] = str(total_end_epoch)
            env["TOTAL_HOURS"] = str(args.total_hours)
        else:
            env["TOTAL_END_EPOCH"] = "inf"
            env["TOTAL_HOURS"] = "inf"

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
            ],
            env=env,
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
            # Send email on initial creation
            send_instance_email(ngrok_url)
        else:
            print("⚠️  Running without ngrok tunnel (local access only)")
        
        # Keep the main process running with session management
        last_status_time = time.time()
        status_interval = 300  # Show status every 5 minutes
        
        while True:
            current_time = time.time()
            
            # Check total runtime limit
            total_elapsed_hours = (current_time - total_start_time) / 3600
            if total_elapsed_hours >= args.total_hours:
                print(f"\n⏰ Reached total runtime limit of {args.total_hours} hours")
                print("🛑 Shutting down gracefully...")
                break
            
            # Check session time for tunnel restart
            session_elapsed_hours = (current_time - session_start_time) / 3600
            if session_elapsed_hours >= session_duration_hours and ngrok_process:
                print(f"\n⏰ Session has been running for {session_duration_hours} hours")
                ngrok_process, ngrok_url = restart_ngrok_tunnel(ngrok_process, port, ngrok_path)
                session_start_time = current_time  # Reset session timer
                
                if ngrok_url:
                    print(f"🌍 New Public Access: {ngrok_url}")
                    print("✅ Tunnel restart complete\n")
                    # Send email on restart
                    send_instance_email(ngrok_url)
                else:
                    print("⚠️  Failed to restart tunnel - continuing with local access only\n")
            
            # Show periodic status updates
            if current_time - last_status_time >= status_interval:
                session_remaining = (session_duration_hours * 3600) - (current_time - session_start_time)
                total_remaining = (args.total_hours * 3600) - (current_time - total_start_time) if args.total_hours != float('inf') else float('inf')
                
                print(f"📊 Status: Session restart in {format_time_remaining(session_remaining)}, Total runtime remaining: {format_time_remaining(total_remaining)}")
                last_status_time = current_time
            
            # Check if Streamlit is still running
            if streamlit_process.poll() is not None:
                print("❌ Streamlit process stopped unexpectedly")
                break
            
            # Check if ngrok is still running (only if we expect it to be)
            if ngrok_process and ngrok_process.poll() is not None:
                print("⚠️  Ngrok process stopped unexpectedly - attempting restart...")
                ngrok_process, ngrok_url = restart_ngrok_tunnel(None, port, ngrok_path)
                session_start_time = current_time  # Reset session timer
                
                if ngrok_url:
                    print(f"🌍 Tunnel restarted: {ngrok_url}")
                    # Send email on unexpected restart as well
                    send_instance_email(ngrok_url)
                else:
                    print("❌ Failed to restart tunnel - continuing with local access only")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"Error starting UI: {e}")
        cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main() 