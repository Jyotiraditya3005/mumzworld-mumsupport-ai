"""
app.py — MumzSupport AI: Streamlit demo interface
Run with: streamlit run app.py
"""

import streamlit as st
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.classifier import classify_email

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MumzSupport AI",
    page_icon="🍼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display:ital@0;1&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    h1, h2, h3 {
        font-family: 'DM Serif Display', serif;
    }

    .main { background: #faf8f5; }

    .intent-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-refund     { background: #fde8e8; color: #c0392b; }
    .badge-exchange   { background: #e8f4fd; color: #2471a3; }
    .badge-complaint  { background: #fef9e7; color: #b7950b; }
    .badge-query      { background: #e9f7ef; color: #1e8449; }
    .badge-unknown    { background: #f2f3f4; color: #7f8c8d; }

    .urgency-high   { color: #e74c3c; font-weight: 700; }
    .urgency-medium { color: #e67e22; font-weight: 600; }
    .urgency-low    { color: #27ae60; font-weight: 600; }
    .urgency-unknown{ color: #95a5a6; font-weight: 500; }

    .reply-box {
        background: white;
        border: 1px solid #e8e4df;
        border-radius: 12px;
        padding: 18px 22px;
        font-size: 14.5px;
        line-height: 1.7;
        margin-top: 8px;
    }

    .escalation-warning {
        background: #fdedec;
        border-left: 4px solid #e74c3c;
        border-radius: 6px;
        padding: 12px 16px;
        margin-top: 12px;
        font-weight: 500;
        color: #922b21;
    }

    .uncertainty-note {
        background: #fef9e7;
        border-left: 4px solid #f39c12;
        border-radius: 6px;
        padding: 10px 14px;
        margin-top: 10px;
        font-size: 13px;
        color: #7d6608;
    }

    .confidence-bar-wrap {
        background: #efefef;
        border-radius: 10px;
        height: 8px;
        margin-top: 4px;
        overflow: hidden;
    }
    .confidence-bar-fill {
        height: 100%;
        border-radius: 10px;
        background: linear-gradient(90deg, #f5a623, #3498db);
    }

    .stTextArea textarea {
        border-radius: 10px !important;
        border: 1.5px solid #ddd6cc !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 14.5px !important;
    }

    div.stButton > button {
        background: #2c3e50;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 28px;
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 15px;
        cursor: pointer;
        transition: background 0.2s;
    }
    div.stButton > button:hover {
        background: #1a252f;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    api_key = st.text_input(
        "OpenRouter API Key",
        type="password",
        value=os.environ.get("OPENROUTER_API_KEY", ""),
        help="Get a free key at openrouter.ai"
    )

    model_options = {
        "Llama 3.3 70B (free)": "meta-llama/llama-3.3-70b-instruct:free",
        "DeepSeek R1 (free)": "deepseek/deepseek-r1:free",
        "Qwen 2.5 72B (free)": "qwen/qwen-2.5-72b-instruct:free",
        "Mistral 7B (free)": "mistralai/mistral-7b-instruct:free",
    }
    model_label = st.selectbox("Model", list(model_options.keys()))
    selected_model = model_options[model_label]

    st.markdown("---")
    st.markdown("### 📌 About")
    st.markdown("""
**MumzSupport AI** classifies customer support emails for Mumzworld into:
- **Intent**: refund / exchange / complaint / query / unknown
- **Urgency**: high / medium / low
- **Confidence score**
- **Reply** in English + Arabic
- **Escalation flag** for critical cases
    """)

    st.markdown("---")
    st.markdown("### 🧪 Load Test Case")
    tc_path = Path(__file__).parent / "data" / "test_emails.json"
    if tc_path.exists():
        test_cases = json.loads(tc_path.read_text())
        tc_options = {f"{tc['id']} — {tc['label']} ({tc['expected_intent']})": tc for tc in test_cases}
        selected_tc = st.selectbox("Pick a test case", ["(none)"] + list(tc_options.keys()))
    else:
        selected_tc = "(none)"
        tc_options = {}


# ─── Main UI ─────────────────────────────────────────────────────────────────

st.markdown("# 🍼 MumzSupport AI")
st.markdown("#### Customer Support Email Classifier — *Mumzworld Intern Assessment, Track A*")
st.markdown("---")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("### ✉️ Input Email")

    # Pre-fill from test case if selected
    prefill = ""
    if selected_tc != "(none)" and selected_tc in tc_options:
        prefill = tc_options[selected_tc]["email"]
        st.info(f"**Expected:** intent=`{tc_options[selected_tc]['expected_intent']}`, urgency=`{tc_options[selected_tc]['expected_urgency']}`  \n*{tc_options[selected_tc]['notes']}*")

    email_input = st.text_area(
        "Paste customer email here",
        value=prefill,
        height=240,
        placeholder="e.g. Hi, I received the wrong item in my order #MW-1234. I want a refund..."
    )

    run_btn = st.button("🔍 Classify & Generate Reply")

    st.markdown("---")
    st.markdown("**Try these examples:**")
    examples = [
        ("🔴 Safety critical", "The baby formula I received expired in January 2024. My 3-month-old has been drinking it for two days. I'm extremely worried. Please help urgently."),
        ("🔁 Exchange", "Hi, I ordered the Ergobaby carrier in Navy but I'd prefer Dusty Pink. Can I swap it? Still in original packaging."),
        ("❓ Ambiguous", "hi"),
        ("🌍 Arabic", "السلام عليكم، طلبت منتج من أسبوعين ولسه ما وصل. ممكن تساعدوني أعرف وين الطلب؟"),
        ("😡 Escalation threat", "I'm going to post about this on Instagram and tell all my followers never to shop here unless you resolve my missing order TODAY."),
    ]
    for label, txt in examples:
        if st.button(label, key=f"ex_{label}"):
            st.session_state["quick_email"] = txt
            st.rerun()

    if "quick_email" in st.session_state:
        email_input = st.session_state.pop("quick_email")


with col2:
    st.markdown("### 📊 Classification Result")

    if run_btn or ("pending_email" in st.session_state):
        to_classify = email_input or st.session_state.pop("pending_email", "")

        if not api_key:
            st.error("❌ Please enter your OpenRouter API key in the sidebar.")
        elif not to_classify.strip():
            st.warning("Please enter an email to classify.")
        else:
            with st.spinner("Classifying..."):
                try:
                    result = classify_email(to_classify, api_key, selected_model)

                    # Intent badge
                    badge_class = f"badge-{result.intent}"
                    st.markdown(f"""
                    <div style="margin-bottom:12px">
                      <span class="intent-badge {badge_class}">{result.intent.upper()}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Metrics row
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        urg_class = f"urgency-{result.urgency}"
                        st.markdown(f"**Urgency**  \n<span class='{urg_class}'>{result.urgency.upper()}</span>", unsafe_allow_html=True)
                    with m2:
                        conf_pct = int(result.confidence * 100)
                        st.markdown(f"**Confidence**  \n`{conf_pct}%`")
                        st.markdown(f"""<div class="confidence-bar-wrap"><div class="confidence-bar-fill" style="width:{conf_pct}%"></div></div>""", unsafe_allow_html=True)
                    with m3:
                        esc_icon = "🚨 YES" if result.needs_escalation else "✅ NO"
                        st.markdown(f"**Escalate?**  \n{esc_icon}")

                    st.markdown(f"*{result.reasoning}*", unsafe_allow_html=False)

                    if result.needs_escalation:
                        st.markdown("""<div class="escalation-warning">⚠️ This ticket has been flagged for immediate human review.</div>""", unsafe_allow_html=True)

                    if result.uncertainty_note:
                        st.markdown(f"""<div class="uncertainty-note">💬 <b>Uncertainty note:</b> {result.uncertainty_note}</div>""", unsafe_allow_html=True)

                    st.markdown("---")

                    tab1, tab2, tab3 = st.tabs(["🇬🇧 English Reply", "🇸🇦 Arabic Reply", "🔧 Raw JSON"])

                    with tab1:
                        st.markdown(f'<div class="reply-box">{result.reply_en}</div>', unsafe_allow_html=True)
                        st.download_button("📋 Copy EN reply", result.reply_en, file_name="reply_en.txt")

                    with tab2:
                        st.markdown(f'<div class="reply-box" dir="rtl" style="text-align:right; font-size:15px;">{result.reply_ar}</div>', unsafe_allow_html=True)
                        st.download_button("📋 Copy AR reply", result.reply_ar, file_name="reply_ar.txt")

                    with tab3:
                        st.json(result.model_dump())

                except ValueError as e:
                    st.error(f"Configuration error: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
    else:
        st.markdown("""
        <div style="background: #f0ece6; border-radius: 12px; padding: 40px 30px; text-align: center; color: #7a6f62; margin-top: 20px;">
            <div style="font-size: 48px; margin-bottom: 12px;">📬</div>
            <div style="font-size: 16px; font-weight: 500;">Paste an email and click <b>Classify</b></div>
            <div style="font-size: 13px; margin-top: 8px;">Results will appear here</div>
        </div>
        """, unsafe_allow_html=True)


# ─── Footer ──────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#aaa; font-size:12px;'>MumzSupport AI · Mumzworld AI-Native Intern Assessment · Track A · Built with OpenRouter + Llama 3.3 70B</div>",
    unsafe_allow_html=True
)
