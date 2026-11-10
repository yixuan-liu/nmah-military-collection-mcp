import os

API_BASE_URL = "https://api.si.edu/openaccess/api/v1.0"
REQUEST_TIMEOUT = 45.0


def get_api_key() -> str:
    """Read the key on demand so discovery works without credentials."""
    return os.environ.get("SMITHSONIAN_API_KEY", "").strip()
