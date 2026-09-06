"""Enable / disable / show country entitlement for a Telegram user."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Literal

from sqlalchemy import select

from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.db.models import CountryModel, EntitlementModel, UserModel

Action = Literal["enable", "disable", "status"]


async def set_entitlement(*, telegram_id: int, country_slug: str, action: Action) -> int:
    async with SessionFactory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if user is None:
            print(
                f"error: user telegram_id={telegram_id} not found "
                "(user must open the bot at least once)",
                file=sys.stderr,
            )
            return 2

        country = await session.scalar(
            select(CountryModel).where(CountryModel.slug == country_slug)
        )
        if country is None:
            print(f"error: country slug={country_slug!r} not found", file=sys.stderr)
            return 3

        row = await session.scalar(
            select(EntitlementModel).where(
                EntitlementModel.user_id == user.id,
                EntitlementModel.country_id == country.id,
            )
        )

        if action == "status":
            active = bool(row and row.active)
            print(
                f"telegram_id={telegram_id} user_id={user.id} "
                f"country={country.slug} title={country.title!r} active={active}"
            )
            return 0

        want_active = action == "enable"
        if row is None:
            if not want_active:
                print(
                    f"ok: telegram_id={telegram_id} country={country.slug} "
                    "active=false (no entitlement row)"
                )
                return 0
            session.add(EntitlementModel(user_id=user.id, country_id=country.id, active=True))
        else:
            row.active = want_active
        await session.commit()
        print(
            f"ok: telegram_id={telegram_id} country={country.slug} "
            f"title={country.title!r} active={want_active}"
        )
        return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Enable/disable Pomogator country access for a Telegram user"
    )
    parser.add_argument("--telegram-id", type=int, required=True)
    parser.add_argument("--country", required=True, help="Country slug, e.g. brazil")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    action: Action
    if args.enable:
        action = "enable"
    elif args.disable:
        action = "disable"
    else:
        action = "status"

    raise SystemExit(
        asyncio.run(
            set_entitlement(
                telegram_id=args.telegram_id,
                country_slug=args.country.strip().lower(),
                action=action,
            )
        )
    )


if __name__ == "__main__":
    main()
