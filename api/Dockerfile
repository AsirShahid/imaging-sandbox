FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Runtime libs for JPEG/JPEG2000 DICOM pixel decoding (pylibjpeg backends).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Drop privileges: this image is on the public request path.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
