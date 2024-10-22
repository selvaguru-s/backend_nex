from celery import Celery

def make_celery():
    # Initialize Celery with Redis as the broker
    celery = Celery(
        __name__,
        broker='redis://localhost:7000/0',
        include=[
            'tasks.tools.c_nmap',
            'tasks.tools.c_networktools',
            'tasks.tools.c_whatweb',
            'tasks.tools.c_sublist3r'
            'tasks.tools.c_httpcurl'  # Include the modules where your tasks are located
        ]
    )

    # You can add more configuration here if needed
    celery.conf.update(
        task_routes={
            'tasks.tools.c_nmap.perform_scan': {'queue': 'scan'},
            'tasks.tools.c_networktools.perform_network_tool': {'queue': 'basic'},
            'tasks.tools.c_sublist3r.perform_sublist3r': {'queue': 'sublist3r'},
            'tasks.tools.c_whatweb.perform_whatweb': {'queue': 'whatweb'},
            'tasks.tools.c_httpcurl.perform_httpcurl': {'queue': 'httpcurl'},
        }
    )

    return celery

celery = make_celery()
