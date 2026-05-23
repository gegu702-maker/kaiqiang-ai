ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.10-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COSYVOICE_REPO=https://github.com/FunAudioLLM/CosyVoice.git \
    COSYVOICE_MODEL_DIR=iic/CosyVoice2-0.5B

RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --fix-missing --no-install-recommends \
    git \
    git-lfs \
    ffmpeg \
    sox \
    libsox-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/CosyVoice

RUN git clone --recursive ${COSYVOICE_REPO} CosyVoice \
    && cd CosyVoice \
    && git submodule update --init --recursive \
    && pip install --upgrade pip \
    && pip install setuptools wheel \
    && sed -i '/openai-whisper/d' requirements.txt \
    && pip install -r requirements.txt \
    && pip install --no-build-isolation openai-whisper==20231117

WORKDIR /opt/CosyVoice/CosyVoice

COPY server.py runtime/python/fastapi/server.py

EXPOSE 50000

CMD python runtime/python/fastapi/server.py --port 50000 --model_dir "${COSYVOICE_MODEL_DIR}"
