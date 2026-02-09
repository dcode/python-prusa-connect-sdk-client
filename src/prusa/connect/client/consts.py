"""Constants used across the Prusa Connect SDK.

How to use the most important parts:
- Import this module to reference default URLs, application names, and authentication endpoints without
  hardcoding them in your application logic.
"""

APP_NAME = "prusa-connect"
APP_AUTHOR = "Prusa"

# API Defaults
DEFAULT_BASE_URL = "https://connect.prusa3d.com/app"
DEFAULT_TIMEOUT = 30.0

# Authentication Endpoints
AUTH_URL = "https://account.prusa3d.com/o/authorize/"
TOKEN_URL = "https://account.prusa3d.com/o/token/"
CLIENT_ID = "MRHTlZhZqkNrrQ6FUPtjyusAz8nc59ErHXP8XkS4"
REDIRECT_URI = "https://connect.prusa3d.com/login/auth-callback"

# Media Endpoints (for avatars, etc.)
MEDIA_BASE_URL = "https://media.printables.com/media/"
