"""
check_templates.py - ตรวจคุณภาพไฟล์ท่าต้นแบบ (JSON) ของทุกคำ

วางไว้ข้าง engine.py (โฟลเดอร์ handJoint) แล้วรัน:   python check_templates.py
ผลจะแสดงในหน้าจอ และบันทึกเป็น template_report.csv (เปิดด้วย Excel ได้)

แนวคิด: จำลอง "ผู้เรียนที่ทำท่าถูกเป๊ะ" จากไฟล์ต้นแบบเอง (เติมการสั่นของข้อต่อ และมุมมือที่แกว่งมากขึ้น
เมื่อมือเอียง/ชี้เข้ากล้อง เหมือนที่เกิดจริง) แล้วให้ระบบประเมินด้วยสูตรเดิม
ถ้าคำไหนได้คะแนนต่ำทั้งที่ผู้เรียนจำลองทำถูกทุกอย่าง แปลว่าปัญหาอยู่ที่ต้นแบบหรือสูตร ไม่ใช่ผู้เรียน
"""
import csv
import glob
import json
import os

import numpy as np

from engine import evaluate

DATA_DIR = os.environ.get("HANDJ_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(DATA_DIR, "output_json_relative_features")
rng = np.random.default_rng(0)


def jitter(hand, sigma=0.02):
    """จำลองข้อมูลจริงจากกล้อง: ข้อต่อสั่นเล็กน้อย และมุมมือคลาดเคลื่อนมากขึ้นเมื่อมือเอียง/ชี้เข้ากล้อง
    (ทิศมือคำนวณจากเวกเตอร์ข้อมือ->โคนนิ้วกลาง ยิ่งเวกเตอร์สั้น มุมยิ่งแกว่ง)"""
    a = np.array(hand, float)
    r9 = max(float(np.linalg.norm(a[9, :2])), 0.05)
    th = float(np.clip(rng.normal(0, 0.035 / r9), -0.6, 0.6))
    c, s = np.cos(th), np.sin(th)
    a[:, :2] = a[:, :2] @ np.array([[c, -s], [s, c]]).T
    a[:, :2] += rng.normal(0, sigma, a[:, :2].shape)
    a[:, 2] += rng.normal(0, sigma * 0.3, a.shape[0])
    return a.tolist()


def simulate_learner(kfs, reps=8):
    frames = []
    for kf in kfs:
        for _ in range(reps):
            frames.append({"frame_idx": len(frames) + 1, "jpeg": b"",
                           "hands": {s: (jitter(h) if h is not None else None) for s, h in kf["hands"].items()}})
    return frames


def analyse(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    kfs = data["keyframes"]
    hands = [(s, np.array(h, float)) for kf in kfs for s, h in kf["hands"].items() if h is not None]
    flags = []

    if any(h.shape != (21, 3) for _, h in hands):
        return None, ["โครงสร้างข้อมูลผิดปกติ"]

    sides = sorted({s for s, _ in hands})
    both = [kf for kf in kfs if kf["hands"].get("Left") is not None and kf["hands"].get("Right") is not None]
    both_frac = len(both) / len(kfs) if len(sides) == 2 else 1.0

    # รูปแบบใหม่: หมุนมือแล้ว จุดที่ 9 ต้องอยู่บนแกนตั้ง (x ≈ 0)
    rotated = np.mean([abs(h[9][0]) < 1e-3 for _, h in hands]) > 0.95
    # ความยาวข้อมือ->โคนนิ้วกลาง เทียบกับขนาดมือ: เล็ก = มือชี้เข้ากล้อง/เอียง ทำให้ทิศมือคำนวณไม่นิ่ง
    r9 = np.array([np.linalg.norm(h[9][:2]) for _, h in hands])
    low_ratio = float(np.mean(r9 < 0.3))

    sims = [evaluate(kfs, simulate_learner(kfs))["score"] for _ in range(3)]
    sim = float(np.mean(sims))

    if not rotated:
        flags.append("ไฟล์แบบเก่า (ไม่ได้หมุนมือ) ควรสร้างใหม่ด้วย oct15featureextractTemplate.py")
    if len(kfs) < 2:
        flags.append("คีย์เฟรมน้อยมาก")
    if len(kfs) > 12:
        flags.append("คีย์เฟรมเยอะ (ท่าเคลื่อนไหวเร็ว เทียบยาก)")
    if len(sides) == 2 and both_frac < 0.8:
        flags.append("มือข้างหนึ่งหายในต้นแบบบางเฟรม")
    if low_ratio > 0.3:
        flags.append("มือเอียง/ชี้เข้ากล้อง ทิศมืออาจไม่นิ่ง")
    if sim < 85:
        flags.append("คะแนนจำลองต่ำ")

    row = {"keyframes": len(kfs), "hands": "+".join(sides), "both_hands_frames_%": round(both_frac * 100),
           "tilted_hand_%": round(low_ratio * 100), "new_format": "yes" if rotated else "NO",
           "simulated_score": round(sim, 1)}
    return row, flags


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "*", "*_relative_features.json")))
    if not files:
        raise SystemExit("ไม่พบไฟล์ JSON ใน " + ROOT)
    rows = []
    for p in files:
        chapter = os.path.basename(os.path.dirname(p))
        word = os.path.basename(p).replace("_relative_features.json", "")
        try:
            row, flags = analyse(p)
        except Exception as e:  # ไฟล์เสียหรืออ่านไม่ได้
            row, flags = None, [f"อ่านไฟล์ไม่ได้: {e}"]
        rows.append({"chapter": chapter, "word": word, **(row or {}), "notes": "; ".join(flags)})

    rows.sort(key=lambda r: r.get("simulated_score", -1))
    print(f"{'chapter':10} {'word':26} {'kf':>3} {'hands':10} {'both%':>5} {'tilt%':>5} {'new':>4} {'sim':>6}  หมายเหตุ")
    for r in rows:
        print(f"{r['chapter']:10} {r['word'][:26]:26} {r.get('keyframes', '-'):>3} {r.get('hands', '-'):10} "
              f"{r.get('both_hands_frames_%', '-'):>5} {r.get('tilted_hand_%', '-'):>5} {r.get('new_format', '-'):>4} "
              f"{r.get('simulated_score', '-'):>6}  {r['notes']}")

    cols = ["chapter", "word", "keyframes", "hands", "both_hands_frames_%", "tilted_hand_%", "new_format", "simulated_score", "notes"]
    out = os.path.join(DATA_DIR, "template_report.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\nบันทึกรายงานแล้ว: {out}")
    print("sim = คะแนนของผู้เรียนจำลองที่ทำถูกเป๊ะ (ควรเกิน 90) | both% = เฟรมที่เจอสองมือ | tilt% = มือเอียง/ชี้เข้ากล้อง")


if __name__ == "__main__":
    main()
