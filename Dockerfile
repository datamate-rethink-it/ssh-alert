FROM python:3.13-alpine

RUN apk add --no-cache tzdata

WORKDIR /app

COPY requirements.txt /app

RUN pip install -r requirements.txt

COPY ssh-alert.py /app

CMD ["python3", "/app/ssh-alert.py"]
