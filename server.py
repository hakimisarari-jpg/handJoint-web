"""
server.py - Backend API สำหรับ SignLearn AI (รันบน localhost)
ใช้เฉพาะ starlette + uvicorn + websockets ที่มีใน env handJ อยู่แล้ว (ไม่ต้องลง fastapi)

รัน:  uvicorn server:app --reload --port 8000
โฟลเดอร์ข้อมูล (อยู่ข้างไฟล์นี้ หรือแก้ DATA_DIR):
    vid/<บท>/<คำ>.mp4
    output_json_relative_features/<บท>/<คำ>_relative_features.json
ถ้ามีโฟลเดอร์ frontend/ (มี index.html) จะเสิร์ฟที่ http://localhost:8000/ ให้เลย
"""
import glob
import json
import os
import re
import time

import cv2
import numpy as np
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from engine import evaluate, extract_robust_relative_landmarks

DATA_DIR = os.environ.get("HANDJ_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
JSON_ROOT = os.path.join(DATA_DIR, "output_json_relative_features")
VIDEO_ROOT = os.path.join(DATA_DIR, "vid")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
MODEL_COMPLEXITY = int(os.environ.get("HANDJ_COMPLEXITY", "1"))  # 1 = แม่นยำ (เหมือนสคริปต์อาจารย์), 0 = เร็วกว่า
MIN_SCORE = float(os.environ.get("HANDJ_MIN_SCORE", "0.75"))  # ตัดมือที่ความมั่นใจต่ำ (เช่น ผม/เงา ที่ถูกจับผิด)
# ต้นแบบมือเดียว: ใช้มือที่มั่นใจที่สุดของผู้เรียนข้างเดียว โดยไม่สนป้ายซ้าย/ขวา (ตั้ง HANDJ_SINGLE_ANYSIDE=0 เพื่อปิด)
SINGLE_ANYSIDE = os.environ.get("HANDJ_SINGLE_ANYSIDE", "1") != "0"
VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv")

CHAPTERS = [  # เรียงตามดีไซน์ SignLearn AI
    {"id": "greetings", "th": "คำทักทาย", "en": "Greetings"},
    {"id": "numbers", "th": "ตัวเลข", "en": "Numbers"},
    {"id": "times", "th": "เวลา", "en": "Times"},
]
LABEL_FIX = {"fourty": "forty"}  # แก้ชื่อที่สะกดผิดในชื่อไฟล์ (ไม่ต้องเปลี่ยนชื่อไฟล์จริง)


def _label(word):
    """ชื่อที่แสดงบนเว็บเป็นอังกฤษทั้งหมด: you_re welcome -> You're welcome"""
    t = re.sub(r"_(re|s|t|ll|ve|d|m)\b", r"'\1", LABEL_FIX.get(word, word)).replace("_", " ")
    return t[:1].upper() + t[1:]


def _words(chapter):
    pattern = os.path.join(JSON_ROOT, chapter, "*_relative_features.json")
    return [os.path.basename(p).replace("_relative_features.json", "") for p in sorted(glob.glob(pattern))]


def _video_path(chapter, word):
    for ext in VIDEO_EXTS:
        p = os.path.join(VIDEO_ROOT, chapter, word + ext)
        if os.path.exists(p):
            return p
    return None


def _check_chapter(chapter):
    if chapter not in {c["id"] for c in CHAPTERS}:
        raise HTTPException(404, "unknown chapter")


def _template_sides(chapter, word):
    """มือที่ท่าต้นแบบใช้จริง (Left/Right) ใช้ตัดมือที่ไม่เกี่ยวข้อง เช่น ผม ออก"""
    try:
        path = os.path.join(JSON_ROOT, str(chapter), f"{os.path.basename(str(word))}_relative_features.json")
        with open(path, encoding="utf-8") as f:
            kfs = json.load(f)["keyframes"]
        sides = {s for kf in kfs for s in ("Left", "Right") if kf["hands"].get(s) is not None}
        return sides or {"Left", "Right"}
    except Exception:
        return {"Left", "Right"}


def _template_hands(chapter, word, side):
    """มือของต้นแบบ (ข้าง side) ทุกคีย์เฟรม ใช้เลือกว่ามือไหนของผู้เรียนคือมือที่กำลังทำท่า"""
    try:
        path = os.path.join(JSON_ROOT, str(chapter), f"{os.path.basename(str(word))}_relative_features.json")
        with open(path, encoding="utf-8") as f:
            kfs = json.load(f)["keyframes"]
        return [np.array(kf["hands"][side], float) for kf in kfs if kf["hands"].get(side) is not None]
    except Exception:
        return []


def _pick_hands(cands, wanted, single_side, tmpl_hands=None):
    """cands = [(label, score, landmarks)] -> [(key, label, score, landmarks, coords)]
    key = ชื่อข้างที่ใช้เก็บลง hand_dict
    ต้นแบบมือเดียว: เลือก 'มือที่หน้าตาใกล้ท่าต้นแบบที่สุด' (ไม่ดูป้ายซ้าย/ขวา) เพื่อไม่ให้สลับไปมาระหว่างมือที่ทำท่ากับมืออีกข้างที่วางอยู่"""
    cands = [c for c in cands if c[1] >= MIN_SCORE]
    if single_side:
        scored = []
        for label, score, lm in cands:
            coords = extract_robust_relative_landmarks(lm)
            if tmpl_hands:
                arr = np.array(coords)
                d = min(float(np.mean(np.linalg.norm(arr - t, axis=1))) for t in tmpl_hands)
            else:
                d = -score  # ไม่มีข้อมูลต้นแบบ ให้ใช้ความมั่นใจสูงสุดแทน
            scored.append((d, label, score, lm, coords))
        scored.sort(key=lambda x: x[0])
        return [(single_side, l, sc, lm, co) for _, l, sc, lm, co in scored[:1]]
    return [(l, l, sc, lm, extract_robust_relative_landmarks(lm)) for l, sc, lm in cands if l in wanted]


# ---------------------------------------------------------------- REST
async def api_chapters(request):
    return JSONResponse([{**c, "count": len(_words(c["id"]))} for c in CHAPTERS])


async def api_words(request):
    ch = request.path_params["chapter"]
    _check_chapter(ch)
    return JSONResponse([
        {"id": w, "label": _label(w), "has_video": _video_path(ch, w) is not None}
        for w in _words(ch)
    ])


async def api_video(request):
    ch, word = request.path_params["chapter"], request.path_params["word"]
    _check_chapter(ch)
    path = _video_path(ch, os.path.basename(word))
    if path is None:
        raise HTTPException(404, "video not found")
    return FileResponse(path)  # วิดีโอต้นฉบับ (ไม่ flip) -> Frontend กลับด้านด้วย CSS scaleX(-1)


# ---------------------------------------------------------------- WebSocket
async def ws_session(ws):
    """
    โปรโตคอล (ต่อ 1 การเชื่อมต่อ = 1 รอบฝึก)
    Client -> Server
      binary : เฟรมกล้องดิบเป็น JPEG (ไม่ต้อง flip ฝั่ง client, server flip เอง เหมือนสคริปต์อาจารย์)
      text   : {"type":"start"} | {"type":"stop"} |
               {"type":"evaluate","chapter":"greetings","word":"deaf","threshold":0.14}
    Server -> Client
      {"type":"hands","recording":bool,"frames":int,
       "hands":[{"label":"Left|Right","score":0.98,"landmarks":[[x,y,z] x21]}]}   # พิกัด 0-1 บนภาพที่ flip แล้ว
      {"type":"result", ...ผลจาก engine.evaluate...}
      {"type":"error","message":"..."}
    """
    await ws.accept()
    from mediapipe.python.solutions import hands as mp_hands  # import ตอนใช้ เพื่อให้ REST ทดสอบได้โดยไม่ต้องมี mediapipe

    detector = mp_hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=MODEL_COMPLEXITY,
                              min_detection_confidence=0.5, min_tracking_confidence=0.5)
    recording, frames, counter = False, [], 0
    wanted = {"Left", "Right"}  # มือที่ต้นแบบใช้ (ตั้งผ่านข้อความ config)
    single_side = None          # ถ้าต้นแบบใช้มือเดียว จะเป็น "Left" หรือ "Right"
    tmpl_hands = []             # มือของต้นแบบ (ใช้เลือกมือที่กำลังทำท่า)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if msg.get("bytes"):
                img = cv2.imdecode(np.frombuffer(msg["bytes"], np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    continue
                counter += 1
                img = cv2.flip(img, 1)
                t0 = time.perf_counter()
                res = detector.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                out, hand_dict = [], {"Left": None, "Right": None}
                if res.multi_hand_landmarks and res.multi_handedness:
                    cands = [(hd.classification[0].label, hd.classification[0].score, lm)
                             for lm, hd in zip(res.multi_hand_landmarks, res.multi_handedness)]
                    for key, label, score, lm, coords in _pick_hands(cands, wanted, single_side, tmpl_hands):
                        out.append({"label": label, "score": round(score, 3),
                                    "landmarks": [[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in lm.landmark]})
                        hand_dict[key] = coords
                if recording and any(v is not None for v in hand_dict.values()):
                    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    frames.append({"frame_idx": counter, "hands": hand_dict, "jpeg": jpg.tobytes()})
                ms = round((time.perf_counter() - t0) * 1000)
                await ws.send_json({"type": "hands", "ms": ms, "recording": recording, "frames": len(frames), "hands": out})

            elif msg.get("text"):
                cmd = json.loads(msg["text"])
                t = cmd.get("type")
                if t == "config":
                    wanted = _template_sides(cmd.get("chapter"), cmd.get("word"))
                    single_side = next(iter(wanted)) if (SINGLE_ANYSIDE and len(wanted) == 1) else None
                    tmpl_hands = _template_hands(cmd.get("chapter"), cmd.get("word"), single_side) if single_side else []
                elif t == "start":
                    recording, frames = True, []
                elif t == "stop":
                    recording = False
                elif t == "evaluate":
                    recording = False
                    ch, word = cmd.get("chapter"), os.path.basename(str(cmd.get("word", "")))
                    tpl = os.path.join(JSON_ROOT, str(ch), f"{word}_relative_features.json")
                    if len(frames) < 5:
                        await ws.send_json({"type": "error", "message": "ตรวจพบมือน้อยเกินไป"})
                    elif not os.path.exists(tpl):
                        await ws.send_json({"type": "error", "message": "ไม่พบข้อมูลต้นแบบของคำนี้"})
                    else:
                        with open(tpl, encoding="utf-8") as f:
                            kfs = json.load(f)["keyframes"]
                        result = evaluate(kfs, frames, float(os.environ.get("HANDJ_THRESHOLD") or cmd.get("threshold", 0.14)))
                        # ไม่ส่งคะแนนดิบไปหน้าเว็บ (อาจารย์ให้แสดงเฉพาะคะแนนที่ปรับแล้วเมื่อผ่าน หรือ "ไม่ผ่าน")
                        payload = {k: v for k, v in result.items() if k not in ("score", "total_correct", "total_checked")}
                        await ws.send_json({"type": "result", **payload})
    except WebSocketDisconnect:
        pass
    finally:
        detector.close()


routes = [
    Route("/api/chapters", api_chapters),
    Route("/api/words/{chapter}", api_words),
    Route("/api/video/{chapter}/{word}", api_video),
    WebSocketRoute("/ws/session", ws_session),
]
if os.path.isdir(FRONTEND_DIR):
    routes.append(Mount("/", StaticFiles(directory=FRONTEND_DIR, html=True)))

app = Starlette(routes=routes, middleware=[
    Middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://localhost:5173",
                                              "http://127.0.0.1:5173", "http://localhost:8000"],
               allow_methods=["*"], allow_headers=["*"]),
])
