import os

# Disable background scheduler during tests (lifespan would run heavy yfinance scans).
os.environ["BACKGROUND_JOBS_ENABLED"] = "false"
os.environ["WEBSOCKET_ENABLED"] = "true"
