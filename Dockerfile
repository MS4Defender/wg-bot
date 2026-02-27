FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "-lc", "pwd && echo '---LS---' && ls -la && echo '---RUN---' && python -u main.py"]
