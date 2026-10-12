# Portable build recipe; no image is published or hardware-certified in v0.1.
FROM python:3.13-slim
WORKDIR /app
COPY solar_playbook ./solar_playbook
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
ENTRYPOINT ["python", "-m", "solar_playbook"]
CMD ["demo", "--out", "/tmp/solar-playbook"]
