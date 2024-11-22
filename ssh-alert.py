import logging
import os
import re
import subprocess
import sys
import time

import requests

FILENAME = '/var/log/auth.log'
REGEX_PATTERN = re.compile(r"Accepted (publickey|password) for (?P<user>[^\s]+) from (?P<ip>[^\s]+)")
ALLOWED_IPS = os.environ.get('ALLOWED_IPS', [])
ZAMMAD_URL = os.environ.get('ZAMMAD_URL')
ZAMMAD_TOKEN = os.environ.get('ZAMMAD_TOKEN')
ZAMMAD_CUSTOMER = 'cdb@seatable.io'
ZAMMAD_TICKET_HOSTNAME = os.environ.get('ZAMMAD_TICKET_HOSTNAME')
ZAMMAD_GROUP = os.environ.get('ZAMMAD_GROUP', 'Support')

# Mapping from IP address to UNIX timestamps
LAST_TICKET_BY_IP: dict[str, float] = {}
# Only allow a single ticket per IP address to be created in this interval
TICKET_INTERVAL_IN_SECONDS = 60

logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

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
            create_ticket(user, ip)
            logger.info('Successfully created ticket')
            LAST_TICKET_BY_IP[ip] = time.time()
        except requests.exceptions.HTTPError as error:
            logger.error('Could not create ticket: %s', error.response.json())
        except Exception as error:
            logger.error('Could not create ticket: %s', error)

def create_ticket(user: str, ip: str) -> None:
    url = f'{ZAMMAD_URL.rstrip("/")}/api/v1/tickets'
    data = {
        "title": f'SSH Login on {ZAMMAD_TICKET_HOSTNAME}',
        "group": ZAMMAD_GROUP,
        "customer": ZAMMAD_CUSTOMER,
        "article": {
            "subject": f'SSH Login on {ZAMMAD_TICKET_HOSTNAME}',
            "body": f'SSH Login on {ZAMMAD_TICKET_HOSTNAME} for user {user} from {ip}',
            "type": "web",
        }
    }
    headers = {
        'Authorization': f'Bearer {ZAMMAD_TOKEN}',
        'Content-Type': 'application/json; charset=utf-8',
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

if __name__ == '__main__':
    logger.info('Starting ssh-alert')

    allowed_ips = os.environ.get('ALLOWED_IPS', '').split(',')
    logger.info('Allowed IPs: %s', allowed_ips)

    if not ZAMMAD_URL:
        logger.critical('ZAMMAD_URL must be provided')
        sys.exit(1)

    if not ZAMMAD_TOKEN:
        logger.critical('ZAMMAD_TOKEN must be provided')
        sys.exit(1)

    if not ZAMMAD_TICKET_HOSTNAME:
        logger.critical('ZAMMAD_TICKET_HOSTNAME must be provided')
        sys.exit(1)

    main(allowed_ips)
