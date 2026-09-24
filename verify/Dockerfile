# One-shot verification image: bundles the API code + tests so it can run
# pytest itself, then exercises the live api/web services over the network.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/api

COPY api/requirements.txt /srv/api/requirements.txt
RUN pip install --no-cache-dir \
    -r /srv/api/requirements.txt \
    pytest==8.3.4 httpx==0.28.1

COPY api/app /srv/api/app
COPY api/tests /srv/api/tests
COPY verify/verify.py /srv/verify.py

CMD ["python", "/srv/verify.py"]
