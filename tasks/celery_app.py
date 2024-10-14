from celery import Celery

def make_celery():
    # Initialize Celery with Redis as the broker
    celery = Celery(
        __name__,
        broker='redis://localhost:7000/0',
        include=['tasks.tools.c_nmap'],
        include=['tasks.tools.c_networktools'],
        include=['tasks.tools.c_whatweb'] ,
        include=['tasks.tools.c_sublist3r']  # Include the module where your tasks are located
    )

    # You can add more configuration here if needed
    celery.conf.update(
        task_routes={
            'tasks.tools.c_nmap.perform_scan': {'queue': 'scan'},
            'tasks.tools.c_networktools.perform_network_tool': {'queue': 'basic'},
            'tasks.tools.c_sublist3r.perform_sublist3r': {'queue': 'sublist3r'},
            'tasks.tools.c_whatweb.perform_whatweb': {'queue': 'whatweb'}
        }
    )

    return celery

celery = make_celery()