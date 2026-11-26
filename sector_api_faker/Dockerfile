FROM python:3.15-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app
COPY . /app/sector_api_faker/

EXPOSE 8080

CMD ["python", "-m", "sector_api_faker"]
