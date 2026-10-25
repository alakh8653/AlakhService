"""Operator commands. Grant the first admin with:

    docker compose exec auth_service python -m app.cli make-admin ops@example.com

(Later admins can be granted the same way; the account must already be registered.)
"""

import argparse
import asyncio
import sys

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def set_role(db: AsyncSession, identifier: str, role: str) -> User:
    """Gives the account with this email or phone number [role]; raises LookupError if there is none."""
    user = (
        await db.execute(select(User).where(or_(User.email == identifier.lower(), User.phone == identifier)))
    ).scalar_one_or_none()
    if user is None:
        raise LookupError(f"No account with email or phone {identifier!r}")
    user.role = role
    await db.commit()
    return user


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("make-admin", "grant admin access"), ("revoke-admin", "return an admin to a normal user")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("identifier", help="the account's email or phone number")
    args = parser.parse_args(argv)

    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            user = await set_role(db, args.identifier, "admin" if args.command == "make-admin" else "user")
        except LookupError as e:
            print(e, file=sys.stderr)
            return 1
    print(f"{user.email or user.phone} is now {user.role}. They must sign in again for it to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
