"""Authentication route group."""

from routes.auth.sessions import router
from routes.dependencies import get_current_user
