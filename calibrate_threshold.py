"""
calibrate_threshold.py - หาเกณฑ์ (threshold) ที่แยก "ท่าถูก" กับ "ท่าผิด" ได้ดีที่สุด

รัน (ในโฟลเดอร์ handJoint, เปิด env handJ แล้ว):  python calibrate_threshold.py
ไม่ต้องเปิดกล้อง ใช้เวลาประมาณ 1-3 นาที

วิธีวัด (ทุกอย่างจำลองจากไฟล์ต้นแบบของคุณเอง):
  - ท่าถูก = ต้นแบบของคำนั้น + สัญญาณรบกวน (ปรับให้ได้ราว 85% เหมือนที่คุณเจอตอนทำถูก)
  - ท่าผิด = ต้นแบบของ "คำอื่น" + สัญญาณรบกวนเท่ากัน แล้วเอามาให้ระบบตรวจกับคำนี้
ยิ่ง gap (ท่าถูก - ท่าผิด) กว้าง แปลว่าระบบแยกท่าได้ดี
"""
import glob
import json
import os

import numpy as np

import engine

DATA_DIR = os.environ.get("HANDJ_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(DATA_DIR, "output_json_relative_features")
rng = np.random.default_rng(1)


def noisy(hand, sigma):
    a = np.array(hand, float)
    r9 = max(float(np.linalg.norm(a[9, :2])), 0.05)
    th = float(np.clip(rng.normal(0, 0.035 / r9), -0.6, 0.6))
    c, s = np.cos(th), np.sin(th)
    a[:, :2] = a[:, :2] @ np.array([[c, -s], [s, c]]).T
    a[:, :2] += rng.normal(0, sigma, a[:, :2].shape)
    a[:, 2] += rng.normal(0, sigma * 0.3, a.shape[0])
    return a.tolist()


def frames_from(kfs, sigma, reps=6):
    out = []
    for kf in kfs:
        for _ in range(reps):
            out.append({"frame_idx": len(out) + 1, "jpeg": b"",
                        "hands": {s: (noisy(h, sigma) if h is not None else None) for s, h in kf["hands"].items()}})
    return out


def load():
    words = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "*", "*_relative_features.json"))):
        name = os.path.basename(p).replace("_relative_features.json", "")
        with open(p, encoding="utf-8") as f:
            words[name] = json.load(f)["keyframes"]
    return words


def run(words, names, thr, sigma, skip, n_imp=6):
    engine.SKIP_JOINTS = set(skip)
    gen, imp = [], []
    for w in names:
        gen.append(engine.evaluate(words[w], frames_from(words[w], sigma), thr)["score"])
        others = [o for o in words if o != w]
        for o in rng.choice(others, size=n_imp, replace=False):
            imp.append(engine.evaluate(words[w], frames_from(words[o], sigma), thr)["score"])
    return float(np.mean(gen)), float(np.mean(imp))


def main():
    words = load()
    if len(words) < 3:
        raise SystemExit("ไม่พบไฟล์ต้นแบบใน " + ROOT)
    names = list(rng.choice(list(words), size=min(20, len(words)), replace=False))
    print(f"พบ {len(words)} คำ ใช้ตัวอย่าง {len(names)} คำ\n")

    # 1) หาระดับสัญญาณรบกวนที่ทำให้ท่าถูกได้ราว 85% ที่เกณฑ์เดิม 0.14
    sigma = 0.02
    for s in (0.02, 0.04, 0.06, 0.08, 0.10, 0.12):
        g, _ = run(words, names[:8], 0.14, s, [], n_imp=1)
        sigma = s
        if g <= 88:
            break
    print(f"ระดับรบกวนที่ใช้จำลอง sigma={sigma} (ทำให้ท่าถูกได้ราว 85-88% ที่เกณฑ์ 0.14)\n")

    # 2) เทียบเกณฑ์และการข้ามข้อต่อที่ได้คะแนนฟรี
    print(f"{'ข้ามข้อต่อ':12} {'threshold':>9} {'ท่าถูก':>8} {'ท่าผิด':>8} {'gap':>7}")
    best = None
    for skip, label in (([], "ไม่ข้าม"), ([0, 9], "ข้าม 0,9")):
        for thr in (0.14, 0.12, 0.10, 0.08):
            g, i = run(words, names, thr, sigma, skip)
            print(f"{label:12} {thr:>9} {g:>8.1f} {i:>8.1f} {g - i:>7.1f}")
            # เลือกชุดที่ gap กว้าง โดยท่าถูกยังได้ไม่ต่ำกว่า 70
            if g >= 70 and (best is None or g - i > best[0]):
                best = (g - i, label, thr, g, i)
    print()
    if best:
        _, label, thr, g, i = best
        print(f"แนะนำ: {label}, threshold={thr}  (ท่าถูก≈{g:.0f}, ท่าผิด≈{i:.0f})")
        skip_env = "set HANDJ_SKIP_JOINTS=0,9\n" if label != "ไม่ข้าม" else ""
        print("วิธีใช้ ก่อนรัน uvicorn ให้พิมพ์:\n" + skip_env + f"set HANDJ_THRESHOLD={thr}")


if __name__ == "__main__":
    main()
