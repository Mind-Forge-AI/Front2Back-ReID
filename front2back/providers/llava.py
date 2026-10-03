"""Local LLaVA-OneVision 0.5B via Hugging Face Transformers (greedy decoding).

pip install "front2back-reid[local]"   # torch, transformers, accelerate
"""

from __future__ import annotations

import io
import os
import time

_RUNTIME: dict = {}


def _load(model_id: str):
    if model_id not in _RUNTIME:
        import torch
        from transformers import AutoProcessor, LlavaOnevisionForConditionalGeneration

        processor = AutoProcessor.from_pretrained(model_id)
        model = LlavaOnevisionForConditionalGeneration.from_pretrained(
            model_id, dtype=os.environ.get("LLAVA_ONEVISION_TORCH_DTYPE", "auto"),
            device_map=os.environ.get("LLAVA_ONEVISION_DEVICE_MAP", "auto"))
        _RUNTIME[model_id] = (torch, processor, model)
    return _RUNTIME[model_id]


def chat(model_id: str, images: list[dict], text: str, *, max_tokens: int = 700, **_: object) -> dict:
    from PIL import Image

    torch, processor, model = _load(model_id)
    content = [{"type": "image", "image": Image.open(io.BytesIO(im["bytes"])).convert("RGB")} for im in images]
    content.append({"type": "text", "text": text})
    start = time.perf_counter()
    inputs = processor.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True,
                                           tokenize=True, return_dict=True, return_tensors="pt")
    try:
        inputs = inputs.to(model.device, dtype=getattr(model, "dtype", None))
    except (TypeError, RuntimeError):
        inputs = inputs.to(model.device)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=int(max_tokens), do_sample=False)
    out_ids = generated[:, inputs["input_ids"].shape[-1]:]
    text_out = processor.batch_decode(out_ids, skip_special_tokens=True)[0].strip()
    return {"text": text_out, "latency_ms": int((time.perf_counter() - start) * 1000), "usage": {}, "raw": {"model": model_id}}
