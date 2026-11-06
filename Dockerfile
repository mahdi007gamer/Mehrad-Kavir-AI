FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd -g 10001 mkai \
    && useradd --no-create-home -u 10001 -g mkai mkai
COPY app ./app
RUN mkdir -p /srv/data && chown -R mkai:mkai /srv
USER mkai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" || exit 1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
