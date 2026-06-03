FROM python:3.11-slim
WORKDIR /app
RUN pip install pyyaml --no-cache-dir
COPY student_exporter.py .
COPY pomodoro.html .
COPY admin.html .
COPY late-night-alert.js .
EXPOSE 8001
CMD ["python", "student_exporter.py"]
