"""MiniFASNet (.pth) vaznlarini ONNX formatiga o'girish — faqat ishlab chiquvchi uchun.

Foydalanuvchiga PyTorch kerak emas: tayyor ONNX fayllar assets/models/ da.
Vaznlar ``weights_only=True`` bilan yuklanadi (pickle orqali kod bajarilmaydi),
arxitektura esa shu repozitoriydagi tools/minifasnet_arch.py dan olinadi.

Ishlatish:
    pip install torch onnx
    python tools/convert_minifasnet.py --weights <.pth fayllar papkasi>

Vazn manbasi: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
(resources/anti_spoof_models, Apache 2.0)
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import torch
from minifasnet_arch import MiniFASNet

MODELS = {
    # fayl: (versiya, SE, chiqish, sha256)
    "2.7_80x80_MiniFASNetV2.pth": ("V2", False, "minifasnet_v2_2.7_80x80.onnx",
                                   "a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0"),
    "4_0_0_80x80_MiniFASNetV1SE.pth": ("V1", True, "minifasnet_v1se_4.0_80x80.onnx",
                                       "84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets" / "models"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, (ver, se, onnx_name, sha) in MODELS.items():
        pth = Path(a.weights) / name
        if hashlib.sha256(pth.read_bytes()).hexdigest() != sha:
            raise SystemExit(f"{name}: SHA-256 mos kelmadi")
        state = torch.load(pth, map_location="cpu", weights_only=True)
        state = {(k[7:] if k.startswith("module.") else k): v for k, v in state.items()}
        model = MiniFASNet(ver, se)
        model.load_state_dict(state, strict=True)
        model.eval()
        torch.onnx.export(model, (torch.zeros(1, 3, 80, 80),), str(out / onnx_name), input_names=["input"],
                          output_names=["logits"], dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
                          opset_version=17, dynamo=False)
        print("OK", out / onnx_name)


if __name__ == "__main__":
    main()
