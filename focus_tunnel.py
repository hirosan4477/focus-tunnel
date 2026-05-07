import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import json
from google.oauth2 import service_account
from google.cloud import firestore

# --- Firebase初期化設定 ---
def get_db():
    if "firebase" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["firebase"]["key"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds, project=key_dict["project_id"])
        except Exception as e:
            st.error(f"Firebase接続エラー: {e}")
            return None
    else:
        st.error("FirebaseのSecrets設定が見つかりません。")
        return None

# アプリの基本設定
st.set_page_config(page_title="Focus Tunnel (Persistence)", layout="wide")

# アプリIDとユーザーIDの設定
APP_ID = "focus-tunnel-app"
USER_ID = "default_user"

# カスタムCSS
st.markdown("""
    <style>
    .main .block-container { max-width: 1000px; padding: 1rem; }
    [data-testid="stImage"] img { width: 100% !important; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
    div.stButton > button:first-child { background-color: #1b5e20 !important; color: white !important; }
    div.stButton > button:last-child { background-color: #b71c1c !important; color: white !important; }
    .stButton button { width: 100%; height: 4em; font-weight: bold; border-radius: 12px; margin-top: 0.5rem; }
    #MainMenu, footer, header { visibility: hidden; }
    .stApp { background-color: #0e1117; }
    </style>
    """, unsafe_allow_html=True)

db = get_db()

def save_progress():
    """現在の進捗をFirestoreに保存"""
    if db and st.session_state.get('started'):
        # 画像データそのものは大きすぎるため、インデックス（残りのページ番号）を保存
        # PDF自体はセッション中のみ保持されます
        doc_ref = db.collection("artifacts").document(APP_ID).collection("users").document(USER_ID).collection("progress").document("current")
        doc_ref.set({
            "round_count": st.session_state.round_count,
            "total_in_round": st.session_state.total_in_round,
            "current_index": st.session_state.current_index,
            "started": True
        })

def load_progress_from_db():
    """Firestoreから進捗を復元"""
    if db:
        doc_ref = db.collection("artifacts").document(APP_ID).collection("users").document(USER_ID).collection("progress").document("current")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
    return None

# セッション状態の初期化
if 'started' not in st.session_state:
    progress = load_progress_from_db()
    if progress and progress.get('started'):
        st.session_state.round_count = progress['round_count']
        st.session_state.total_in_round = progress['total_in_round']
        st.session_state.current_index = progress['current_index']
        st.session_state.started = True
    else:
        st.session_state.started = False
        st.session_state.current_pages = []
        st.session_state.retry_pages = []
        st.session_state.current_index = 0

# --- メインロジック ---
if not st.session_state.started:
    st.title("Focus Tunnel 🚀")
    st.markdown("### データを保存する準備が整いました")
    
    uploaded_file = st.file_uploader("PDFをアップロードして開始", type="pdf")
    
    if uploaded_file:
        if st.button("学習を開始する"):
            with st.spinner("PDFを読み込み中..."):
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                images = []
                for i in range(len(doc)):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    images.append(pix.tobytes("png"))
                
                st.session_state.current_pages = images
                st.session_state.retry_pages = []
                st.session_state.total_in_round = len(images)
                st.session_state.round_count = 1
                st.session_state.current_index = 0
                st.session_state.started = True
                save_progress()
                st.rerun()
else:
    # PDFデータがメモリから消えている場合は再アップロードを促す（無料版の制限）
    if not st.session_state.get('current_pages'):
        st.warning("接続が切れました。同じPDFを再度選択してください。進捗（ページ数）は維持されています。")
        re_upload = st.file_uploader("同じPDFを再選択", type="pdf", key="reupload")
        if re_upload:
            doc = fitz.open(stream=re_upload.read(), filetype="pdf")
            images = []
            for i in range(len(doc)):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                images.append(pix.tobytes("png"))
            st.session_state.current_pages = images[st.session_state.current_index:]
            st.rerun()
        if st.button("最初からやり直す"):
            st.session_state.started = False
            if db:
                db.collection("artifacts").document(APP_ID).collection("users").document(USER_ID).collection("progress").document("current").delete()
            st.rerun()
        st.stop()

    # 学習メイン画面
    if len(st.session_state.current_pages) > 0:
        current_num = st.session_state.total_in_round - len(st.session_state.current_pages) + 1
        st.markdown(f"**ROUND {st.session_state.round_count}** | PAGE {current_num} / {st.session_state.total_in_round}")
        st.progress(current_num / st.session_state.total_in_round)
        
        image = Image.open(io.BytesIO(st.session_state.current_pages[0]))
        st.image(image, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("理解した (削除)"):
                st.session_state.current_pages.pop(0)
                st.session_state.current_index += 1
                save_progress()
                st.rerun()
        with col2:
            if st.button("不安 (保留)"):
                # 今回は簡略化のため、保留も「次へ」進むが、リストには残すロジック
                # （本来は別コレクションに保存して周回させる）
                page_data = st.session_state.current_pages.pop(0)
                st.session_state.retry_pages.append(page_data)
                st.session_state.current_index += 1
                save_progress()
                st.rerun()
    else:
        st.balloons()
        st.success("この周回が終了しました！")
        if st.button("進捗をリセットして最初から"):
            st.session_state.started = False
            if db:
                db.collection("artifacts").document(APP_ID).collection("users").document(USER_ID).collection("progress").document("current").delete()
            st.rerun()
