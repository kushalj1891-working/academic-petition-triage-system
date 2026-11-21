import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/runs.db")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "triage-v1")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "stub")
MODEL_NAME = os.getenv("MODEL_NAME", "")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
