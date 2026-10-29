"""engine.py - อัลกอริทึมประเมินท่าทาง (คัดลอกจาก App.py เดิมทุกฟังก์ชัน ไม่แก้สูตร)"""
import base64
import os
import numpy as np
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw

# ข้อต่อที่ข้ามไม่นับคะแนน (ตั้งผ่าน HANDJ_SKIP_JOINTS เช่น "0,9") ค่าเริ่มต้น = นับครบ 21 จุดเหมือนของอาจารย์
# กติกาคะแนนที่อาจารย์กำหนด: คะแนนดิบ >= PASS_MARK ถือว่าผ่าน และแสดงคะแนน = คะแนนดิบ x SCORE_FACTOR (ไม่เกิน SCORE_CAP)
# ต่ำกว่า PASS_MARK = ไม่ผ่าน (ไม่แสดงคะแนน) เก็บภาพเฟรมที่ผิดมากที่สุด MAX_ERROR_FRAMES ภาพ
PASS_MARK = float(os.environ.get("HANDJ_PASS_MARK", "50"))
SCORE_FACTOR = float(os.environ.get("HANDJ_SCORE_FACTOR", "1.15"))
SCORE_CAP = float(os.environ.get("HANDJ_SCORE_CAP", "98"))
MAX_ERROR_FRAMES = int(os.environ.get("HANDJ_MAX_ERROR_FRAMES", "2"))

SKIP_JOINTS = {int(x) for x in os.environ.get("HANDJ_SKIP_JOINTS", "").split(",") if x.strip()}

LANDMARK_NAMES = {
    0: "Wrist (ข้อมือ)",
    1: "Thumb_Cmc (โคนนิ้วโป้ง)", 2: "Thumb_Mcp (ข้อต่อนิ้วโป้งล่าง)", 3: "Thumb_Ip (ข้อต่อนิ้วโป้งบน)", 4: "Thumb_Tip (ปลายนิ้วโป้ง)",
    5: "Index_Mcp (โคนนิ้วชี้)", 6: "Index_Pip (ข้อต่อกลางนิ้วชี้)", 7: "Index_Dip (ข้อต่อปลายแหลมนิ้วชี้)", 8: "Index_Tip (ปลายนิ้วชี้)",
    9: "Middle_Mcp (โคนนิ้วกลาง)", 10: "Middle_Pip (ข้อต่อกลางนิ้วกลาง)", 11: "Middle_Dip (ข้อต่อปลายแหลมนิ้วกลาง)", 12: "Middle_Tip (ปลายนิ้วกลาง)",
    13: "Ring_Mcp (โคนนิ้วนาง)", 14: "Ring_Pip (ข้อต่อกลางนิ้วนาง)", 15: "Ring_Dip (ข้อต่อปลายแหลมนิ้วนาง)", 16: "Ring_Tip (ปลายนิ้วนาง)",
    17: "Pinky_Mcp (โคนนิ้วก้อย)", 18: "Pinky_Pip (ข้อต่อกลางนิ้วก้อย)", 19: "Pinky_Dip (ข้อต่อปลายแหลมนิ้วก้อย)", 20: "Pinky_Tip (ปลายนิ้วก้อย)"
}

# ==============================================================================
# ฟังก์ชันคำนวณและสกัดพิกัด (Robust Relative Landmarks)
# ==============================================================================
def extract_robust_relative_landmarks(hand_landmarks, z_weight=0.2):
    coords = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
    wrist = coords[0]
    relative = coords - wrist
    
    # Rotation Normalization
    v = relative[9][:2]
    angle = np.arctan2(v[1], v[0])
    target_angle = -np.pi / 2
    rotation_angle = target_angle - angle
    
    cos_a, sin_a = np.cos(rotation_angle), np.sin(rotation_angle)
    rot_mat = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    relative[:, :2] = np.dot(relative[:, :2], rot_mat.T)
    
    # Scale Normalization
    max_dist = np.max(np.linalg.norm(relative[:, :2], axis=1))
    if max_dist > 0:
        relative = relative / max_dist
        
    relative[:, 2] = relative[:, 2] * z_weight
    return relative.tolist()

def calculate_joint_distances_robust(t_coords, u_coords):
    t_arr = np.array(t_coords)
    u_arr = np.array(u_coords)
    diff = t_arr - u_arr
    raw_distances = np.sqrt(diff[:, 0]**2 + diff[:, 1]**2 + diff[:, 2]**2)
    return np.clip(raw_distances / 2.0, 0.0, 1.0)

def convert_hand_dict_to_vector(hand_dict):
    vec = []
    active_coords = None
    for side in ['Right', 'Left']:
        if hand_dict.get(side) is not None:
            active_coords = hand_dict[side]
            break
            
    for side in ['Right', 'Left']:
        if hand_dict.get(side) is not None:
            vec.extend(np.array(hand_dict[side]).flatten())
        elif active_coords is not None:
            vec.extend(np.array(active_coords).flatten())
        else:
            vec.extend(np.zeros(63))
            
    return np.array(vec)

def align_and_compare_hand_pairs(t_hands, u_hands, joint_error_threshold=0.14):
    pairs = []
    for side in ['Right', 'Left']:
        if t_hands.get(side) is not None and u_hands.get(side) is not None:
            pairs.append((side, t_hands[side], u_hands[side]))
            
    if len(pairs) == 0:
        t_active = [s for s in ['Right', 'Left'] if t_hands.get(s) is not None]
        u_active = [s for s in ['Right', 'Left'] if u_hands.get(s) is not None]
        if len(t_active) > 0 and len(u_active) > 0:
            pairs.append((f"{t_active[0]}->{u_active[0]}", t_hands[t_active[0]], u_hands[u_active[0]]))

    total_checked, correct_count, errors = 0, 0, []
    if len(pairs) == 0:
        for side, coords in t_hands.items():
            if coords is not None:
                total_checked += 21
                for j_id in range(21):
                    errors.append((side, j_id, LANDMARK_NAMES.get(j_id, f"Joint_{j_id}"), 1.0))
        return total_checked, correct_count, errors

    for label, t_coords, u_coords in pairs:
        dists = calculate_joint_distances_robust(t_coords, u_coords)
        for j_id, dist in enumerate(dists):
            if j_id in SKIP_JOINTS:
                continue
            total_checked += 1
            if dist > joint_error_threshold:
                errors.append((label, j_id, LANDMARK_NAMES.get(j_id, f"Joint_{j_id}"), dist))
            else:
                correct_count += 1
                
    return total_checked, correct_count, errors



FINGERS = [("นิ้วโป้ง", (1, 2, 3, 4)), ("นิ้วชี้", (5, 6, 7, 8)), ("นิ้วกลาง", (9, 10, 11, 12)),
           ("นิ้วนาง", (13, 14, 15, 16)), ("นิ้วก้อย", (17, 18, 19, 20))]


def _pairs(t_hands, u_hands):
    """จับคู่มือต้นแบบกับมือผู้เรียน (ตรรกะเดียวกับ align_and_compare_hand_pairs)"""
    pairs = [(s, t_hands[s], u_hands[s]) for s in ("Right", "Left")
             if t_hands.get(s) is not None and u_hands.get(s) is not None]
    if not pairs:
        ta = [s for s in ("Right", "Left") if t_hands.get(s) is not None]
        ua = [s for s in ("Right", "Left") if u_hands.get(s) is not None]
        if ta and ua:
            pairs.append((f"{ta[0]}->{ua[0]}", t_hands[ta[0]], u_hands[ua[0]]))
    return pairs


def make_hints(t_hands, u_hands, threshold=0.14, limit=3):
    """แปลงข้อต่อที่คลาดเคลื่อนเป็นคำแนะนำภาษาไทยที่ผู้เรียนเข้าใจ (ระดับนิ้ว ไม่ใช่ระดับข้อต่อ)"""
    pairs = _pairs(t_hands, u_hands)
    hints = []
    if not pairs:
        return [{"hand": "", "finger": "มือ", "text": "ไม่เห็นมือในภาพนี้ ลองยกมือเข้ากรอบกล้องให้เห็นชัด", "level": "high", "_d": 1.0}][:limit]
    for label, t, u in pairs:
        t, u = np.array(t, float), np.array(u, float)
        d = calculate_joint_distances_robust(t, u)
        side = label.split("->")[-1]
        hand = ("มือขวา" if side == "Right" else "มือซ้าย") if len(pairs) > 1 else ""
        thumb_dir = 1.0 if (t[5][0] - t[17][0]) >= 0 else -1.0  # ด้านนิ้วโป้งอยู่ทิศ x บวกหรือลบ
        for name, ids in FINGERS:
            worst = max((float(d[j]) for j in ids if j not in SKIP_JOINTS), default=0.0)
            if worst <= threshold:
                continue
            tip = ids[-1]
            d_ext = float(np.linalg.norm(u[tip]) - np.linalg.norm(t[tip]))          # + = เหยียดกว่าต้นแบบ
            to_thumb = float((u[tip][0] - t[tip][0]) * thumb_dir)                  # + = เอียงไปทางนิ้วโป้ง
            if abs(d_ext) >= abs(to_thumb) and abs(d_ext) > 0.08:
                text = "งอมากเกินไป ลองเหยียดให้ตรงขึ้น" if d_ext < 0 else "เหยียดมากเกินไป ลองงอเข้าอีกนิด"
            elif abs(to_thumb) > 0.08:
                if ids[0] == 1:
                    text = ("กางออกจากฝ่ามือมากเกินไป ลองเก็บเข้าหาฝ่ามือ" if to_thumb > 0
                            else "เก็บเข้าหาฝ่ามือมากเกินไป ลองกางออกอีกนิด")
                else:
                    text = ("เอียงไปทางนิ้วโป้งมากเกินไป ลองขยับกลับมาทางนิ้วก้อย" if to_thumb > 0
                            else "เอียงไปทางนิ้วก้อยมากเกินไป ลองขยับกลับมาทางนิ้วโป้ง")
            else:
                text = "ตำแหน่งคลาดเล็กน้อย ลองดูท่าผู้สอนอีกครั้ง"
            hints.append({"hand": hand, "finger": name, "text": text,
                          "level": "high" if worst >= 0.25 else "low", "_d": worst})
    hints.sort(key=lambda h: -h["_d"])
    return hints[:limit]


def evaluate(template_kfs, user_frames, threshold=0.14):
    """user_frames: list ของ {'frame_idx', 'hands', 'jpeg'(bytes)} -> dict พร้อมส่งเป็น JSON"""
    t_vecs = [convert_hand_dict_to_vector(kf['hands']) for kf in template_kfs]
    u_vecs = [convert_hand_dict_to_vector(f['hands']) for f in user_frames]
    _, path = fastdtw(t_vecs, u_vecs, dist=euclidean)

    t_to_u = {i: [] for i in range(len(template_kfs))}
    for t_i, u_i in path:
        t_to_u[t_i].append(u_i)

    checked_all, correct_all, error_frames = 0, 0, []
    for t_i, cands in t_to_u.items():
        if not cands:
            continue
        best = min(cands, key=lambda u: euclidean(t_vecs[t_i], u_vecs[u]))
        uf = user_frames[best]
        checked, correct, errors = align_and_compare_hand_pairs(
            template_kfs[t_i]['hands'], uf['hands'], joint_error_threshold=threshold)
        checked_all += checked
        correct_all += correct
        if errors:
            frame_score = (correct / checked * 100) if checked else 0.0
            error_frames.append({
                "frame_score": round(frame_score, 1),  # % ข้อต่อที่ถูกในเฟรมนี้ (ยิ่งต่ำ ยิ่งผิดมาก)
                "_severity": sum(float(x[3]) for x in errors),
                "hints": make_hints(template_kfs[t_i]['hands'], uf['hands'], threshold),
                "template_kf_id": t_i + 1,
                "user_frame_idx": uf['frame_idx'],
                "image": "data:image/jpeg;base64," + base64.b64encode(uf['jpeg']).decode(),
                "errors": [{"side": s, "joint_id": j, "joint_name": n, "distance": round(float(d), 3)}
                           for s, j, n, d in errors],
            })
    raw = round(correct_all / checked_all * 100, 2) if checked_all else 0.0
    passed = raw >= PASS_MARK
    n_error = len(error_frames)
    error_frames.sort(key=lambda f: (f["frame_score"], -f["_severity"]))  # ผิดมากที่สุดมาก่อน
    error_frames = error_frames[:MAX_ERROR_FRAMES]
    for f in error_frames:
        f.pop("_severity")
        for h in f["hints"]:
            h.pop("_d", None)
    return {
        "score": raw,  # คะแนนดิบ (ใช้ในสคริปต์วัดผล server จะไม่ส่งตัวนี้ไปหน้าเว็บ)
        "passed": passed,
        "display_score": round(min(raw * SCORE_FACTOR, SCORE_CAP), 1) if passed else None,
        "total_checked": checked_all,
        "total_correct": correct_all,
        "template_keyframes": len(template_kfs),
        "error_keyframes": n_error,
        "error_frames": error_frames,
    }
