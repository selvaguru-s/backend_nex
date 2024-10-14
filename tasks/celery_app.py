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
            'tasks.tools.c_whatweb.perform_whatweb':{'queue':'whatweb'},
            'tasks.tools.c_networktools.perform_network_tool':{'queue':'basic'},
            'tasks.tools.c_sublist3r.perform_sublist3r':{'queue':'sublist3r'}
            
        }
    )
    
    return celery

celery = make_celery()
