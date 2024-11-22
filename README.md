# ssh-alert

This Docker container monitors `/var/log/auth.log` for suspicious logins and creates Zammad tickets if a successful login was detected.

## Prerequisites

Debian 12 does not write sshd logs to `/var/log/auth.log` by default:

1. Install `rsyslog`: `apt install rsyslog`.
1. Update `/etc/ssh/sshd_config`:

    ```
    SyslogFacility AUTH
    LogLevel INFO
    ```
1. Restart `sshd`: `service ssh restart`

## Environment Variables

```ini
# Comma-separated list of IP addresses
# Ranges or wildcards are currently not supported
ALLOWED_IPS='1.2.3.4,2.3.4.5'

ZAMMAD_URL='https://your-zammad-instance.com'

# Token with 'ticket.agent' scope
ZAMMAD_TOKEN=''

# This is used inside the created tickets to identify the machine
ZAMMAD_TICKET_HOSTNAME='hostname'
```

## How to test and develop

```bash
docker compose up -d --build
# TODO: docker compose watch support
docker compose logs -f
```

## Deployment

-> [`deploy/ssh-alert.yml`](./deploy/ssh-alert.yml)
