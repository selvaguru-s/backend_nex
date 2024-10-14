from celery import Celery

def make_celery():
    # Initialize Celery with Redis as the broker
    celery = Celery(
        __name__,
        broker='redis://localhost:7000/0',
        backend='redis://localhost:7000/0'  # Optional: if you want to store results
    )
    
    celery.conf.update(
        task_routes={
            'tasks.tools.c_nmap.perform_scan': {'queue': 'scan'},
            
        }
    )
    
    return celery

celery = make_celery()
