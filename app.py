import os
import glob
import base64
import json
import cv2
import mediapipe as mp
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw

from mediapipe.python.solutions import hands as mp_hands
from mediapipe.python.solutions import drawing_utils as mp_drawing
from mediapipe.python.solutions import drawing_styles as mp_drawing_styles

@st.cache_resource
def get_mp_hands(max_num_hands=2, min_detection_confidence=0.5, min_tracking_confidence=0.5):
    return mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=max_num_hands,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence
    )

# ==============================================================================
# ตั้งค่าหน้าเว็บ Streamlit (Page Configuration)
# ==============================================================================
st.set_page_config(
    page_title="Thai Sign Language Evaluator",
    page_icon="🤟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# ชื่อเรียกจุดข้อต่อมือ 21 จุด
# ==============================================================================
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
            total_checked += 1
            if dist > joint_error_threshold:
                errors.append((label, j_id, LANDMARK_NAMES.get(j_id, f"Joint_{j_id}"), dist))
            else:
                correct_count += 1
                
    return total_checked, correct_count, errors

import sys


def open_camera():
    """เปิดกล้อง (บน Windows ใช้ DirectShow เพื่อเปิดไวและขอภาพ 16:9 เหมือนกล้อง Mac ที่อาจารย์ทดสอบ)"""
    if sys.platform == "win32":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap
    return cv2.VideoCapture(0)


# ==============================================================================
# ตั้งค่าตำแหน่งโฟลเดอร์ (ไม่แสดงพาธบนหน้าเว็บ)
# โครงสร้างที่คาดไว้ (อยู่โฟลเดอร์เดียวกับไฟล์นี้):
#   vid/<บท>/<คำ>.mp4
#   output_json_relative_features/<บท>/<คำ>_relative_features.json
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_ROOT = os.path.join(BASE_DIR, "output_json_relative_features")
VIDEO_ROOT = os.path.join(BASE_DIR, "vid")
VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv")

CHAPTERS = {
    "greetings": {"th": "คำทักทาย", "en": "Greetings", "icon": "👋"},
    "numbers": {"th": "ตัวเลข", "en": "Numbers", "icon": "🔢"},
    "times": {"th": "เวลา", "en": "Times", "icon": "🕒"},
}

# ชื่อไทยของคำศัพท์ (เติมเพิ่มได้) ถ้าไม่มีจะแสดงชื่อไฟล์แทน
WORD_LABELS = {
    "deaf": "คนหูหนวก",
    "eight": "แปด",
}


def list_words(chapter):
    """สแกนหาคำศัพท์ของบทจากไฟล์ JSON ที่มีอยู่จริง"""
    folder = os.path.join(JSON_ROOT, chapter)
    words = []
    for path in sorted(glob.glob(os.path.join(folder, "*_relative_features.json"))):
        words.append(os.path.basename(path).replace("_relative_features.json", ""))
    return words


def word_title(word):
    th = WORD_LABELS.get(word)
    return f"{th} ({word})" if th else word.replace("_", " ")


def get_json_path(chapter, word):
    return os.path.join(JSON_ROOT, chapter, f"{word}_relative_features.json")


def get_video_path(chapter, word):
    for ext in VIDEO_EXTS:
        p = os.path.join(VIDEO_ROOT, chapter, word + ext)
        if os.path.exists(p):
            return p
    return None


@st.cache_data(show_spinner=False)
def video_to_data_uri(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"mov": "video/quicktime", "mkv": "video/x-matroska", "avi": "video/x-msvideo"}.get(ext, "video/mp4")
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def show_teacher_video(chapter, word, height=420):
    """แสดงวิดีโอผู้สอนแบบกลับซ้าย-ขวา (ตรงกับด้านที่ใช้ดึง joint ใน JSON)"""
    path = get_video_path(chapter, word)
    if path is None:
        st.error("❌ ไม่พบวิดีโอตัวอย่างของคำนี้")
        with st.expander("รายละเอียดสำหรับผู้ดูแลระบบ"):
            st.code(os.path.join(VIDEO_ROOT, chapter, word + ".mp4"))
        return
    flip_css = "transform: scaleX(-1);" if st.session_state.mirror_teacher else ""
    html = f"""
    <video controls autoplay muted loop playsinline
           style="width:100%; max-height:{height - 10}px; border-radius:12px; background:#000; {flip_css}">
      <source src="{video_to_data_uri(path)}">
    </video>"""
    components.html(html, height=height)


# ==============================================================================
# Session State
# ==============================================================================
defaults = {
    "page": "chapter",       # chapter -> word -> hand -> watch -> practice -> result
    "chapter": None,
    "word": None,
    "confirmed_hand": "Right",
    "user_frames_data": [],
    "mirror_teacher": True,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def go(page):
    st.session_state.page = page
    st.rerun()


# ==============================================================================
# Sidebar
# ==============================================================================
st.sidebar.title("⚙️ ตั้งค่า")
JOINT_THRESHOLD = st.sidebar.slider(
    "ความเข้มงวดในการตรวจ (Joint Error Threshold)",
    min_value=0.05, max_value=0.30, value=0.14, step=0.01,
    help="ค่าน้อย = ตรวจเข้มงวดขึ้น"
)
st.session_state.mirror_teacher = st.sidebar.checkbox(
    "กลับด้านวิดีโอผู้สอน (กระจกเงา)", value=st.session_state.mirror_teacher
)
if st.sidebar.button("🏠 กลับหน้าแรก"):
    st.session_state.user_frames_data = []
    go("chapter")

# ==============================================================================
# Header + แถบขั้นตอน
# ==============================================================================
st.title("🤟 เรียนภาษามือไทย")
st.caption("ฝึกทำท่าตามผู้สอน แล้วให้ระบบช่วยตรวจว่าท่าของคุณถูกหรือไม่")

PRACTICE_STEPS = ["hand", "watch", "practice", "result"]
if st.session_state.page in PRACTICE_STEPS:
    cur = PRACTICE_STEPS.index(st.session_state.page)
    labels = ["ตรวจสอบมือ", "ดูตัวอย่าง", "ฝึกทำท่า", "สรุปผล"]
    cols = st.columns(4)
    for i, (c, lb) in enumerate(zip(cols, labels)):
        mark = "✅" if i < cur else ("🔵" if i == cur else "⚪")
        c.markdown(f"**{mark} {i + 1}. {lb}**")
    st.caption(f"บทเรียน: {CHAPTERS[st.session_state.chapter]['th']}  |  คำ: {word_title(st.session_state.word)}")
st.markdown("---")

page = st.session_state.page

# ------------------------------------------------------------------------------
# หน้า 1: เลือกบทเรียน
# ------------------------------------------------------------------------------
if page == "chapter":
    st.subheader("📚 เลือกบทเรียน")
    cols = st.columns(len(CHAPTERS))
    for col, (key, info) in zip(cols, CHAPTERS.items()):
        with col:
            n = len(list_words(key))
            st.markdown(f"## {info['icon']} {info['th']}")
            st.caption(f"{info['en']} · {n} คำ")
            if st.button("เริ่มเรียนบทนี้", key=f"ch_{key}", type="primary",
                         use_container_width=True, disabled=(n == 0)):
                st.session_state.chapter = key
                go("word")

# ------------------------------------------------------------------------------
# หน้า 2: เลือกคำศัพท์
# ------------------------------------------------------------------------------
elif page == "word":
    ch = st.session_state.chapter
    st.subheader(f"{CHAPTERS[ch]['icon']} บท{CHAPTERS[ch]['th']} — เลือกคำศัพท์")
    if st.button("← กลับไปเลือกบท"):
        go("chapter")

    words = list_words(ch)
    if not words:
        st.warning("ยังไม่มีคำศัพท์ในบทนี้")
    per_row = 3
    for i in range(0, len(words), per_row):
        cols = st.columns(per_row)
        for col, w in zip(cols, words[i:i + per_row]):
            with col:
                if st.button(word_title(w), key=f"w_{w}", use_container_width=True):
                    st.session_state.word = w
                    st.session_state.user_frames_data = []
                    go("hand")

# ------------------------------------------------------------------------------
# ขั้นตอนที่ 1: ตรวจสอบและยืนยันมือซ้าย/ขวา
# ------------------------------------------------------------------------------
elif page == "hand":
    st.subheader("📌 ขั้นตอนที่ 1: ตรวจสอบและยืนยันมือที่ใช้")
    st.info("💡 ชูมือหน้ากล้องเพื่อตรวจสอบตำแหน่งมือซ้าย/ขวา ระบบจะแสดงป้ายบนภาพ")

    col_cam, col_ctrl = st.columns([2, 1])

    with col_ctrl:
        st.write("### ⚙️ เลือกมือหลักที่ใช้ทำท่าทาง")
        hand_option = st.radio(
            "ระบุมือที่ต้องการใช้ประเมิน:",
            ["Right (มือขวา)", "Left (มือซ้าย)", "Right+Left (สองมือ)"],
            index=0
        )
        if st.button("✅ ยืนยันมือ และไปขั้นตอนถัดไป", type="primary", use_container_width=True):
            st.session_state.confirmed_hand = hand_option.split()[0]
            go("watch")
        if st.button("← เลือกคำอื่น", use_container_width=True):
            go("word")
        st.markdown("---")
        st.caption("มือที่ระบบกำลังตรวจจับได้ในขณะนี้:")
        detected_status = st.empty()

    with col_cam:
        st.write("### 🎥 Live Preview ตรวจสอบมือ")
        cam_preview = st.empty()
        cap = open_camera()
        mp_hands_obj = get_mp_hands(max_num_hands=2, min_detection_confidence=0.5)

        while cap.isOpened() and st.session_state.page == "hand":
            ret, frame = cap.read()
            if not ret:
                st.error("❌ ไม่สามารถเปิดกล้อง Webcam ได้")
                break

            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = frame_rgb.shape
            results = mp_hands_obj.process(frame_rgb)
            detected_hands_list = []

            if results.multi_hand_landmarks and results.multi_handedness:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    label = handedness.classification[0].label
                    score = handedness.classification[0].score
                    detected_hands_list.append(f"{label} ({score*100:.0f}%)")

                    mp_drawing.draw_landmarks(
                        frame_rgb, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style()
                    )
                    wrist_x = int(hand_landmarks.landmark[0].x * w)
                    wrist_y = int(hand_landmarks.landmark[0].y * h)
                    text_color = (0, 255, 0) if label == "Right" else (0, 215, 255)
                    cv2.putText(frame_rgb, f"[{label} Hand]",
                                (max(10, wrist_x - 50), max(30, wrist_y - 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2, cv2.LINE_AA)

            if detected_hands_list:
                detected_status.success(f"ตรวจพบ: {', '.join(detected_hands_list)}")
            else:
                detected_status.warning("ยังไม่พบมือในกล้อง กรุณาชูมือขึ้นมา")

            cam_preview.image(frame_rgb, channels="RGB", output_format="JPEG", use_container_width=True)

        cap.release()

# ------------------------------------------------------------------------------
# ขั้นตอนที่ 2: ดูวิดีโอตัวอย่างผู้สอน
# ------------------------------------------------------------------------------
elif page == "watch":
    st.subheader("📌 ขั้นตอนที่ 2: ดูท่าทางจากผู้สอน")
    st.success(f"มือที่ยืนยันใช้งาน: **[{st.session_state.confirmed_hand}]**")

    col_vid, col_info = st.columns([2, 1])
    with col_vid:
        show_teacher_video(st.session_state.chapter, st.session_state.word)
    with col_info:
        st.write("### คำแนะนำ")
        st.write("1. สังเกตการเคลื่อนไหวและจังหวะการเปลี่ยนท่าทางของผู้สอน")
        st.write("2. เมื่อพร้อมแล้ว กดปุ่มด้านล่างเพื่อเปิดกล้องและเริ่มฝึก")
        if st.button("🎬 พร้อมปฏิบัติท่าทาง", type="primary", use_container_width=True):
            go("practice")
        if st.button("← กลับไปตรวจสอบมือ", use_container_width=True):
            go("hand")

# ------------------------------------------------------------------------------
# ขั้นตอนที่ 3: ฝึกปฏิบัติ (วิดีโอผู้สอน | กล้องผู้เรียน)
# ------------------------------------------------------------------------------
elif page == "practice":
    st.subheader("📌 ขั้นตอนที่ 3: ฝึกปฏิบัติและบันทึกท่าทาง")
    st.info("💡 ดูวิดีโอฝั่งซ้าย แล้วทำท่าตามหน้ากล้องฝั่งขวา กด '🔴 เริ่มบันทึก' เพื่อเริ่มเก็บข้อมูล")

    col_teacher, col_user = st.columns(2)

    with col_teacher:
        st.write("### 🎬 วิดีโอต้นแบบผู้สอน")
        show_teacher_video(st.session_state.chapter, st.session_state.word)

    with col_user:
        st.write("### 🎥 กล้องของคุณ")
        cam_placeholder = st.empty()
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            start_btn = st.button("🔴 เริ่มบันทึก", type="primary", use_container_width=True)
        with btn_col2:
            stop_btn = st.button("⏹️ หยุดบันทึก & ประเมิน", use_container_width=True)

    if start_btn:
        st.session_state.user_frames_data = []
        cap = open_camera()
        mp_hands_obj = get_mp_hands(max_num_hands=2, min_detection_confidence=0.5)
        frame_count = 0
        st.toast("🔴 กำลังบันทึกการทำท่าทาง...", icon="🎥")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            frame = cv2.flip(frame, 1)
            annotated_frame = frame.copy()
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = mp_hands_obj.process(frame_rgb)

            frame_hand_dict = {'Left': None, 'Right': None}
            if results.multi_hand_landmarks and results.multi_handedness:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    side = handedness.classification[0].label
                    frame_hand_dict[side] = extract_robust_relative_landmarks(hand_landmarks)
                    mp_drawing.draw_landmarks(
                        annotated_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style()
                    )

            if frame_hand_dict['Left'] is not None or frame_hand_dict['Right'] is not None:
                st.session_state.user_frames_data.append({
                    'frame_idx': frame_count,
                    'image': cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB),
                    'hands': frame_hand_dict
                })

            cv2.putText(annotated_frame, "REC - Recording...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cam_placeholder.image(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB),
                                  channels="RGB", output_format="JPEG", use_container_width=True)

        cap.release()

    if stop_btn:
        if len(st.session_state.user_frames_data) > 0:
            go("result")
        else:
            st.error("❌ ยังไม่มีข้อมูลบันทึก กรุณากด '🔴 เริ่มบันทึก' และทำท่าทางก่อน")

# ------------------------------------------------------------------------------
# ขั้นตอนที่ 4: ประเมินผลด้วย DTW
# ------------------------------------------------------------------------------
elif page == "result":
    st.subheader("📌 ขั้นตอนที่ 4: ผลการประเมินและจุดที่ควรปรับ")
    template_path = get_json_path(st.session_state.chapter, st.session_state.word)

    if not os.path.exists(template_path):
        st.error("❌ ไม่พบข้อมูลต้นแบบของคำนี้")
        with st.expander("รายละเอียดสำหรับผู้ดูแลระบบ"):
            st.code(template_path)
    else:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_kfs = json.load(f)['keyframes']

        user_frames_data = st.session_state.user_frames_data

        template_vecs = [convert_hand_dict_to_vector(kf['hands']) for kf in template_kfs]
        user_vecs = [convert_hand_dict_to_vector(f['hands']) for f in user_frames_data]

        distance, dtw_path = fastdtw(template_vecs, user_vecs, dist=euclidean)

        t_to_u_map = {t_idx: [] for t_idx in range(len(template_kfs))}
        for t_idx, u_idx in dtw_path:
            t_to_u_map[t_idx].append(u_idx)

        aligned_user_keyframes = []
        for t_idx in range(len(template_kfs)):
            u_candidates = t_to_u_map[t_idx]
            if not u_candidates:
                continue
            t_vec = template_vecs[t_idx]
            best_u_idx = min(u_candidates, key=lambda u_i: euclidean(t_vec, user_vecs[u_i]))
            matched_kf = user_frames_data[best_u_idx].copy()
            matched_kf['template_matched_idx'] = t_idx
            aligned_user_keyframes.append(matched_kf)

        total_checked, total_correct, error_frames = 0, 0, []
        for u_kf in aligned_user_keyframes:
            t_idx = u_kf['template_matched_idx']
            checked, correct, errors = align_and_compare_hand_pairs(
                template_kfs[t_idx]['hands'], u_kf['hands'], joint_error_threshold=JOINT_THRESHOLD
            )
            total_checked += checked
            total_correct += correct
            if errors:
                error_frames.append({
                    'template_kf_id': t_idx + 1,
                    'user_frame_idx': u_kf['frame_idx'],
                    'image': u_kf['image'],
                    'errors': errors
                })

        score = (total_correct / total_checked * 100) if total_checked > 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("⭐ คะแนนความถูกต้อง", f"{score:.2f}%")
        m2.metric("✅ ข้อต่อที่ถูกต้อง", f"{total_correct} / {total_checked} จุด")
        m3.metric("⚠️ ท่าที่มีจุดผิด", f"{len(error_frames)} / {len(template_kfs)} ท่า")
        st.markdown("---")

        if not error_frames:
            st.balloons()
            st.success("🎉 ยินดีด้วย! คุณทำท่าทางถูกต้องตรงกับผู้สอนทุกท่า")
        else:
            st.write("### 🔍 จุดข้อต่อที่ควรปรับในแต่ละท่า")
            for idx, err_info in enumerate(error_frames, start=1):
                with st.expander(f"⚠️ ท่าที่ผิด #{idx} (ตรงกับท่าผู้สอน #{err_info['template_kf_id']})", expanded=(idx == 1)):
                    c_img, c_detail = st.columns(2)
                    with c_img:
                        st.image(err_info['image'], caption=f"เฟรมของคุณที่ #{err_info['user_frame_idx']}",
                                 use_container_width=True)
                    with c_detail:
                        st.write("**ข้อต่อที่คลาดเคลื่อนเกินเกณฑ์:**")
                        for side, j_id, j_name, dist in err_info['errors']:
                            st.error(f"• **[{side}]** {j_name} (ID: {j_id}) — ค่าความต่าง: `{dist:.3f}`")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔄 ลองทำคำนี้อีกครั้ง", type="primary", use_container_width=True):
            st.session_state.user_frames_data = []
            go("practice")
    with b2:
        if st.button("📚 เลือกคำอื่น", use_container_width=True):
            st.session_state.user_frames_data = []
            go("word")
