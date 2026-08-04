"""Terminal-only admin management.

There is deliberately no path in the web app for a user to become admin on their own - the
first admin has to be bootstrapped from here, run directly on the server/dev machine:

    python -m app.cli promote-admin someone@example.com

Every admin after that can be promoted/demoted from the Users tab in Settings (admin-only).
"""

import argparse
import sys

from app.db import SessionLocal
from app.models import User, UserRole


def promote_admin(email: str) -> None:
    """Set an already-registered account's role to ADMIN.

    Requires the account to already exist (created by registering through the web app first) -
    this command only changes a role, it doesn't create accounts.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"No account found for {email!r} - register through the web app first.")
            sys.exit(1)

        if user.role == UserRole.ADMIN:
            print(f"{email} is already an admin.")
            return

        user.role = UserRole.ADMIN
        db.commit()
        print(f"{email} is now an admin.")
    finally:
        db.close()


def main() -> None:
    """Entry point for `python -m app.cli <command> ...`. Currently only one subcommand exists
    (`promote-admin`); structured with argparse subparsers so more can be added later without
    changing the invocation style."""
    parser = argparse.ArgumentParser(description="Vessel Monitoring Dashboard admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    promote_parser = subparsers.add_parser("promote-admin", help="Grant admin role to a registered user")
    promote_parser.add_argument("email", help="Email of an already-registered account")

    args = parser.parse_args()
    if args.command == "promote-admin":
        promote_admin(args.email)


if __name__ == "__main__":
    main()
