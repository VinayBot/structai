"""Promote an existing user to the admin role, directly against the database.

Registration always creates role="user", so there's no API path to create the
*first* admin - this script is that bootstrap step. Once at least one admin
exists, further role changes go through PATCH /admin/users/{user_id}/role.

Example:
    python3 scripts/promote_admin.py --email you@example.com
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db import get_session_maker
from app.models.user import User


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    async with get_session_maker()() as session:
        user = await session.scalar(select(User).where(User.email == args.email))
        if user is None:
            print(f"no user with email {args.email!r}", file=sys.stderr)
            sys.exit(1)

        user.role = "admin"
        await session.commit()

    print(f"{args.email} is now an admin")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
