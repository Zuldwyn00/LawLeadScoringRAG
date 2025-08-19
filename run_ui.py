#!/usr/bin/env python3
"""
Launch script for the Lead Scoring Desktop GUI.

This script starts the customtkinter desktop interface for the lead scoring system.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_requirements():
    """Check if required packages are installed."""
    try:
        import customtkinter
        import tkinter
        print("✅ GUI dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing required dependencies: {e}")
        print("Please install requirements with: pip install -r requirements.txt")
        return False

def main():
    """Launch the desktop GUI application."""
    print("🚀 Starting Lead Scoring Desktop GUI...")
    
    # Check dependencies
    if not check_requirements():
        sys.exit(1)
    
    try:
        # Import and run the GUI application
        from ui.main_window import LeadScoringApp
        
        # Create and run the application
        app = LeadScoringApp()
        print("✅ GUI application started successfully")
        print("💡 Use the interface to score leads with AI analysis")
        print("📋 Click 'View Logs' to see real-time processing logs")
        print("Press Ctrl+C in terminal or close the window to exit")
        
        # Start the main event loop
        app.run()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down GUI application...")
    except ImportError as e:
        print(f"❌ Error importing GUI modules: {e}")
        print("Make sure all UI files are present in the ui/ directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
