"""
Modal Dialogs and Windows

This module contains modal dialog windows for displaying detailed information
such as AI analysis results and original lead descriptions.
"""

import customtkinter as ctk
import threading
import time
from pathlib import Path
import logging
from .styles import COLORS, FONTS


# ─── ANALYSIS DIALOG ────────────────────────────────────────────────────────────
class AnalysisDialog(ctk.CTkToplevel):
    """Modal dialog for displaying AI analysis results."""

    def __init__(self, parent, lead: dict):
        super().__init__(parent)

        self.lead = lead
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

    def setup_window(self):
        """Configure the dialog window."""
        self.title(f"AI Analysis - Score: {self.lead['score']}/100")
        self.geometry("900x700")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color=COLORS["primary_black"])
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="AI Analysis & Recommendation",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        # Score info
        score_info = f"Score: {self.lead['score']}/100 | Confidence: {self.lead.get('confidence', 50)}/100"
        score_label = ctk.CTkLabel(
            title_frame,
            text=score_info,
            font=FONTS()["heading"],
            text_color=COLORS["text_gray"],
        )
        score_label.grid(row=1, column=0, pady=(0, 10))

        # Analysis content
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self.analysis_text = ctk.CTkTextbox(
            content_frame,
            font=FONTS()["body"],
            fg_color=COLORS["secondary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
        )
        self.analysis_text.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.analysis_text.insert("1.0", self.lead["analysis"])
        self.analysis_text.configure(state="disabled")

        # Close button
        close_button = ctk.CTkButton(
            self,
            text="Close",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.destroy,
        )
        close_button.grid(row=2, column=0, pady=(0, 20))

    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()

        # Get parent window position and size
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Get dialog size
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")


# ─── DESCRIPTION DIALOG ─────────────────────────────────────────────────────────
class DescriptionDialog(ctk.CTkToplevel):
    """Modal dialog for displaying original lead descriptions."""

    def __init__(self, parent, lead: dict):
        super().__init__(parent)

        self.lead = lead
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

    def setup_window(self):
        """Configure the dialog window."""
        self.title("Original Lead Description")
        self.geometry("700x500")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color=COLORS["primary_black"])
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="Original Lead Description",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        # Timestamp info
        timestamp_label = ctk.CTkLabel(
            title_frame,
            text=f"Submitted: {self.lead['timestamp']}",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        timestamp_label.grid(row=1, column=0, pady=(0, 10))

        # Description content
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self.description_text = ctk.CTkTextbox(
            content_frame,
            font=FONTS()["body"],
            fg_color=COLORS["secondary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["accent_orange"],
            border_width=2,
            wrap="word",
        )
        self.description_text.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.description_text.insert("1.0", self.lead["description"])
        self.description_text.configure(state="disabled")

        # Close button
        close_button = ctk.CTkButton(
            self,
            text="Close",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.destroy,
        )
        close_button.grid(row=2, column=0, pady=(0, 20))

    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()

        # Get parent window position and size
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Get dialog size
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")


# ─── PASSWORD DIALOG ────────────────────────────────────────────────────────────
class PasswordDialog(ctk.CTkToplevel):
    """Modal dialog for password authentication."""

    def __init__(self, parent):
        super().__init__(parent)

        self.password_correct = False
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Focus on password entry
        self.password_entry.focus()

    def setup_window(self):
        """Configure the dialog window."""
        self.title("Authentication Required")
        self.geometry("400x250")
        self.configure(fg_color=COLORS["primary_black"])
        self.resizable(False, False)

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="🔐 Authentication Required",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=20)

        # Content frame
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_columnconfigure(0, weight=1)

        # Instructions
        instruction_label = ctk.CTkLabel(
            content_frame,
            text="Please enter the password to access the Lead Scoring System:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
            wraplength=350,
        )
        instruction_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Password entry
        self.password_entry = ctk.CTkEntry(
            content_frame,
            placeholder_text="Enter password...",
            show="*",
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["border_gray"],
            border_width=2,
        )
        self.password_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.password_entry.bind("<Return>", lambda e: self.check_password())

        # Error label (initially hidden)
        self.error_label = ctk.CTkLabel(
            content_frame, text="", font=FONTS()["small"], text_color="#ef4444"
        )
        self.error_label.grid(row=2, column=0, padx=20, pady=5)

        # Button frame
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Cancel button
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            font=FONTS()["button"],
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            border_color=COLORS["border_gray"],
            border_width=2,
            command=self.cancel,
        )
        cancel_button.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        # Login button
        login_button = ctk.CTkButton(
            button_frame,
            text="Login",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.check_password,
        )
        login_button.grid(row=0, column=1, padx=(10, 0), sticky="ew")

    def check_password(self):
        """Check if the entered password is correct."""
        import os

        correct_password = os.getenv("STREAMLIT_PASSWORD")
        entered_password = self.password_entry.get()

        if not correct_password:
            # No password required
            self.password_correct = True
            self.destroy()
            return

        if entered_password == correct_password:
            self.password_correct = True
            self.destroy()
        else:
            self.error_label.configure(text="❌ Incorrect password. Please try again.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus()

    def cancel(self):
        """Cancel authentication and close the application."""
        self.password_correct = False
        self.destroy()

    def center_window(self):
        """Center the dialog window on the screen."""
        self.update_idletasks()

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Get dialog dimensions
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")


# ─── LOG VIEWER DIALOG ──────────────────────────────────────────────────────
class LogViewerDialog(ctk.CTkToplevel):
    """Modal dialog for viewing filtered log files."""

    def __init__(self, parent, session_start_time=None):
        super().__init__(parent)

        self.session_start_time = session_start_time
        self.auto_refresh = False
        self.refresh_job = None
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Load initial log content
        self.refresh_logs()

        # Start auto-refresh since it's enabled by default
        self.auto_refresh = True
        self.schedule_refresh()

    def setup_window(self):
        """Configure the dialog window."""
        self.title("📋 Current Lead Scoring Logs")
        self.geometry("1000x600")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color=COLORS["primary_black"])
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="📋 Current Lead Scoring Logs",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        # Session info
        if self.session_start_time:
            session_info = f"Lead scoring started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            session_label = ctk.CTkLabel(
                title_frame,
                text=session_info,
                font=FONTS()["body"],
                text_color=COLORS["text_gray"],
            )
            session_label.grid(row=1, column=0, pady=(0, 10))

        # Control frame
        control_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        control_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        control_frame.grid_columnconfigure(2, weight=1)

        # Refresh button
        refresh_button = ctk.CTkButton(
            control_frame,
            text="🔄 Refresh",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.refresh_logs,
            width=100,
        )
        refresh_button.grid(row=0, column=0, padx=10, pady=10)

        # Auto-refresh toggle (enabled by default)
        self.auto_refresh_var = ctk.BooleanVar(value=True)
        auto_refresh_checkbox = ctk.CTkCheckBox(
            control_frame,
            text="Auto-refresh (5s)",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
            variable=self.auto_refresh_var,
            command=self.toggle_auto_refresh,
        )
        auto_refresh_checkbox.grid(row=0, column=1, padx=10, pady=10)

        # Log count label
        self.log_count_label = ctk.CTkLabel(
            control_frame,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
        )
        self.log_count_label.grid(row=0, column=3, padx=10, pady=10)

        # Log content frame
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # Log text display
        self.log_text = ctk.CTkTextbox(
            content_frame,
            font=ctk.CTkFont(family="Courier New", size=11),  # Monospace font for logs
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="none",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        # Close button
        close_button = ctk.CTkButton(
            self,
            text="Close",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.on_close,
        )
        close_button.grid(row=3, column=0, pady=(0, 20))

    def get_log_files(self):
        """Get list of available log files."""
        log_files = []

        # Only show the main log file (pdf_scraper.log) for session filtering
        project_root = Path(__file__).resolve().parents[1]
        main_log = project_root / "logs" / "pdf_scraper.log"
        if main_log.exists():
            log_files.append(("Current Session", main_log))

        return log_files

    def filter_logs_by_time(self, log_content, start_time):
        """Filter log entries to only show those after the start time."""
        if not start_time:
            return log_content

        filtered_lines = []
        for line in log_content.split("\n"):
            if not line.strip():
                continue

            try:
                # Extract timestamp from log line (YYYY-MM-DD HH:MM:SS)
                if " - " in line:
                    timestamp_str = line.split(" - ")[0]
                    from datetime import datetime

                    log_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                    # Only include logs from this session
                    if log_time >= start_time:
                        filtered_lines.append(line)

            except (ValueError, IndexError):
                # If we can't parse the timestamp, include the line anyway
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def filter_logs_by_level(
        self, log_content: str, min_level: int = logging.INFO
    ) -> str:
        """
        Filter log entries to only include records at or above the given level.

        Preserves multi-line records by including continuation lines only when the
        preceding header line was included.

        Args:
            log_content (str): Raw log text as written by the logger.
            min_level (int): Minimum logging level to include (e.g., logging.INFO).

        Returns:
            str: Filtered log text containing only lines for included records.
        """
        level_name_to_value = {
            "NOTSET": logging.NOTSET,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        filtered_lines = []
        include_following_lines = False

        for line in log_content.split("\n"):
            if line.strip() == "":
                # keep blank lines if we're inside an included record for readability
                if include_following_lines:
                    filtered_lines.append(line)
                continue

            parts = line.split(" - ", 3)
            if len(parts) >= 3:
                level_name = parts[2].strip()
                level_value = level_name_to_value.get(level_name)
                if level_value is not None:
                    include_following_lines = level_value >= min_level
                    if include_following_lines:
                        filtered_lines.append(line)
                    # Skip header line if below threshold and do not include subsequent continuations
                    continue

            # Lines that don't parse as a header (likely continuation)
            if include_following_lines:
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def refresh_logs(self):
        """Refresh the log content."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")

        log_files = self.get_log_files()
        if not log_files:
            self.log_text.insert("1.0", "No log files found.")
            self.log_count_label.configure(text="No logs available")
            self.log_text.configure(state="disabled")
            return

        total_entries = 0

        for log_name, log_path in log_files:
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Filter by session time if provided
                if self.session_start_time:
                    content = self.filter_logs_by_time(content, self.session_start_time)

                # Always filter to show only INFO and above levels
                content = self.filter_logs_by_level(content, min_level=logging.INFO)

                if content.strip():
                    self.log_text.insert("end", f"\n{'='*80}\n")
                    self.log_text.insert("end", f"{log_name.upper()}\n")
                    self.log_text.insert("end", f"{'='*80}\n\n")
                    self.log_text.insert("end", content)
                    self.log_text.insert("end", "\n\n")

                    # Count entries
                    entries = len(
                        [
                            line
                            for line in content.split("\n")
                            if line.strip() and " - " in line
                        ]
                    )
                    total_entries += entries

            except Exception as e:
                self.log_text.insert("end", f"\nError reading {log_name}: {str(e)}\n")

        # Update count
        if self.session_start_time and total_entries == 0:
            self.log_count_label.configure(
                text="No logs yet - processing will start soon"
            )
            self.log_text.insert(
                "1.0",
                "🔄 Lead scoring is starting...\n\nLog entries will appear here as the AI processes your lead:\n• AI client initialization\n• Vector embeddings generation\n• Historical case searches\n• Tool calls for file analysis\n• Scoring iterations\n• Final jurisdiction adjustments\n\nEnable 'Auto-refresh' to see logs update in real-time!",
            )
        else:
            self.log_count_label.configure(text=f"{total_entries} log entries")

        # Scroll to bottom to show latest logs
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def toggle_auto_refresh(self):
        """Toggle auto-refresh functionality."""
        self.auto_refresh = self.auto_refresh_var.get()

        if self.auto_refresh:
            self.schedule_refresh()
        else:
            if self.refresh_job:
                self.after_cancel(self.refresh_job)
                self.refresh_job = None

    def schedule_refresh(self):
        """Schedule the next auto-refresh."""
        if self.auto_refresh:
            self.refresh_logs()
            self.refresh_job = self.after(
                5000, self.schedule_refresh
            )  # Refresh every 5 seconds

    def on_close(self):
        """Handle window close event."""
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
        self.destroy()

    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()

        # Get parent window position and size
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Get dialog size
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")
