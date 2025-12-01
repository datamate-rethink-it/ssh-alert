import logging
import os
import re
import socket
import subprocess
import sys
import time
import requests

logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

FILENAME = '/var/log/auth.log'
REGEX_PATTERN = re.compile(r"Accepted (publickey|password) for (?P<user>[^\s]+) from (?P<ip>[^\s]+)")

# Environment variables
ZAMMAD_URL = os.environ.get('ZAMMAD_URL')
ZAMMAD_TOKEN = os.environ.get('ZAMMAD_TOKEN')
ZAMMAD_CUSTOMER = 'cdb@seatable.io'
ZAMMAD_GROUP = os.environ.get('ZAMMAD_GROUP', 'Support')
ZAMMAD_ENABLE = os.environ.get('ZAMMAD_ENABLE', 'false').lower() == 'true'

NTFY_URL = os.environ.get('NTFY_URL')
NTFY_TOPIC = os.environ.get('NTFY_TOPIC', 'ssh-alert')
NTFY_TOKEN = os.environ.get('NTFY_TOKEN')
NTFY_ENABLE = os.environ.get('NTFY_ENABLE', 'false').lower() == 'true'

ALLOWED_IPS = [ip.strip() for ip in os.environ.get('ALLOWED_IPS', '').split(',') if ip.strip()]
HOSTNAME = socket.gethostname().strip()

# Input validation
if ZAMMAD_ENABLE:
    if not all([ZAMMAD_URL, ZAMMAD_TOKEN, ZAMMAD_GROUP, ZAMMAD_CUSTOMER]):
        logger.critical('ZAMMAD_ENABLE=true but configuration is missing')
        sys.exit(1)

if NTFY_ENABLE:
    if not all([NTFY_URL, NTFY_TOPIC, NTFY_TOKEN]):
        logger.critical('NTFY_ENABLE=true but NTFY_URL is missing')
        sys.exit(1)


# Mapping from IP address to UNIX timestamps
LAST_TICKET_BY_IP: dict[str, float] = {}
# Only allow a single ticket per IP address to be created in this interval
TICKET_INTERVAL_IN_SECONDS = 60

def main(allowed_ips: list[str]):
    f = subprocess.Popen(['tail', '-F', '-n0', FILENAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    while True:
        line = f.stdout.readline()

        if not line:
            break

        line = line.strip().decode('utf-8')
        match = re.search(REGEX_PATTERN, line)
        if not match:
            continue

        user = match.group('user')
        ip = match.group('ip')

        if ip in allowed_ips:
            logger.info('Login from %s from %s (ALLOWED)', user, ip)
            continue

        logger.error('Login from %s from %s (NOT ALLOWED)', user, ip)
        current_time = time.time()
        if (LAST_TICKET_BY_IP.get(ip, 0) + TICKET_INTERVAL_IN_SECONDS) > current_time:
            logger.info('Skipping ticket creation since last ticket was created less than %d seconds ago', TICKET_INTERVAL_IN_SECONDS)
            continue

        try:
            if ZAMMAD_ENABLE:
                create_ticket(user, ip)
                
            if NTFY_ENABLE:
                create_ntfy_notification(user, ip)

            LAST_TICKET_BY_IP[ip] = time.time()
        except Exception as error:
            logger.error('Notification failed: %s', error)

def create_ntfy_notification(user: str, ip: str) -> None:
    url = f'{NTFY_URL.rstrip("/")}/{NTFY_TOPIC}'
    message = f'SSH Login on `{HOSTNAME}` for user `{user}` from {ip}'

    headers = {
        'prio': 'high',
        'tags': 'warning',
        'Authorization': f'Bearer {NTFY_TOKEN}'
    }
    
    response = requests.post(url, data=message.encode('utf-8'), headers=headers)
    response.raise_for_status()
    logger.info('ntfy notification sent to %s', NTFY_TOPIC)

def create_ticket(user: str, ip: str) -> None:
    url = f'{ZAMMAD_URL.rstrip("/")}/api/v1/tickets'
    data = {
        "title": f'SSH-Alert on {HOSTNAME}',
        "group": ZAMMAD_GROUP,
        "customer": ZAMMAD_CUSTOMER,
        "article": {
            "subject": f'SSH-Alert on {HOSTNAME}',
            "body": f'SSH Login on {HOSTNAME} for user {user} from {ip}',
            "type": "web",
        }
    }
    headers = {
        'Authorization': f'Bearer {ZAMMAD_TOKEN}',
        'Content-Type': 'application/json; charset=utf-8',
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    logger.info('Zammad ticket created')

if __name__ == '__main__':
    logger.info('Starting ssh-alert:')
    logger.info('- Hostname:    %s', HOSTNAME)
    logger.info('- Allowed IPs: %s', ALLOWED_IPS)
    logger.info('- Use ZAMMAD:  %s', ZAMMAD_ENABLE)
    logger.info('- Use NTFY:    %s', NTFY_ENABLE)
    main(ALLOWED_IPS)
