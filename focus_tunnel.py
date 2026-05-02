import streamlit as st
import fitz  # PyMuPDF: PDF処理用
from PIL import Image
import io

# アプリの基本設定
st.set_page_config(page_title="Focus Tunnel (Retry Mode)", layout="wide")

# カスタムCSS
st.markdown("""
    <style>
    .main .block-container {
        max-width: 1000px;
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    [data-testid="stImage"] img {
        width: 100% !important;
        border-radius: 8px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }

    div.stButton > button:first-child {
        background-color: #1b5e20 !important;
        color: white !important;
        border: 2px solid #2e7d32;
    }
    div.stButton > button:last-child {
        background-color: #b71c1c !important;
        color: white !important;
        border: 2px solid #d32f2f;
    }
    .stButton button {
        width: 100%;
        height: 4em;
        font-weight: bold;
        border-radius: 12px;
        font-size: 1.1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-top: 0.5rem;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: #0e1117;
    }
    
    @media (max-width: 640px) {
        .main .block-container {
            padding: 0.5rem;
        }
        .stButton button {
            height: 4.5em;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def initialize_session():
    if 'current_pages' not in st.session_state:
        st.session_state.current_pages = []
    if 'retry_pages' not in st.session_state:
        st.session_state.retry_pages = []
    if 'total_in_round' not in st.session_state:
        st.session_state.total_in_round = 0
    if 'round_count' not in st.session_state:
        st.session_state.round_count = 1
    if 'started' not in st.session_state:
        st.session_state.started = False

def process_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    images = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_data = pix.tobytes("png")
        images.append(img_data)
    return images

initialize_session()

if not st.session_state.started:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.title("Focus Tunnel 🚀")
        st.markdown("### 「戻れない」からこそ、今に集中できる。")
        st.info("わかるものは「削除」、わからないものは「保留」して追い込みましょう。")
        
        uploaded_file = st.file_uploader("勉強用PDFをアップロード", type="pdf")
        
        if uploaded_file is not None:
            if st.button("学習を開始する"):
                with st.spinner("PDFを高解像度で展開中..."):
                    images = process_pdf(uploaded_file)
                    st.session_state.current_pages = images
                    st.session_state.retry_pages = []
                    st.session_state.total_in_round = len(images)
                    st.session_state.round_count = 1
                    st.session_state.started = True
                st.rerun()

else:
    if len(st.session_state.current_pages) > 0:
        _, content_col, _ = st.columns([0.02, 0.96, 0.02])
        
        with content_col:
            current_num = st.session_state.total_in_round - len(st.session_state.current_pages) + 1
            st.markdown(f"**ROUND {st.session_state.round_count}** | PAGE {current_num} / {st.session_state.total_in_round}")
            st.progress(current_num / st.session_state.total_in_round)
            
            current_page_data = st.session_state.current_pages[0]
            image = Image.open(io.BytesIO(current_page_data))
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
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            if len(st.session_state.retry_pages) > 0:
                st.balloons()
                st.success(f"第 {st.session_state.round_count} 段階が終了しました！")
                st.warning(f"復習が必要なページが {len(st.session_state.retry_pages)} 枚あります。")
                
                if st.button("保留ページのみで次の周回を開始 ➔"):
                    st.session_state.current_pages = st.session_state.retry_pages.copy()
                    st.session_state.retry_pages = []
                    st.session_state.total_in_round = len(st.session_state.current_pages)
                    st.session_state.round_count += 1
                    st.rerun()
                    
                if st.button("ここで終了してリセット"):
                    st.session_state.started = False
                    st.rerun()
            else:
                st.balloons()
                st.success("🎉 全てクリアしました！")
                if st.button("新しいPDFを読み込む"):
                    st.session_state.started = False
                    st.rerun()