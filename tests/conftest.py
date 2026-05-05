import os

# Set test credentials before any app module is imported.
# These values are used only during testing and are never committed.
os.environ.setdefault("BRAIN_API_KEY", "changeme_shared_secret")
