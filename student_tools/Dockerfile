FROM python:3.11-slim
WORKDIR /app
RUN pip install pyyaml yfinance --no-cache-dir
COPY student_exporter.py .
COPY features.py .
COPY pomodoro.html .
COPY admin.html .
COPY stocks.html .
COPY weather.html .
COPY news.html .
COPY late-night-alert.js .
EXPOSE 8001
CMD ["python", "student_exporter.py"]
