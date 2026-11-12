FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
WORKDIR /app
RUN useradd --system dispatch
COPY server.py regras.py perguntas.py ./
COPY static/ static/
COPY tests/ tests/
USER dispatch
EXPOSE 8000
CMD ["python", "server.py"]
