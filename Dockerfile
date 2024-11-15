FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt /app

RUN pip install -r requirements.txt

COPY sshlog.py /app

CMD ["python3", "/app/sshlog.py"]
