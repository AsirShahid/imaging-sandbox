"""RQ worker entrypoint: `python -m app.worker`."""
from redis import Redis
from rq import Queue, Worker

from .config import settings


def main() -> None:
    conn = Redis.from_url(settings.redis_url)
    Worker([Queue("default", connection=conn)], connection=conn).work(with_scheduler=True)


if __name__ == "__main__":
    main()
