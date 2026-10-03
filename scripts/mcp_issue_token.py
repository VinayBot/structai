"""Issue a StructAI access/refresh token pair for the MCP server to act as.

Logs in (or, with --register, registers then logs in) the given account directly
against the configured database - no running server required - using the same
app.services.auth_service calls the HTTP /auth routes use. Paste the printed
tokens into .env as MCP_ACCESS_TOKEN / MCP_REFRESH_TOKEN. See docs/MCP_SERVER.md.

Examples:
    python3 scripts/mcp_issue_token.py --email you@example.com --password yourpassword
    python3 scripts/mcp_issue_token.py --email you@example.com --password yourpassword --register
"""

import argparse
import asyncio
import sys

from app.core.errors import AppError
from app.db import get_session_maker


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--register",
        action="store_true",
        help="create the account first (skipped if it already exists)",
    )
    args = parser.parse_args()

    from app.services import auth_service

    async with get_session_maker()() as session:
        if args.register:
            try:
                await auth_service.register_user(session, email=args.email, password=args.password)
            except AppError as exc:
                print(f"(register skipped: {exc.message})", file=sys.stderr)

        tokens = await auth_service.authenticate_user(
            session, email=args.email, password=args.password
        )

    print(f"MCP_ACCESS_TOKEN={tokens.access_token}")
    print(f"MCP_REFRESH_TOKEN={tokens.refresh_token}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
