"""LOCAL ONLY: explicitly assign a demo user a role (no HTTP endpoint)."""
import argparse
from .db import connect, initialize
from .editor import ROLES, initialize_editor


def main():
    parser = argparse.ArgumentParser(description="Assign local demo account role")
    parser.add_argument("username")
    parser.add_argument("role", choices=sorted(ROLES))
    args = parser.parse_args()
    initialize()
    initialize_editor()
    with connect() as db:
        cur = db.execute("UPDATE users SET role=? WHERE username=?", (args.role, args.username.lower()))
        if not cur.rowcount:
            parser.error("Пользователь не найден: сначала зарегистрируйте его через сайт")
    print(f"Готово: {args.username.lower()} -> {args.role}")


if __name__ == "__main__":
    main()
