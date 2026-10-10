"""Reset a user's password from the server, for when no administrator can sign in.

    docker compose exec backend python -m scripts.reset_password <username>

The password becomes the default administrator password (DEFAULT_ADMIN_PASSWORD, "admin" unless set), the
account is reactivated and must choose a new password at its next sign-in, and its sessions are ended.
"""

import sys

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.repositories.user import UserRepository
from app.services.auth import AuthService


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.reset_password <username>")
    with SessionLocal() as db:
        user = UserRepository().get_by_username(db, sys.argv[1])
        if user is None:
            sys.exit(f"No user named {sys.argv[1]!r}")
        user.hashed_password = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
        user.is_active = True
        user.must_change_password = True
        AuthService().end_sessions(db, user)
    print(f"Password of {user.username!r} reset to the default; it must be changed at the next sign-in.")


if __name__ == "__main__":
    main()
