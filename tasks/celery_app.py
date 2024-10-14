from celery import Celery

# Initialize Celery with Redis as the broker
celery = Celery(
    __name__,
    broker='redis://localhost:7000/0'
)

