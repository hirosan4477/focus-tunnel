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
        return None

# アプリの基本設定
st.set_page_config(page_title="Focus Tunnel (Persistence)", layout="wide")

# アプリIDとユーザーIDの設定
# パスルール: /artifacts/{appId}/users/{userId}/{collectionName}/{docId}
APP_ID = "focus-tunnel-v1" 
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

def get_progress_doc():
    """Firestoreのドキュメント参照を取得"""
    if not db:
        return None
    return db.collection("artifacts").document(APP_ID).collection("users").document(USER_ID).collection("progress").document("current")

def save_progress():
    """現在の進捗をFirestoreに保存"""
    if st.session_state.get('started'):
        doc_ref = get_progress_doc()
        if doc_ref:
            try:
                doc_ref.set({
                    "round_count": st.session_state.round_count,
                    "total_in_round": st.session_state.total_in_round,
                    "current_index": st.session_state.current_index,
                    "started": True
                })
            except Exception as e:
                print(f"Firestore Save Error: {e}")

def load_progress_from_db():
    """Firestoreから進捗を読み込む"""
    doc_ref = get_progress_doc()
    if doc_ref:
        try:
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            print(f"Firestore Load Error: {e}")
    return None

# セッション状態の初期化と復元
if 'started' not in st.session_state:
    # 最初にDBからデータを取得
    db_progress = load_progress_from_db()
    
    if db_progress and db_progress.get('started'):
        st.session_state.round_count = db_progress.get('round_count', 1)
        st.session_state.total_in_round = db_progress.get('total_in_round', 0)
        st.session_state.current_index = db_progress.get('current_index', 0)
        st.session_state.started = True
    else:
        st.session_state.started = False
        st.session_state.round_count = 1
        st.session_state.total_in_round = 0
        st.session_state.current_index = 0

if 'current_pages' not in st.session_state:
    st.session_state.current_pages = []
if 'retry_pages' not in st.session_state:
    st.session_state.retry_pages = []

# --- メインロジック ---
if not st.session_state.started:
    st.title("Focus Tunnel 🚀")
    st.markdown("### 進捗保存モード")
    
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
                st.session_state.total_in_round = len(images)
                st.session_state.round_count = 1
                st.session_state.current_index = 0
                st.session_state.started = True
                save_progress()
                st.rerun()
else:
    # メモリから画像が消えている（再起動や長時間放置）場合の処理
    if not st.session_state.current_pages:
        st.warning("セッションがリセットされました。進捗を再開するにはPDFを再度選択してください。")
        re_upload = st.file_uploader("同じPDFを再選択", type="pdf", key="reupload")
        if re_upload:
            with st.spinner("PDFを再構築中..."):
                doc = fitz.open(stream=re_upload.read(), filetype="pdf")
                all_images = []
                for i in range(len(doc)):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    all_images.append(pix.tobytes("png"))
                
                # 保存されたインデックスから残りのページを復元
                idx = st.session_state.current_index
                st.session_state.current_pages = all_images[idx:]
                st.rerun()
        
        if st.button("進捗を破棄して最初から"):
            doc_ref = get_progress_doc()
            if doc_ref:
                doc_ref.delete()
            st.session_state.clear()
            st.rerun()
        st.stop()

    # 学習画面
    if len(st.session_state.current_pages) > 0:
        # 現在表示しているページ番号を計算
        current_display_num = st.session_state.current_index + 1
        st.markdown(f"**ROUND {st.session_state.round_count}** | PAGE {current_display_num} / {st.session_state.total_in_round}")
        st.progress(min(current_display_num / st.session_state.total_in_round, 1.0))
        
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
                # 保留分をメモリ内に保持（周回用）
                st.session_state.retry_pages.append(st.session_state.current_pages.pop(0))
                st.session_state.current_index += 1
                save_progress()
                st.rerun()
    else:
        st.balloons()
        st.success("この周回が終了しました！")
        if st.button("最初からリセット"):
            doc_ref = get_progress_doc()
            if doc_ref:
                doc_ref.delete()
            st.session_state.clear()
            st.rerun()
