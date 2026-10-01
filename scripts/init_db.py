"""Create all database tables. """

from backend.app.db.base import Base
from backend.app.db.session import engine
import backend.app.models              # noqa: F401  (registers models with Base.metadata)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tables created:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()