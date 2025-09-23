
from typing import List
from utils import count_tokens, setup_logger, load_config

class TelemetryManager:
    def __init__(self, client_config: dict):
        self.config = client_config  # Store the full config
        pricing = self.config.get("pricing", {})
        self.input_price = pricing.get("input", 0.0)
        self.output_price = pricing.get("output", 0.0)
        self.total_price = 0

        self.logger = setup_logger(self.__class__.__name__, load_config())
        
        # Debug logging to check pricing configuration
        self.logger.info("TelemetryManager initialized for '%s' with pricing - Input: $%.2f, Output: $%.2f", 
                        self.config.get("deployment_name", "unknown"), self.input_price, self.output_price)


    def calculate_price(self, text: str | List, is_input: bool):
        # Handle both string and list inputs
        if isinstance(text, list):
            # Extract text content from message objects using lambda
            text_content = " ".join(map(lambda msg: getattr(msg, 'content', str(msg)), text))
        else:
            text_content = str(text)
        
        tokens = count_tokens(text_content)
        
        if is_input:
            price = (tokens / 1_000_000) * self.input_price
        else:
            price = (tokens / 1_000_000) * self.output_price

        self.logger.info("Tokens: %d, %s, Price per 1M tokens: $%.2f, Estimated price: '$%.6f'", 
                        tokens, "INPUT" if is_input else "OUTPUT", 
                        self.input_price if is_input else self.output_price, price)
        self.total_price += price