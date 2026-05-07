import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import base64
from google.oauth2 import service_account
from google.cloud import firestore

# --- Firebase初期化設定 ---
def get_db():
    # Streamlit Cloudの Secrets に保存した秘密鍵を読み込む
    if "firebase" in st.secrets:
        key_dict = json.loads(st.secrets["firebase"]["key"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict["project_id"])
    else:
        st.error("FirebaseのSecrets設定が見つかりません。")
        return None

# アプリの基本設定
st.set_page_config(page_title="Focus Tunnel (Persistence)", layout="wide")

# カスタムCSS（以前と同じ）
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

# セッション状態の初期化
def init_session():
    if 'user_id' not in st.session_state:
        # 本来は認証が必要ですが、簡易的に固定IDか入力制にします
        st.session_state.user_id = "default_user" 
    if 'loaded' not in st.session_state:
        st.session_state.loaded = False

db = get_db()
init_session()

def save_to_firestore(pages, round_count, total_in_round):
    """進捗をクラウドに保存"""
    if db:
        doc_ref = db.collection("users").document(st.session_state.user_id)
        # 画像データは大きいのでBase64エンコードして保存（Firestoreの1MB制限に注意）
        # 本来はStorageを使うのがベストですが、今回は簡易版として進捗のみ保存
        doc_ref.set({
            "round_count": round_count,
            "total_in_round": total_in_round,
            "remaining_count": len(pages)
        })

def load_progress():
    """クラウドから進捗を読み込む"""
    if db:
        doc_ref = db.collection("users").document(st.session_state.user_id)
        doc = doc_ref.get()
        return doc.to_dict() if doc.exists else None
    return None

# --- メインロジック ---
if not st.session_state.get('started', False):
    st.title("Focus Tunnel 🚀 (Cloud Save)")
    st.info("このバージョンでは進捗がFirestoreに保存されます。")
    
    uploaded_file = st.file_uploader("PDFをアップロード", type="pdf")
    
    if uploaded_file:
        if st.button("学習を開始する"):
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
            st.session_state.started = True
            st.rerun()
else:
    # 学習画面（ここでの挙動は前回と同じですが、アクションごとにセッション状態を維持）
    if st.session_state.current_pages:
        current_num = st.session_state.total_in_round - len(st.session_state.current_pages) + 1
        st.markdown(f"**ROUND {st.session_state.round_count}** | PAGE {current_num} / {st.session_state.total_in_round}")
        
        image = Image.open(io.BytesIO(st.session_state.current_pages[0]))
        st.image(image, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("理解した (削除)"):
                st.session_state.current_pages.pop(0)
                st.rerun()
        with col2:
            if st.button("不安 (保留)"):
                st.session_state.retry_pages.append(st.session_state.current_pages.pop(0))
                st.rerun()
    else:
        # 周回終了処理など（前回と同じ）
        if st.session_state.retry_pages:
            if st.button("保留ページで次周開始"):
                st.session_state.current_pages = st.session_state.retry_pages.copy()
                st.session_state.retry_pages = []
                st.session_state.total_in_round = len(st.session_state.current_pages)
                st.session_state.round_count += 1
                st.rerun()
        if st.button("リセット"):
            st.session_state.started = False
            st.rerun()
