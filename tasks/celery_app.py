from celery import Celery

def make_celery():
    # Initialize Celery with Redis as the broker
    celery = Celery(
        __name__,
        broker='redis://localhost:7000/0',
        include=['tasks.tools.c_nmap']  # Include the module where your tasks are located
    )

    # You can add more configuration here if needed
    celery.conf.update(
        task_routes={
            'tasks.tools.c_nmap.perform_scan': {'queue': 'scan'}
        }
    )

    return celery

celery = make_celery()