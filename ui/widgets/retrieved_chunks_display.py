"""
Retrieved chunks display component for showing vectorDB search results.

This component displays the chunks that were retrieved and used to generate 
the lead scoring analysis, allowing users to see the underlying data.
"""

import customtkinter as ctk
from typing import List, Dict, Any
from pathlib import Path
from ..styles import COLORS, FONTS, get_frame_style


class RetrievedChunksDisplayFrame(ctk.CTkFrame):
    """
    Frame for displaying retrieved chunks from vector search that were used for lead analysis.
    """
    
    def __init__(self, parent):
        super().__init__(parent, **get_frame_style("secondary"))
        
        self.parent_window = parent
        self.is_expanded = False
        self.sidebar_width = 400  # Full width when expanded
        self.collapsed_width = 150  # Minimal width when collapsed
        self.width_change_handler = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the retrieved chunks display interface."""
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Set initial width for sidebar (start collapsed)
        self.configure(width=self.collapsed_width)
        
        # Header with toggle button
        self.header_frame = ctk.CTkFrame(self, **get_frame_style("transparent"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(10, 5))
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Title and toggle button container
        title_container = ctk.CTkFrame(self.header_frame, **get_frame_style("transparent"))
        title_container.grid(row=0, column=0, sticky="w")
        
        self.toggle_button = ctk.CTkButton(
            title_container,
            text="▶",
            font=FONTS()["button"],
            width=25,
            height=25,
            command=self._toggle_expansion,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            text_color=COLORS["text_white"]
        )
        self.toggle_button.pack(side="left", padx=(0, 5))
        
        self.chunks_title = ctk.CTkLabel(
            title_container,
            text="📄 Retrieved Chunks",
            font=FONTS()["heading"],
            text_color=COLORS["accent_orange"]
        )
        self.chunks_title.pack(side="left")
        
        self.chunks_count = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"]
        )
        self.chunks_count.grid(row=0, column=1, sticky="e", padx=(0, 5))
        
        # Set initial count
        self.chunks_count.configure(text="0 chunks")
        
        # Scrollable chunks area (initially hidden)
        self.chunks_scrollable = ctk.CTkScrollableFrame(
            self,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"]
        )
        self.chunks_scrollable.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chunks_scrollable.grid_columnconfigure(0, weight=1)
        
        # Start collapsed
        self.chunks_scrollable.grid_remove()
        self.is_expanded = False
        self.toggle_button.configure(text="▶")  # Show expand arrow initially
        self.grid_propagate(False)  # Start with minimal height
        
        # Initial empty state
        self._show_empty_state()
    
    def _show_empty_state(self):
        """Show empty state when no chunks."""
        empty_label = ctk.CTkLabel(
            self.chunks_scrollable,
            text="📝 Retrieved chunks will appear here after scoring a lead",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"]
        )
        empty_label.grid(row=0, column=0, pady=50)
    
    def clear(self):
        """Clear all chunks from the display."""
        for widget in self.chunks_scrollable.winfo_children():
            widget.destroy()
        
        self.chunks_count.configure(text="0 chunks")
        self._show_empty_state()
        
        # Collapse when clearing
        if self.is_expanded:
            self._toggle_expansion()
    
    def display_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Display retrieved chunks.
        
        Args:
            chunks (List[Dict]): List of retrieved chunk dictionaries with keys:
                - content: The text content of the chunk
                - metadata: Dict with source, page_range, score, etc.
        """
        # Clear existing chunks
        for widget in self.chunks_scrollable.winfo_children():
            widget.destroy()
        
        if not chunks:
            self._show_no_chunks()
            return
        
        # Update count
        self.chunks_count.configure(text=f"{len(chunks)} chunks")
        
        # Display each chunk
        for i, chunk in enumerate(chunks):
            self._create_chunk_card(chunk, i)
        
        # Auto-expand when new chunks are available
        self.auto_expand_on_chunks()
    
    def _show_no_chunks(self):
        """Show message when no chunks found."""
        self.chunks_count.configure(text="0 chunks")
        
        no_chunks_label = ctk.CTkLabel(
            self.chunks_scrollable,
            text="❌ No relevant chunks were retrieved.\nTry running the lead scoring analysis.",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
            justify="center"
        )
        no_chunks_label.grid(row=0, column=0, pady=50)
    
    def _create_chunk_card(self, chunk: Dict[str, Any], index: int):
        """
        Create a card for displaying a single retrieved chunk.
        
        Args:
            chunk (Dict): Chunk data with content and metadata
            index (int): Chunk index
        """
        card_frame = ctk.CTkFrame(
            self.chunks_scrollable,
            **get_frame_style("secondary"),
            border_width=1,
            border_color=COLORS["border_gray"]
        )
        card_frame.grid(row=index, column=0, sticky="ew", padx=5, pady=5)
        card_frame.grid_columnconfigure(0, weight=1)
        
        # Extract data from chunk
        content = chunk.get('content', chunk.get('text', ''))
        metadata = chunk.get('metadata', {})
        source = metadata.get('source', chunk.get('source', 'Unknown Source'))
        score = chunk.get('score', metadata.get('score', 0))
        
        
        # Try to get page range from various possible locations
        page_range = (
            metadata.get('page_range') or 
            chunk.get('page_range') or 
            metadata.get('pages') or 
            chunk.get('pages') or 
            "Unknown"
        )
        
        # Header with source and score
        header_frame = ctk.CTkFrame(card_frame, **get_frame_style("transparent"))
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Chunk number and source
        source_text = f"📄 Chunk {index + 1}: {Path(source).name}"
        source_label = ctk.CTkLabel(
            header_frame,
            text=source_text,
            font=FONTS()["subheading"],
            anchor="w",
            text_color=COLORS["text_white"]
        )
        source_label.grid(row=0, column=0, sticky="w")
        
        # Relevance score
        score_text = f"Relevance: {score:.3f}"
        score_label = ctk.CTkLabel(
            header_frame,
            text=score_text,
            font=FONTS()["small"],
            text_color=COLORS["accent_orange"],
            anchor="e"
        )
        score_label.grid(row=0, column=1, sticky="e")
        
        # Page range
        page_info = f"📑 Pages: {page_range}"
        page_label = ctk.CTkLabel(
            header_frame,
            text=page_info,
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
            anchor="w"
        )
        page_label.grid(row=1, column=0, columnspan=2, sticky="w")
        
        # Content preview
        content_preview = self._create_content_preview(content)
        
        # Ensure content preview is not empty
        if not content_preview or content_preview.strip() == "":
            content_preview = f"[No content available for chunk {index + 1}]"
            print(f"Warning: Empty content for chunk {index + 1}")
        
        content_textbox = ctk.CTkTextbox(
            card_frame,
            height=120,
            font=FONTS()["body"],
            wrap="word",
            fg_color=COLORS["tertiary_black"],
            border_color=COLORS["border_gray"],
            text_color=COLORS["text_white"],
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"]
        )
        content_textbox.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))
        content_textbox.insert("1.0", content_preview)
        content_textbox.configure(state="disabled")  # Read-only
    
    def _create_content_preview(self, text: str, max_length: int = 2000) -> str:
        """
        Create a preview of the content text.
        
        Args:
            text (str): Full text content
            max_length (int): Maximum preview length
            
        Returns:
            str: Truncated preview text
        """
        if not text:
            return "Content not available"
        
        # Clean up the text
        text = text.strip()
        
        if len(text) <= max_length:
            return text
        
        # Truncate and add ellipsis
        truncated = text[:max_length].rsplit(' ', 1)[0]
        return f"{truncated}..."
    
    def _toggle_expansion(self):
        """Toggle the expansion state of the chunks section."""
        self.is_expanded = not self.is_expanded
        
        if self.is_expanded:
            # Show chunks and update button
            self.chunks_scrollable.grid()
            self.toggle_button.configure(text="◀")
            self.configure(width=self.sidebar_width)  # Expand width
            # Allow the frame to expand to full height
            self.grid_propagate(True)  # Re-enable automatic height expansion
            # Notify parent of width change
            if self.width_change_handler:
                self.width_change_handler(True)
        else:
            # Hide chunks and update button
            self.chunks_scrollable.grid_remove()
            self.toggle_button.configure(text="▶")
            self.configure(width=self.collapsed_width)  # Collapse width
            # Force the frame to only take up the height it needs
            self.grid_propagate(False)  # Prevent automatic height expansion
            # Notify parent of width change
            if self.width_change_handler:
                self.width_change_handler(False)
    
    def set_width_change_handler(self, handler):
        """
        Set the callback handler for width changes.
        
        Args:
            handler: Function to call when width changes
        """
        self.width_change_handler = handler
    
    def auto_expand_on_chunks(self):
        """Automatically expand when chunks are available."""
        if not self.is_expanded:
            self._toggle_expansion()
    
    def jump_to_chunk(self, chunk_index: int):
        """
        Jump to and highlight a specific retrieved chunk.
        
        Args:
            chunk_index (int): 1-based index of the chunk to jump to
        """
        # Ensure chunks are expanded and visible
        if not self.is_expanded:
            self._toggle_expansion()
        
        # Give the UI time to expand and render completely
        self.after(200, lambda: self._perform_jump_to_chunk(chunk_index))
    
    def _perform_jump_to_chunk(self, chunk_index: int):
        """
        Perform the actual jump to chunk after UI is ready.
        
        Args:
            chunk_index (int): 1-based index of the chunk to jump to
        """
        # Convert to 0-based index
        zero_based_index = chunk_index - 1
        
        # Find the chunk card widget
        chunk_widgets = [w for w in self.chunks_scrollable.winfo_children() 
                        if isinstance(w, ctk.CTkFrame)]
        
        if 0 <= zero_based_index < len(chunk_widgets):
            target_widget = chunk_widgets[zero_based_index]
            
            # Clear previous highlights
            self._clear_chunk_highlights()
            
            # Highlight the target chunk
            self._highlight_chunk(target_widget, chunk_index)
            
            # Try multiple approaches to scroll to the widget
            self._scroll_to_widget(target_widget)
        else:
            print(f"Chunk index {chunk_index} out of range. Available chunks: {len(chunk_widgets)}")
    
    def _clear_chunk_highlights(self):
        """Clear all chunk highlights."""
        for widget in self.chunks_scrollable.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                widget.configure(border_width=1, border_color=COLORS["border_gray"])
    
    def _highlight_chunk(self, widget: ctk.CTkFrame, chunk_number: int):
        """
        Highlight a specific chunk widget.
        
        Args:
            widget: The chunk card widget to highlight
            chunk_number: The chunk number for logging
        """
        # Add orange border and slight glow effect
        widget.configure(
            border_width=3,
            border_color=COLORS["accent_orange"]
        )
        
        # Schedule removal of highlight after 3 seconds
        widget.after(3000, lambda: widget.configure(
            border_width=1,
            border_color=COLORS["border_gray"]
        ))
    
    def _scroll_to_widget(self, widget: ctk.CTkFrame):
        """
        Scroll the chunks view to show the specified widget.
        
        Args:
            widget: The widget to scroll to
        """
        try:
            # Force geometry update
            widget.update_idletasks()
            self.chunks_scrollable.update_idletasks()
            
            # Get the widget's position relative to the scrollable frame
            widget_y = widget.winfo_y()
            widget_height = widget.winfo_height()
            
            # Get the scrollable frame dimensions
            scrollable_height = self.chunks_scrollable.winfo_height()
            
            # Always try to scroll if widget is not at the top
            if widget_y > 0:
                try:
                    # Try to scroll the widget into view using canvas yview_moveto
                    canvas = self.chunks_scrollable._parent_canvas
                    
                    # Calculate scroll fraction based on widget position
                    estimated_content_height = max(scrollable_height * 2, widget_y + widget_height + 100)
                    scroll_fraction = widget_y / estimated_content_height
                    scroll_fraction = max(0.0, min(1.0, scroll_fraction))
                    
                    canvas.yview_moveto(scroll_fraction)
                    return
                        
                except Exception as e:
                    pass
                
                # Method 2: Try using the scrollbar directly with calculated fraction
                try:
                    scrollbar = self.chunks_scrollable._scrollbar
                    
                    # Calculate scroll fraction based on widget position
                    estimated_content_height = max(scrollable_height * 2, widget_y + widget_height + 100)
                    scroll_fraction = widget_y / estimated_content_height
                    scroll_fraction = max(0.0, min(1.0, scroll_fraction))
                    
                    scrollbar.set(scroll_fraction, scroll_fraction + 0.1)
                    return
                    
                except Exception as e:
                    pass
        except Exception as e:
            print(f"Error scrolling to widget: {e}")  # For debugging
