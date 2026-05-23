# Copyright (c) 2024 Alibaba Inc (authors: Xiang Lyu)
#
# Local FastAPI adapter for CosyVoice.
# The upstream sample loads the uploaded prompt wav into a tensor and then
# passes that tensor to an API path that expects a readable audio path. This
# adapter keeps the prompt as a temporary file until streaming finishes.
import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

logging.getLogger("matplotlib").setLevel(logging.WARNING)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{ROOT_DIR}/../../..")
sys.path.append(f"{ROOT_DIR}/../../../third_party/Matcha-TTS")

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_data(model_output, cleanup_path: str | None = None):
    try:
        for item in model_output:
            tts_audio = (item["tts_speech"].numpy() * (2**15)).astype(np.int16).tobytes()
            yield tts_audio
    finally:
        if cleanup_path:
            Path(cleanup_path).unlink(missing_ok=True)


def save_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "prompt.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(upload.file, tmp)
        return tmp.name


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/inference_sft")
@app.post("/inference_sft")
async def inference_sft(tts_text: str = Form(), spk_id: str = Form()):
    model_output = cosyvoice.inference_sft(tts_text, spk_id)
    return StreamingResponse(generate_data(model_output), media_type="application/octet-stream")


@app.get("/inference_zero_shot")
@app.post("/inference_zero_shot")
async def inference_zero_shot(
    tts_text: str = Form(),
    prompt_text: str = Form(),
    prompt_wav: UploadFile = File(),
):
    logging.info(
        "CosyVoice local zero_shot prompt_wav=%s tts_text=%r prompt_text=%r",
        prompt_wav.filename,
        tts_text,
        prompt_text,
    )
    prompt_path = save_upload(prompt_wav)
    model_output = cosyvoice.inference_zero_shot(tts_text, prompt_text, prompt_path)
    return StreamingResponse(
        generate_data(model_output, prompt_path),
        media_type="application/octet-stream",
    )


@app.get("/inference_cross_lingual")
@app.post("/inference_cross_lingual")
async def inference_cross_lingual(tts_text: str = Form(), prompt_wav: UploadFile = File()):
    prompt_path = save_upload(prompt_wav)
    model_output = cosyvoice.inference_cross_lingual(tts_text, prompt_path)
    return StreamingResponse(
        generate_data(model_output, prompt_path),
        media_type="application/octet-stream",
    )


@app.get("/inference_instruct")
@app.post("/inference_instruct")
async def inference_instruct(
    tts_text: str = Form(),
    spk_id: str = Form(),
    instruct_text: str = Form(),
):
    model_output = cosyvoice.inference_instruct(tts_text, spk_id, instruct_text)
    return StreamingResponse(generate_data(model_output), media_type="application/octet-stream")


@app.get("/inference_instruct2")
@app.post("/inference_instruct2")
async def inference_instruct2(
    tts_text: str = Form(),
    instruct_text: str = Form(),
    prompt_wav: UploadFile = File(),
):
    prompt_path = save_upload(prompt_wav)
    model_output = cosyvoice.inference_instruct2(tts_text, instruct_text, prompt_path)
    return StreamingResponse(
        generate_data(model_output, prompt_path),
        media_type="application/octet-stream",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50000)
    parser.add_argument("--model_dir", type=str, default="iic/CosyVoice2-0.5B")
    args = parser.parse_args()
    cosyvoice = AutoModel(model_dir=args.model_dir)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
