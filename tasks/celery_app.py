from celery import Celery

def make_celery():
    # Initialize Celery with Redis as the broker
    celery = Celery(
        __name__,
        broker='redis://localhost:7000/0',
       
    )
    

    
    return celery

celery = make_celery()
