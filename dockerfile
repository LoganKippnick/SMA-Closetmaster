FROM python:3.13.5-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Command to execute your script
CMD ["python", "main.py"]
