# Repozitoriy bilan birga keladigan modellar

| Fayl | Vazifasi | Manba | Litsenziya |
|---|---|---|---|
| `minifasnet_v2_2.7_80x80.onnx` | Passiv PAD (2.7x kesim) | [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) `2.7_80x80_MiniFASNetV2.pth` | Apache 2.0 © Minivision |
| `minifasnet_v1se_4.0_80x80.onnx` | Passiv PAD (4.0x kesim) | o'sha repo, `4_0_0_80x80_MiniFASNetV1SE.pth` | Apache 2.0 © Minivision |

ONNX fayllar `tools/convert_minifasnet.py` bilan asl vaznlardan olingan
(`weights_only=True`, arxitektura — `tools/minifasnet_arch.py`). PyTorch va ONNX
natijalari bir xil ekanligi `strict=True` yuklash orqali tekshirilgan.

Katta modellar (SCRFD, ArcFace, MediaPipe) repozitoriyga qo'shilmaydi —
`python -m faceid models` ularni rasmiy manbalardan yuklab, SHA-256 bo'yicha tekshiradi:

| Model | Manba | Litsenziya |
|---|---|---|
| SCRFD-10G (`det_10g.onnx`) | InsightFace `buffalo_l` | Faqat notijorat / ilmiy maqsadda |
| ArcFace R50 WebFace600K (`w600k_r50.onnx`) | InsightFace `buffalo_l` | Faqat notijorat / ilmiy maqsadda |
| Face Landmarker (`face_landmarker.task`) | Google MediaPipe | Apache 2.0 |
