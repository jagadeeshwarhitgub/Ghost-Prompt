
import os
import tempfile
import streamlit as st
from scanner import scan_file

st.set_page_config(page_title="Ghost Prompt - AI Assistant", page_icon="👻", layout="wide")

RISK_THRESHOLD = 45  # >= this score -> block and require override

with st.sidebar:
    st.markdown("### 🔑 API Key")
    key_input = st.text_input(
        "Anthropic API key",
        type="password",
        value=st.session_state.get("api_key", os.environ.get("ANTHROPIC_API_KEY", "")),
        help="Pasted here for this session only — not saved to disk. "
             "Get one at console.anthropic.com/settings/keys",
    )
    st.session_state["api_key"] = key_input
    if key_input:
        st.success("Key set for this session.")
    else:
        st.warning("No key set — chat replies will fail until you add one.")

# ---------- Visual identity: glassmorphism SOC dashboard ----------
# Base: deep navy w/ blurred color blobs behind everything (the "glass" needs
# something colorful underneath it to actually read as glass)
# Accent: #22D3C5 (safe cyan) · #FF5D5D (threat red) · #F5A623 (warning amber)
# Type: Inter (UI) + JetBrains Mono (scores, findings, extracted text)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800;900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Centered, wider stage instead of edge-to-edge emptiness */
[data-testid="stAppViewContainer"] {
    background: #000000;
    color: #F1EEFB;
}

/* Static gradient background — no fixed/absolute elements, so it can
   never sit on top of content. */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 15% 0%, rgba(124,58,237,0.35) 0%, rgba(124,58,237,0) 50%),
        radial-gradient(circle at 85% 15%, rgba(255,62,157,0.22) 0%, rgba(255,62,157,0) 45%),
        linear-gradient(160deg, #241145 0%, #1a1030 45%, #0B0D18 100%);
    color: #F1EEFB;
}
[data-testid="stHeader"] { background: transparent; }

/* Hero: bubbles are CONTAINED inside this box (position:relative + overflow:hidden)
   so they can only ever decorate the hero — never float over the rest of the page. */
.hero {
    position: relative;
    overflow: hidden;
    text-align: center;
    padding: 48px 24px 44px 24px;
    border-radius: 28px;
    margin-bottom: 28px;
    background: #111111;
    border: 1px solid rgba(255,255,255,0.10);
}
.hero .bubble {
    position: absolute;
    border-radius: 50%;
    filter: blur(2px);
    opacity: 0.85;
    z-index: 0;
}
.hero .b1 { width: 90px; height: 90px; background: linear-gradient(135deg,#FF7A45,#FF3E9D); top: -20px; left: 8%; filter: blur(0px); }
.hero .b2 { width: 46px; height: 46px; background: linear-gradient(135deg,#22D3C5,#3EA8FF); bottom: 10px; left: 20%; }
.hero .b3 { width: 130px; height: 130px; background: radial-gradient(circle,#7C3AED,#3B1E80); top: -50px; right: 6%; filter: blur(4px); opacity: 0.6; }
.hero .b4 { width: 55px; height: 55px; background: linear-gradient(135deg,#FFB84D,#FF3E9D); bottom: -10px; right: 18%; }
.hero .badge, .hero h1, .hero p { position: relative; z-index: 1; }
.hero .badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.18);
    backdrop-filter: blur(10px);
    padding: 6px 16px; border-radius: 999px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; color: #FFD9A0; letter-spacing: 0.06em;
    margin-bottom: 18px;
}
.hero h1 {
    font-family: 'Playfair Display', serif !important;
    font-size: 3.2rem !important; font-weight: 800 !important;
    letter-spacing: -0.01em; margin-bottom: 6px !important;
    background: linear-gradient(135deg, #FFFFFF 20%, #FFB84D 60%, #FF3E9D 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p {
    color: #C9C2E0; font-size: 1.02rem; max-width: 560px; margin: 0 auto;
}

/* Glass panels: every card-like surface gets translucent blur */
[data-testid="stExpander"], .stFileUploader, [data-testid="stChatMessage"],
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #111111 !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    border-radius: 20px !important;
    backdrop-filter: blur(18px) saturate(150%);
    -webkit-backdrop-filter: blur(18px) saturate(150%);
    box-shadow: 0 8px 32px rgba(0,0,0,0.30);
}

.section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase;
    color: #6B7686; margin-bottom: 10px; display: block;
}

h3 {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important; letter-spacing: -0.01em;
}

/* Findings + extracted text panes */
[data-testid="stMarkdownContainer"] code {
    font-family: 'JetBrains Mono', monospace;
    background: rgba(34,211,197,0.12);
    color: #22D3C5;
    padding: 1px 6px; border-radius: 4px; font-size: 0.85em;
}
.stTextArea textarea, pre {
    font-family: 'JetBrains Mono', monospace !important;
    background: rgba(0,0,0,0.35) !important;
    color: #9FE8DF !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
}

.stCheckbox label, .stButton button { font-family: 'JetBrains Mono', monospace; }
div[data-baseweb="checkbox"] svg { fill: #22D3C5 !important; }
.stButton button {
    background: rgba(34,211,197,0.12) !important;
    border: 1px solid rgba(34,211,197,0.4) !important;
    border-radius: 10px !important;
    color: #9FE8DF !important;
}

[data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1.5px dashed rgba(255,255,255,0.18) !important;
    border-radius: 14px !important;
}

/* Chat input, glass style, pinned nicely */
[data-testid="stChatInput"] {
    background: transparent !important;
}
[data-testid="stChatInput"] textarea {
    background: #111111 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(12px);
    color: #E4E7EB !important;
}

[data-testid="stAlertContainer"] {
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', monospace; font-size: 0.88rem;
    backdrop-filter: blur(12px);
}

[data-testid="column"] { padding: 0 14px; }

/* Empty chat state filler so the left column doesn't look bare */
.empty-chat {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 320px; text-align: center; color: #4A5568;
    border: 1px dashed rgba(255,255,255,0.08); border-radius: 16px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
    background: rgba(255,255,255,0.02);
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <div class="bubble b1"></div>
    <div class="bubble b2"></div>
    <div class="bubble b3"></div>
    <div class="bubble b4"></div>
    <div class="badge">👻 &nbsp; AI DOCUMENT FIREWALL</div>
    <h1>Ghost Prompt</h1>
    <p>Every file is scanned for hidden instructions before it ever reaches the assistant.</p>
</div>
""", unsafe_allow_html=True)

from groq import Groq

API_KEY = "key"   # Replace with your NEW key

def call_llm(user_prompt, context_text, context_label="document content"):
    """
    Sends the user's question and the safe document context to Groq.
    """

    try:
        client = Groq(api_key="key")

        system = (
            "You are a helpful assistant embedded in a company document tool. "
            f"Answer the user's question using only the {context_label} provided below. "
            "If the context doesn't contain enough information to answer, say so plainly. "
            "Be concise and directly address what was actually asked."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system,
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context_text}\n\nQuestion:\n{user_prompt}",
                },
            ],
            temperature=0.7,
            max_completion_tokens=1000,
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error: {e}"
# ---------- session state ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_override" not in st.session_state:
    st.session_state.pending_override = None

col1, col2 = st.columns([2, 1])

with col2:
    st.markdown('<span class="section-label">Upload a document</span>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF only (demo)", type=["pdf"])
    scan_result = None

    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        with st.spinner("Scanning document for hidden instructions..."):
            scan_result = scan_file(tmp_path)

        level = scan_result["risk_level"]
        score = scan_result["risk_score"]
        hex_color = {"Low": "#22D3C5", "Medium": "#F5A623", "High": "#FF5D5D", "Critical": "#FF3B3B"}[level]

        st.markdown(
            f"""<div style="background:#131A24;border:1px solid {hex_color};border-radius:10px;
                        padding:14px 18px;margin:6px 0 14px 0;">
                  <span style="font-family:'JetBrains Mono',monospace;color:#6B7686;font-size:0.75rem;
                        letter-spacing:0.08em;text-transform:uppercase;">Risk Level</span><br>
                  <span style="font-family:'JetBrains Mono',monospace;color:{hex_color};
                        font-size:1.6rem;font-weight:700;">{level}</span>
                  <span style="font-family:'JetBrains Mono',monospace;color:#6B7686;
                        font-size:1rem;"> &nbsp;{score}/100</span>
                </div>""",
            unsafe_allow_html=True,
        )

        if scan_result["findings"]:
            st.markdown("**Findings:**")
            for f in scan_result["findings"]:
                st.markdown(f"- `{f['type']}` — {f['detail']}")
        else:
            st.success("No hidden instructions detected.")

        st.markdown(
            '<div style="margin-top:22px;margin-bottom:10px;">'
            '<span style="font-family:\'Playfair Display\',serif;font-size:1.3rem;'
            'font-weight:700;color:#FFD9A0;">👁️ Human View vs. AI View</span><br>'
            '<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.78rem;color:#9B93B5;">'
            'What you see when you open the file, vs. what the AI actually reads</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        import html as _html
        raw_html = _html.escape(scan_result["raw_text"])
        for seg in scan_result.get("hidden_segments", []):
            seg_esc = _html.escape(seg)
            if seg_esc and seg_esc in raw_html:
                raw_html = raw_html.replace(
                    seg_esc,
                    f'<mark style="background:rgba(255,62,157,0.35);color:#FF9EC9;'
                    f'padding:1px 3px;border-radius:3px;">{seg_esc}</mark>',
                    1,
                )

        hv, av = st.columns(2)
        with hv:
            st.markdown(
                '<span class="section-label">🧑 What a human sees</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:rgba(0,0,0,0.30);border:1px solid rgba(255,255,255,0.10);'
                f'border-radius:14px;padding:14px 16px;font-family:\'JetBrains Mono\',monospace;'
                f'font-size:0.82rem;color:#E4E7EB;max-height:280px;overflow-y:auto;white-space:pre-wrap;">'
                f'{_html.escape(scan_result["clean_text"][:2000]) or "(nothing visible)"}</div>',
                unsafe_allow_html=True,
            )
        with av:
            st.markdown(
                '<span class="section-label">👻 What the AI would read</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:rgba(0,0,0,0.30);border:1px solid rgba(255,62,157,0.30);'
                f'border-radius:14px;padding:14px 16px;font-family:\'JetBrains Mono\',monospace;'
                f'font-size:0.82rem;color:#E4E7EB;max-height:280px;overflow-y:auto;white-space:pre-wrap;">'
                f'{raw_html[:3000]}</div>',
                unsafe_allow_html=True,
            )

        if score >= RISK_THRESHOLD:
            st.error("🚫 This document is BLOCKED from reaching the AI assistant.")
            allow_override = st.checkbox("I have manually reviewed this and want to proceed anyway (not recommended)")
            if allow_override:
                st.session_state.pending_override = scan_result
            else:
                st.session_state.pending_override = None
        else:
            st.session_state.pending_override = scan_result

with col1:
    st.markdown('<span class="section-label">Chat</span>', unsafe_allow_html=True)
    if not st.session_state.messages:
        st.markdown(
            '<div class="empty-chat">📄 &nbsp; Upload a document on the right, then ask a question here.</div>',
            unsafe_allow_html=True,
        )
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("Ask about the uploaded document...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            if uploaded is None:
                reply = "Please upload a document first."
            elif scan_result and scan_result["risk_score"] >= RISK_THRESHOLD and not st.session_state.pending_override:
                # BLOCKED: don't send raw hidden text to the LLM, but DO let it
                # answer the user's actual question using only the scanner's
                # findings — this is safe (we generated it) and keeps replies relevant.
                findings_summary = "\n".join(
                    f"- [{f['type']}] {f['detail']}" for f in scan_result["findings"]
                ) or "No specific findings recorded."
                safety_context = (
                    f"Risk level: {scan_result['risk_level']} ({scan_result['risk_score']}/100)\n"
                    f"This document was BLOCKED from full processing because it contains hidden "
                    f"instructions not visible to a human reader. It has NOT been summarized or "
                    f"acted on. Findings from the security scan:\n{findings_summary}"
                )
                reply = call_llm(prompt, safety_context, context_label="security scan findings")
            else:
                # ALLOWED: only clean_text (visible-only) is ever sent to the LLM
                safe_text = scan_result["clean_text"] if scan_result else ""
                reply = call_llm(prompt, safe_text, context_label="document content")
            st.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
