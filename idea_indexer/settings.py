import os


# Global configuration for API keys, model name, and token budget.
class Settings:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    token_budget_usd = float(os.getenv("TOKEN_BUDGET_DOLLARS", "3.0"))


settings = Settings()
