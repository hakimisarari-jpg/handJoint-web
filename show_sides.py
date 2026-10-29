"""
show_sides.py - ดูว่าในต้นแบบแต่ละคำ ระบบเห็นมือข้างไหนในแต่ละคีย์เฟรม
(ใช้เช็คว่าคำไหน "ใช้มือเดียวจริง" แต่ป้ายซ้าย/ขวาสลับไปมา)

รัน (ในโฟลเดอร์ handJoint):  python show_sides.py
อ่านผล: R = เห็นมือขวา, L = เห็นมือซ้าย, . = ไม่เห็น   ตัวอย่าง  "R.  R.  .L  RL"  = 4 คีย์เฟรม
"""
import glob
import json
import os

DATA_DIR = os.environ.get("HANDJ_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(DATA_DIR, "output_json_relative_features")

print(f"{'chapter':9} {'word':24} {'คีย์เฟรมแต่ละอัน':40} หมายเหตุ")
for p in sorted(glob.glob(os.path.join(ROOT, "*", "*_relative_features.json"))):
    chapter = os.path.basename(os.path.dirname(p))
    word = os.path.basename(p).replace("_relative_features.json", "")
    with open(p, encoding="utf-8") as f:
        kfs = json.load(f)["keyframes"]
    seq = [("R" if kf["hands"].get("Right") is not None else ".") + ("L" if kf["hands"].get("Left") is not None else ".") for kf in kfs]
    only_r = "R." in seq
    only_l = ".L" in seq
    note = ""
    if only_r and only_l:
        note = "ป้ายซ้าย/ขวาสลับไปมา (อาจใช้มือเดียวจริง)"
    elif "RL" in seq and (only_r or only_l):
        note = "สองมือ แต่บางเฟรมหายข้างหนึ่ง"
    print(f"{chapter:9} {word[:24]:24} {'  '.join(seq)[:40]:40} {note}")
