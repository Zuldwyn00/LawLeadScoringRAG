"""
Tracking and Statistics Widgets

This module contains widgets for displaying AI usage costs and lead statistics.
"""

import customtkinter as ctk
from ..styles import COLORS, FONTS


# ─── COST TRACKING WIDGET ────────────────────────────────────────────────────────
class CostTrackingWidget(ctk.CTkFrame):
    """Widget for displaying AI usage costs."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["tertiary_black"], **kwargs)
        self.current_lead_cost = 0.0
        self.total_session_cost = 0.0
        self.model_costs = {}  # Track costs per model
        self.setup_widgets()

    def setup_widgets(self):
        """Set up the cost tracking display."""
        self.cost_label = ctk.CTkLabel(
            self,
            text="💰 AI Usage Costs",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"],
        )
        self.cost_label.pack(pady=(10, 5))

        self.current_cost_label = ctk.CTkLabel(
            self,
            text="Current Lead: $0.000000",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        self.current_cost_label.pack(pady=2)

        self.total_cost_label = ctk.CTkLabel(
            self,
            text="Session Total: $0.000000",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        self.total_cost_label.pack(pady=2)
        
        # Model breakdown label (initially hidden)
        self.model_breakdown_label = ctk.CTkLabel(
            self,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
            wraplength=250,
        )
        self.model_breakdown_label.pack(pady=(2, 10))

    def update_current_lead_cost(self, cost: float):
        """Update the current lead cost display."""
        self.current_lead_cost = cost
        self.current_cost_label.configure(text=f"Current Lead: ${cost:.6f}")

    def add_to_session_total(self, cost: float):
        """Add cost to the session total."""
        self.total_session_cost += cost
        self.total_cost_label.configure(text=f"Session Total: ${self.total_session_cost:.6f}")

    def reset_current_lead_cost(self):
        """Reset the current lead cost to zero."""
        self.current_lead_cost = 0.0
        self.current_cost_label.configure(text="Current Lead: $0.000000")

    def reset_session_total(self):
        """Reset the session total cost to zero."""
        self.total_session_cost = 0.0
        self.total_cost_label.configure(text="Session Total: $0.000000")

    def get_current_lead_cost(self) -> float:
        """Get the current lead cost."""
        return self.current_lead_cost

    def get_session_total_cost(self) -> float:
        """Get the session total cost."""
        return self.total_session_cost

    def update_model_cost(self, model_name: str, cost: float):
        """Update cost for a specific model."""
        if model_name not in self.model_costs:
            self.model_costs[model_name] = 0.0
        self.model_costs[model_name] += cost
        self._update_model_breakdown()

    def _update_model_breakdown(self):
        """Update the model breakdown display."""
        if not self.model_costs:
            self.model_breakdown_label.configure(text="")
            return
        
        breakdown_lines = []
        for model, cost in self.model_costs.items():
            if cost > 0:
                breakdown_lines.append(f"{model}: ${cost:.6f}")
        
        if breakdown_lines:
            breakdown_text = "Models used:\n" + "\n".join(breakdown_lines)
            self.model_breakdown_label.configure(text=breakdown_text)
        else:
            self.model_breakdown_label.configure(text="")

    def reset_model_costs(self):
        """Reset all model costs."""
        self.model_costs = {}
        self._update_model_breakdown()


# ─── STATISTICS WIDGET ──────────────────────────────────────────────────────────
class StatsWidget(ctk.CTkFrame):
    """Widget for displaying lead statistics."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["tertiary_black"], **kwargs)
        self.setup_widgets()

    def setup_widgets(self):
        """Set up the statistics display."""
        self.stats_label = ctk.CTkLabel(
            self,
            text="Statistics",
            font=FONTS()["subheading"],
            text_color=COLORS["text_white"],
        )
        self.stats_label.pack(pady=(10, 5))

        self.total_label = ctk.CTkLabel(
            self,
            text="Total Leads: 0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        self.total_label.pack(pady=2)

        self.avg_score_label = ctk.CTkLabel(
            self,
            text="Average Score: 0.0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        self.avg_score_label.pack(pady=2)

        self.avg_confidence_label = ctk.CTkLabel(
            self,
            text="Average Confidence: 0.0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        self.avg_confidence_label.pack(pady=(2, 10))

    def update(self, scored_leads: list):
        """Update the statistics display."""
        if not scored_leads:
            self.total_label.configure(text="Total Leads: 0")
            self.avg_score_label.configure(text="Average Score: 0.0")
            self.avg_confidence_label.configure(text="Average Confidence: 0.0")
            return

        scores = [lead["score"] for lead in scored_leads]
        confidences = [lead.get("confidence", 50) for lead in scored_leads]

        avg_score = sum(scores) / len(scores)
        avg_confidence = sum(confidences) / len(confidences)

        self.total_label.configure(text=f"Total Leads: {len(scored_leads)}")
        self.avg_score_label.configure(text=f"Average Score: {avg_score:.1f}")
        self.avg_confidence_label.configure(
            text=f"Average Confidence: {avg_confidence:.1f}"
        )
