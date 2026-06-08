FROM python:3.14-bookworm AS development

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    git \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN python -m pip install --upgrade pip \
  && python -m pip install -e ".[dev]"

CMD ["python", "-m", "django", "runserver", "0.0.0.0:30000"]
