# Use Kali Linux as the base image
FROM kalilinux/kali-rolling

# Install required packages including sudo
RUN apt-get update && \
    apt-get install -y python3 python3-pip redis-server nmap sublist3r whois traceroute dnsutils sslscan openssl whatweb sudo && \
    apt-get clean

# Allow running nmap with sudo without password
RUN echo 'ALL ALL=(ALL) NOPASSWD: /usr/bin/nmap' >> /etc/sudoers

# Copy the application code to the /app directory
COPY . /app

# Set the working directory to /app
WORKDIR /app

# Upgrade pip and ensure setuptools is installed to avoid build issues
RUN pip3 install --upgrade pip setuptools --break-system-packages

# Install Python dependencies from requirements.txt
RUN pip3 install --break-system-packages -r requirements.txt

# Expose the Redis port and the application port
EXPOSE 7000
EXPOSE 7001

# Command to run the Redis server, Celery worker, and the Python application with sudo
CMD sudo -E redis-server --port 7000 --daemonize yes && \
    #sudo -E celery -A tasks worker -Q scan,basic,whatweb,sublist3r --loglevel=info & \
    sudo -E celery -A tasks.celery_app worker -Q scan,basic,sublist3r,whatweb  --loglevel=info \
    sudo -E python3 app.py
