FROM python:3.8-slim AS builder
COPY . /backend
WORKDIR /backend
RUN apt update -y
RUN apt install -y build-essential
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN python3 -m pip install -r requirements.txt
RUN python3 -m pip install fastapi[all]
RUN python3 -m pip install detectron2 -f \
  https://dl.fbaipublicfiles.com/detectron2/wheels/cpu/torch1.10/index.html

FROM python:3.8-slim
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . /backend
WORKDIR /backend
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0