"""
Model Selection Widget

This module contains a widget for selecting AI models from the client configuration.
"""

import customtkinter as ctk
import json
from pathlib import Path
from ..styles import COLORS, FONTS


# ─── MODEL SELECTION WIDGET ────────────────────────────────────────────────────────
class ModelSelectorWidget(ctk.CTkFrame):
    """Widget for selecting AI models from client configuration."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.selected_process_model = "gpt-5-mini"  # Default to gpt-5
        self.selected_final_model = "gpt-5"  # Default to gpt-5
        self.process_temperature = None  # No temperature by default
        self.final_temperature = None  # No temperature by default
        self.models = {}
        self.process_model_var = ctk.StringVar(value=self.selected_process_model)
        self.final_model_var = ctk.StringVar(value=self.selected_final_model)
        self.process_temp_var = ctk.StringVar(value="")
        self.final_temp_var = ctk.StringVar(value="")
        
        # Load model configurations
        self._load_model_configs()
        
        # Create UI components
        self._create_widgets()
        
        # Set up callbacks for model changes
        self.process_model_var.trace('w', self._on_process_model_changed)
        self.final_model_var.trace('w', self._on_final_model_changed)
        self.process_temp_var.trace('w', self._on_process_temp_changed)
        self.final_temp_var.trace('w', self._on_final_temp_changed)

    def _load_model_configs(self):
        """Load model configurations from client_configs.json."""
        try:
            config_path = Path(__file__).parent.parent.parent / "scripts" / "clients" / "client_configs.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Extract Azure clients (AI models)
            self.models = config.get("azure_clients", {})
            
            # Validate that default models exist, if not use first available model
            if self.models:
                # Check if process model exists, if not use first available
                if self.selected_process_model not in self.models:
                    first_model = list(self.models.keys())[0]
                    self.selected_process_model = first_model
                    self.process_model_var.set(first_model)
                
                # Check if final model exists, if not use first available  
                if self.selected_final_model not in self.models:
                    first_model = list(self.models.keys())[0]
                    self.selected_final_model = first_model
                    self.final_model_var.set(first_model)
                
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Could not load model configs: {e}")

    def _create_widgets(self):
        """Create the model selection UI components."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)
        
        # Process Model selection
        process_label = ctk.CTkLabel(
            self,
            text="Process Model:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        process_label.grid(row=0, column=0, sticky="w", padx=(15, 10), pady=10)
        
        # Process Model dropdown
        model_names = list(self.models.keys())
        self.process_model_dropdown = ctk.CTkOptionMenu(
            self,
            values=model_names,
            variable=self.process_model_var,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            button_color=COLORS["accent_orange"],
            button_hover_color=COLORS["accent_orange_hover"],
            text_color=COLORS["text_white"],
            dropdown_text_color=COLORS["text_white"],
            dropdown_fg_color=COLORS["tertiary_black"],
            dropdown_hover_color=COLORS["border_gray"],
        )
        self.process_model_dropdown.grid(row=0, column=1, sticky="ew", padx=(0, 15), pady=10)
        
        # Final Model selection
        final_label = ctk.CTkLabel(
            self,
            text="Final Model:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        final_label.grid(row=0, column=2, sticky="w", padx=(15, 10), pady=10)
        
        # Final Model dropdown
        self.final_model_dropdown = ctk.CTkOptionMenu(
            self,
            values=model_names,
            variable=self.final_model_var,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            button_color=COLORS["accent_orange"],
            button_hover_color=COLORS["accent_orange_hover"],
            text_color=COLORS["text_white"],
            dropdown_text_color=COLORS["text_white"],
            dropdown_fg_color=COLORS["tertiary_black"],
            dropdown_hover_color=COLORS["border_gray"],
        )
        self.final_model_dropdown.grid(row=0, column=3, sticky="ew", padx=(0, 15), pady=10)
        
        # Temperature controls
        process_temp_label = ctk.CTkLabel(
            self,
            text="Temp:",
            font=FONTS()["small"],
            text_color=COLORS["text_white"],
        )
        process_temp_label.grid(row=1, column=0, sticky="w", padx=(15, 5), pady=5)
        
        self.process_temp_entry = ctk.CTkEntry(
            self,
            textvariable=self.process_temp_var,
            width=60,
            font=FONTS()["small"],
            placeholder_text="None",
        )
        self.process_temp_entry.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=5)
        
        final_temp_label = ctk.CTkLabel(
            self,
            text="Temp:",
            font=FONTS()["small"],
            text_color=COLORS["text_white"],
        )
        final_temp_label.grid(row=1, column=2, sticky="w", padx=(15, 5), pady=5)
        
        self.final_temp_entry = ctk.CTkEntry(
            self,
            textvariable=self.final_temp_var,
            width=60,
            font=FONTS()["small"],
            placeholder_text="None",
        )
        self.final_temp_entry.grid(row=1, column=3, sticky="w", padx=(0, 15), pady=5)
        
        # Model info labels (shows pricing and description)
        self.process_info_label = ctk.CTkLabel(
            self,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
            wraplength=200,
        )
        self.process_info_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        
        self.final_info_label = ctk.CTkLabel(
            self,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
            wraplength=200,
        )
        self.final_info_label.grid(row=2, column=2, columnspan=2, sticky="w", padx=15, pady=(0, 5))
        
        # Update info displays
        self._update_model_info()

    def _on_process_model_changed(self, *args):
        """Handle process model selection change."""
        self.selected_process_model = self.process_model_var.get()
        self._update_model_info()

    def _on_final_model_changed(self, *args):
        """Handle final model selection change."""
        self.selected_final_model = self.final_model_var.get()
        self._update_model_info()

    def _on_process_temp_changed(self, *args):
        """Handle process temperature change."""
        temp_text = self.process_temp_var.get().strip()
        if temp_text == "":
            self.process_temperature = None
        else:
            try:
                temp_value = float(temp_text)
                if 0.0 <= temp_value <= 2.0:
                    self.process_temperature = temp_value
                else:
                    # Reset to empty if out of range
                    self.process_temp_var.set("")
                    self.process_temperature = None
            except ValueError:
                # Reset to empty if invalid
                self.process_temp_var.set("")
                self.process_temperature = None

    def _on_final_temp_changed(self, *args):
        """Handle final temperature change."""
        temp_text = self.final_temp_var.get().strip()
        if temp_text == "":
            self.final_temperature = None
        else:
            try:
                temp_value = float(temp_text)
                if 0.0 <= temp_value <= 2.0:
                    self.final_temperature = temp_value
                else:
                    # Reset to empty if out of range
                    self.final_temp_var.set("")
                    self.final_temperature = None
            except ValueError:
                # Reset to empty if invalid
                self.final_temp_var.set("")
                self.final_temperature = None

    def _update_model_info(self):
        """Update the model information display."""
        # Update process model info
        if self.selected_process_model in self.models:
            model_config = self.models[self.selected_process_model]
            description = model_config.get("description", "No description available")
            pricing = model_config.get("pricing", {})
            
            # Format pricing info
            input_cost = pricing.get("input", 0)
            output_cost = pricing.get("output", 0)
            
            if input_cost and output_cost:
                pricing_text = f"Input: ${input_cost}/1M tokens, Output: ${output_cost}/1M tokens"
            else:
                pricing_text = "Pricing not available"
            
            info_text = f"{description}\n{pricing_text}"
            self.process_info_label.configure(text=info_text)
        else:
            self.process_info_label.configure(text="Model information not available")
        
        # Update final model info
        if self.selected_final_model in self.models:
            model_config = self.models[self.selected_final_model]
            description = model_config.get("description", "No description available")
            pricing = model_config.get("pricing", {})
            
            # Format pricing info
            input_cost = pricing.get("input", 0)
            output_cost = pricing.get("output", 0)
            
            if input_cost and output_cost:
                pricing_text = f"Input: ${input_cost}/1M tokens, Output: ${output_cost}/1M tokens"
            else:
                pricing_text = "Pricing not available"
            
            info_text = f"{description}\n{pricing_text}"
            self.final_info_label.configure(text=info_text)
        else:
            self.final_info_label.configure(text="Model information not available")

    def get_selected_process_model(self):
        """
        Get the currently selected process model name.
        
        Returns:
            str: The selected process model name.
        """
        return self.selected_process_model

    def get_selected_final_model(self):
        """
        Get the currently selected final model name.
        
        Returns:
            str: The selected final model name.
        """
        return self.selected_final_model

    def get_process_model_config(self):
        """
        Get the configuration for the currently selected process model.
        
        Returns:
            dict: The process model configuration dictionary.
        """
        return self.models.get(self.selected_process_model, {})

    def get_final_model_config(self):
        """
        Get the configuration for the currently selected final model.
        
        Returns:
            dict: The final model configuration dictionary.
        """
        return self.models.get(self.selected_final_model, {})

    def set_process_model(self, model_name):
        """
        Set the selected process model programmatically.
        
        Args:
            model_name (str): The name of the process model to select.
        """
        if model_name in self.models:
            self.process_model_var.set(model_name)
            self.selected_process_model = model_name
            self._update_model_info()

    def set_final_model(self, model_name):
        """
        Set the selected final model programmatically.
        
        Args:
            model_name (str): The name of the final model to select.
        """
        if model_name in self.models:
            self.final_model_var.set(model_name)
            self.selected_final_model = model_name
            self._update_model_info()

    def get_process_temperature(self):
        """
        Get the currently selected process temperature.
        
        Returns:
            float or None: The process temperature, or None if not set.
        """
        return self.process_temperature

    def get_final_temperature(self):
        """
        Get the currently selected final temperature.
        
        Returns:
            float or None: The final temperature, or None if not set.
        """
        return self.final_temperature

    def set_process_temperature(self, temperature):
        """
        Set the process temperature programmatically.
        
        Args:
            temperature (float or None): The temperature value (0.0-2.0) or None.
        """
        if temperature is None:
            self.process_temp_var.set("")
            self.process_temperature = None
        elif 0.0 <= temperature <= 2.0:
            self.process_temp_var.set(str(temperature))
            self.process_temperature = temperature

    def set_final_temperature(self, temperature):
        """
        Set the final temperature programmatically.
        
        Args:
            temperature (float or None): The temperature value (0.0-2.0) or None.
        """
        if temperature is None:
            self.final_temp_var.set("")
            self.final_temperature = None
        elif 0.0 <= temperature <= 2.0:
            self.final_temp_var.set(str(temperature))
            self.final_temperature = temperature
