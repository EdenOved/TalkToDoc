FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
CMD ["bash", "-lc", "sleep infinity"]

