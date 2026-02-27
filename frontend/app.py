"""
🛡️ ResumeGuard — AI-Based Resume Fraud Detection Dashboard
Main Streamlit Application

Premium dark-theme UI with glassmorphism, animated risk gauges,
signal breakdown, AI explanations, batch analysis, and fraud network graph.
"""
import streamlit as st
import requests
import json
import time
import os
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from styles import inject_css

# ─── Page Config ─────────────────────────────────────────
st.set_page_config(
    page_title="Resume — Sentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ─── Config ──────────────────────────────────────────────
API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")


# ─── Utility Functions ───────────────────────────────────

def get_risk_color(score):
    if score >= 85: return "#ef5350"
    elif score >= 65: return "#ff7043"
    elif score >= 40: return "#ffa726"
    elif score >= 20: return "#66bb6a"
    return "#4fc3f7"

def get_risk_gradient(score):
    if score >= 85: return "linear-gradient(135deg, #ff512f 0%, #dd2476 100%)"
    elif score >= 65: return "linear-gradient(135deg, #ff7043 0%, #ff5722 100%)"
    elif score >= 40: return "linear-gradient(135deg, #ffa726 0%, #ff9800 100%)"
    elif score >= 20: return "linear-gradient(135deg, #66bb6a 0%, #4caf50 100%)"
    return "linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%)"

def get_severity_color(severity):
    return {
        "CRITICAL": "#ef5350",
        "HIGH": "#ff7043",
        "MEDIUM": "#ffa726",
        "LOW": "#66bb6a",
        "NONE": "#4fc3f7",
    }.get(severity, "#9e9e9e")

def create_gauge_chart(score, title="Risk Score"):
    """Create a beautiful donut gauge chart."""
    color = get_risk_color(score)
    
    fig = go.Figure(go.Pie(
        values=[score, 100 - score],
        hole=0.75,
        marker=dict(
            colors=[color, "rgba(255,255,255,0.05)"],
            line=dict(width=0)
        ),
        textinfo="none",
        hoverinfo="none",
        direction="clockwise",
        sort=False,
    ))
    
    fig.update_layout(
        showlegend=False,
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=250,
        width=250,
        annotations=[
            dict(
                text=f"<b>{score}</b>",
                x=0.5, y=0.55,
                font=dict(size=48, color=color, family="Inter"),
                showarrow=False,
            ),
            dict(
                text=title,
                x=0.5, y=0.35,
                font=dict(size=14, color="#9e9e9e", family="Inter"),
                showarrow=False,
            ),
        ],
    )
    return fig


def create_signal_radar(signals):
    """Create a radar chart of signal scores."""
    categories = ["Timeline", "Email", "Phone", "Plagiarism", "Similarity", "Mismatch"]
    max_scores = [40, 20, 15, 30, 35, 20]
    values = [
        signals.get("timeline_score", 0),
        signals.get("email_score", 0),
        signals.get("phone_score", 0),
        signals.get("plagiarism_score", 0),
        signals.get("similarity_score", 0),
        signals.get("mismatch_score", 0),
    ]
    # Normalize to percentage
    normalized = [round((v / m) * 100, 1) if m > 0 else 0 for v, m in zip(values, max_scores)]
    normalized.append(normalized[0])  # Close the polygon
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=normalized,
        theta=categories,
        fill="toself",
        fillcolor="rgba(79, 195, 247, 0.15)",
        line=dict(color="#4fc3f7", width=2),
        marker=dict(size=6, color="#4fc3f7"),
    ))

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="rgba(255,255,255,0.08)",
                linecolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#9e9e9e", size=10),
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                linecolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#e0e0e0", size=12),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=30, l=60, r=60),
        height=350,
        showlegend=False,
    )
    return fig


def create_signal_bar(signals):
    """Create horizontal bar chart of signal scores."""
    names = ["Timeline", "Email", "Phone", "Plagiarism", "Similarity", "Mismatch"]
    max_vals = [40, 20, 15, 30, 35, 20]
    values = [
        signals.get("timeline_score", 0),
        signals.get("email_score", 0),
        signals.get("phone_score", 0),
        signals.get("plagiarism_score", 0),
        signals.get("similarity_score", 0),
        signals.get("mismatch_score", 0),
    ]
    colors = [get_risk_color((v / m) * 100) if m > 0 else "#4fc3f7" for v, m in zip(values, max_vals)]

    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v}/{m}" for v, m in zip(values, max_vals)],
        textposition="auto",
        textfont=dict(color="white", size=12),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            tickfont=dict(color="#9e9e9e"),
            title="",
        ),
        yaxis=dict(
            tickfont=dict(color="#e0e0e0", size=13),
        ),
    )
    return fig


# ─── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0;">
        <p style="font-size: 3rem; margin: 0;">🛡️</p>
        <h2 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                    font-weight: 800; margin: 0;">ResumeSentinel</h2>
        <p style="color: #9e9e9e; font-size: 0.85rem;">AI-Powered Fraud Detection</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigation",
        ["🔍 Analyze Resume", "📊 Batch Analysis", "🆚 Compare Resumes", "📈 Dashboard"],
        label_visibility="collapsed",
    )

    st.divider()

    # API Status
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        if r.status_code == 200:
            st.markdown("🟢 **API Status**: Connected")
        else:
            st.markdown("🟡 **API Status**: Degraded")
    except:
        st.markdown("🔴 **API Status**: Offline")
        st.caption("Start the backend: `python main.py`")

    st.divider()
    st.caption("Built for HackWith AI 2026")
    st.caption("Hybrid Architecture: Python + Spring Boot")


# ─── Page: Analyze Resume ────────────────────────────────
if page == "🔍 Analyze Resume":
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ Resume Fraud Detection</h1>
        <p>Upload a resume to analyze it across 6 AI-powered fraud detection signals</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop your resume here",
        type=["pdf", "docx", "txt"],
        help="Supported: PDF, DOCX, TXT — Max 10MB",
        key="single_upload",
    )

    if uploaded:
        with st.spinner("🔬 Analyzing resume across 6 fraud signals..."):
            try:
                progress = st.progress(0, text="Initializing analysis...")
                
                progress.progress(10, text="📄 Parsing document...")
                time.sleep(0.3)
                
                progress.progress(30, text="🔍 Extracting entities...")
                time.sleep(0.2)
                
                progress.progress(50, text="🧠 Running ML signals...")
                
                res = requests.post(
                    f"{API_URL}/validate_resume",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")},
                    timeout=120,
                )
                
                progress.progress(80, text="📊 Calculating risk score...")
                time.sleep(0.3)
                
                progress.progress(100, text="✅ Analysis complete!")
                time.sleep(0.3)
                progress.empty()

                if res.status_code != 200:
                    st.error(f"Analysis failed: {res.text}")
                    st.stop()

                data = res.json()

            except requests.ConnectionError:
                st.error("❌ Cannot connect to backend. Please start the API server first.")
                st.code("cd backend && python main.py", language="bash")
                st.stop()
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        score = data.get("risk_score", 0)
        risk_level = data.get("risk_level", "UNKNOWN")
        color = get_risk_color(score)

        # ─── Risk Score Hero Section ─────────────────
        st.markdown("---")
        
        col_gauge, col_info = st.columns([1, 2])
        
        with col_gauge:
            fig = create_gauge_chart(score)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_info:
            st.markdown(f"""
            <div class="glass-card animate-in">
                <h3 style="color: {color}; font-size: 1.5rem; margin-bottom: 0.5rem;">
                    {data.get('risk_color', '')} {risk_level}
                </h3>
                <p style="color: #e0e0e0; font-size: 1rem; margin-bottom: 1rem;">
                    {data.get('risk_label', '')}
                </p>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <div>
                        <span style="color: #9e9e9e; font-size: 0.8rem;">Candidate</span><br>
                        <span style="font-weight: 700; font-size: 1.1rem;">{data.get('name', 'Unknown')}</span>
                    </div>
                    <div>
                        <span style="color: #9e9e9e; font-size: 0.8rem;">Signals Fired</span><br>
                        <span style="font-weight: 700; font-size: 1.1rem;">{data.get('active_signals', 0)}/6</span>
                    </div>
                    <div>
                        <span style="color: #9e9e9e; font-size: 0.8rem;">Top Concern</span><br>
                        <span style="font-weight: 700; font-size: 1.1rem;">{data.get('most_critical_signal', 'None')}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Alert box
            if data.get("alert"):
                st.markdown(f"""
                <div class="alert-critical animate-in">
                    ⚠️ <strong>RECRUITER ALERT TRIGGERED</strong> — This resume requires immediate manual review.
                </div>
                """, unsafe_allow_html=True)
            elif score >= 40:
                st.markdown(f"""
                <div class="alert-warning animate-in">
                    ⚡ <strong>CAUTION</strong> — Some concerns detected. Manual verification recommended.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="alert-safe animate-in">
                    ✅ <strong>LOW RISK</strong> — Resume appears legitimate. Standard procedures apply.
                </div>
                """, unsafe_allow_html=True)

        # ─── Signal Breakdown ────────────────────────
        st.markdown("---")
        st.subheader("📊 Signal Breakdown")
        
        signals = data.get("signals", {})
        
        col_radar, col_bars = st.columns(2)
        with col_radar:
            st.plotly_chart(
                create_signal_radar(signals),
                use_container_width=True,
                config={"displayModeBar": False}
            )
        with col_bars:
            st.plotly_chart(
                create_signal_bar(signals),
                use_container_width=True,
                config={"displayModeBar": False}
            )

        # Signal detail cards
        signal_info = [
            ("📅", "Timeline", signals.get("timeline_score", 0), 40),
            ("📧", "Email", signals.get("email_score", 0), 20),
            ("📱", "Phone", signals.get("phone_score", 0), 15),
            ("📝", "Plagiarism", signals.get("plagiarism_score", 0), 30),
            ("🔍", "Similarity", signals.get("similarity_score", 0), 35),
            ("🎯", "Mismatch", signals.get("mismatch_score", 0), 20),
        ]

        cols = st.columns(6)
        for i, (icon, name, val, max_val) in enumerate(signal_info):
            pct = (val / max_val * 100) if max_val > 0 else 0
            col_color = get_risk_color(pct)
            with cols[i]:
                st.markdown(f"""
                <div class="signal-card animate-in" style="animation-delay: {i * 0.1}s;">
                    <div class="signal-icon">{icon}</div>
                    <div class="signal-name">{name}</div>
                    <div class="signal-score" style="color: {col_color};">{val}</div>
                    <div style="color: #9e9e9e; font-size: 0.75rem;">/ {max_val}</div>
                    <div class="progress-bar-bg" style="margin-top: 0.5rem;">
                        <div class="progress-bar-fill" style="width: {pct}%; background: {col_color};"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ─── AI Explanation ──────────────────────────
        st.markdown("---")
        st.subheader("🤖 AI Analysis & Explanation")

        explanation = data.get("llm_explanation", "No explanation available.")
        st.markdown(f"""
        <div class="glass-card animate-in">
            <div style="white-space: pre-wrap; line-height: 1.7; font-size: 0.95rem;">
{explanation}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ─── Extracted Entities ──────────────────────
        st.markdown("---")
        with st.expander("📋 Extracted Entities", expanded=False):
            entities = data.get("entities", {})
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                st.markdown(f"**Name:** {entities.get('name', 'N/A')}")
                st.markdown(f"**Emails:** {', '.join(entities.get('emails', [])) or 'N/A'}")
                st.markdown(f"**Phones:** {', '.join(entities.get('phones', [])) or 'N/A'}")
                st.markdown(f"**Skills Count:** {entities.get('skills_count', 0)}")
            with e_col2:
                st.markdown("**Experiences:**")
                for exp in entities.get("experiences", []):
                    st.markdown(f"- {exp.get('role', '')} at **{exp.get('company', '')}** ({exp.get('start', '')} – {exp.get('end', '')})")
                st.markdown("**Education:**")
                for edu in entities.get("education", []):
                    st.markdown(f"- {edu.get('degree', '')} — {edu.get('context', '')[:80]}")

        # ─── Email & Phone API Verification Results ──
        st.markdown("---")
        st.subheader("✅ Contact Verification Results")

        ev_col, pv_col = st.columns(2)

        with ev_col:
            st.markdown("##### ✉️ Email Verification (ZeroBounce)")
            email_verif = data.get("email_verification", [])
            if email_verif:
                for ev in email_verif:
                    status = ev.get("status", "unknown")
                    is_valid = ev.get("is_valid", False)
                    is_disp = ev.get("is_disposable", False)
                    badge_color = "#66bb6a" if is_valid else "#ef5350"
                    badge_text = "VALID" if is_valid else status.upper()
                    disp_badge = ' <span style="background:#ff7043;padding:2px 8px;border-radius:8px;font-size:0.75rem;">DISPOSABLE</span>' if is_disp else ""
                    st.markdown(f"""
                    <div class="glass-card" style="padding: 0.75rem; margin-bottom: 0.5rem;">
                        <span style="font-weight:600;">{ev.get('email','N/A')}</span>
                        <span style="background:{badge_color};color:#fff;padding:2px 10px;border-radius:8px;font-size:0.75rem;margin-left:8px;">{badge_text}</span>{disp_badge}
                        <div style="color:#9e9e9e;font-size:0.8rem;margin-top:4px;">
                            Sub-status: {ev.get('sub_status','—')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No email verification data available.")

        with pv_col:
            st.markdown("##### 📞 Phone Verification (NumVerify)")
            phone_verif = data.get("phone_verification", [])
            if phone_verif:
                for pv in phone_verif:
                    is_valid = pv.get("is_valid", False)
                    badge_color = "#66bb6a" if is_valid else "#ef5350"
                    badge_text = "VALID" if is_valid else "INVALID"
                    line_type = pv.get("line_type", "unknown") or "unknown"
                    voip_badge = ' <span style="background:#ffa726;padding:2px 8px;border-radius:8px;font-size:0.75rem;">VoIP</span>' if line_type.lower() == "voip" else ""
                    st.markdown(f"""
                    <div class="glass-card" style="padding: 0.75rem; margin-bottom: 0.5rem;">
                        <span style="font-weight:600;">{pv.get('phone','N/A')}</span>
                        <span style="background:{badge_color};color:#fff;padding:2px 10px;border-radius:8px;font-size:0.75rem;margin-left:8px;">{badge_text}</span>{voip_badge}
                        <div style="color:#9e9e9e;font-size:0.8rem;margin-top:4px;">
                            State: {pv.get('state','—')} | Country: {pv.get('country','—')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No phone verification data available.")

        # ─── Raw JSON ────────────────────────────────
        with st.expander("🔧 Raw API Response", expanded=False):
            st.json(data)


# ─── Page: Batch Analysis ────────────────────────────────
elif page == "📊 Batch Analysis":
    st.markdown("""
    <div class="main-header">
        <h1>📊 Batch Resume Analysis</h1>
        <p>Upload multiple resumes to analyze them together with cross-resume fraud detection</p>
    </div>
    """, unsafe_allow_html=True)

    files = st.file_uploader(
        "Upload multiple resumes",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="batch_upload",
    )

    if files and st.button("🚀 Analyze All", type="primary", use_container_width=True):
        with st.spinner(f"Analyzing {len(files)} resumes..."):
            progress = st.progress(0)
            results = []
            errors = []

            for i, f in enumerate(files):
                try:
                    res = requests.post(
                        f"{API_URL}/validate_resume",
                        files={"file": (f.name, f.getvalue(), "application/octet-stream")},
                        timeout=120,
                    )
                    if res.status_code == 200:
                        results.append(res.json())
                    else:
                        errors.append({"file": f.name, "error": res.text})
                except Exception as e:
                    errors.append({"file": f.name, "error": str(e)})
                
                progress.progress((i + 1) / len(files))

            progress.empty()

        if results:
            # Summary metrics
            scores = [r["risk_score"] for r in results]
            
            st.markdown("---")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Analyzed", len(results))
            m2.metric("Avg Risk Score", f"{sum(scores)/len(scores):.1f}")
            m3.metric("High Risk", sum(1 for s in scores if s >= 65))
            m4.metric("Max Score", max(scores))

            # Distribution chart
            st.markdown("---")
            st.subheader("Risk Distribution")
            
            df = pd.DataFrame([{
                "Name": r.get("name", "Unknown"),
                "File": r.get("filename", ""),
                "Risk Score": r.get("risk_score", 0),
                "Risk Level": r.get("risk_level", ""),
                "Active Signals": r.get("active_signals", 0),
            } for r in results])

            fig = px.bar(
                df.sort_values("Risk Score", ascending=True),
                x="Risk Score",
                y="Name",
                orientation="h",
                color="Risk Score",
                color_continuous_scale=["#4fc3f7", "#66bb6a", "#ffa726", "#ff7043", "#ef5350"],
                range_color=[0, 100],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10),
                height=max(300, len(results) * 50),
                xaxis=dict(gridcolor="rgba(255,255,255,0.08)", range=[0, 100]),
                yaxis=dict(tickfont=dict(color="#e0e0e0")),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Results table
            st.markdown("---")
            st.subheader("Detailed Results")
            st.dataframe(
                df.style.background_gradient(subset=["Risk Score"], cmap="RdYlGn_r"),
                use_container_width=True,
                hide_index=True,
            )

        if errors:
            st.error(f"⚠️ {len(errors)} file(s) failed to process")
            for err in errors:
                st.caption(f"❌ {err['file']}: {err['error']}")


# ─── Page: Compare Resumes ───────────────────────────────
elif page == "🆚 Compare Resumes":
    st.markdown("""
    <div class="main-header">
        <h1>🆚 Resume Comparison</h1>
        <p>Upload two resumes to compare them for similarity and shared information</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        file1 = st.file_uploader("Resume 1", type=["pdf", "docx", "txt"], key="cmp1")
    with col2:
        file2 = st.file_uploader("Resume 2", type=["pdf", "docx", "txt"], key="cmp2")

    if file1 and file2 and st.button("🔍 Compare", type="primary", use_container_width=True):
        with st.spinner("Comparing resumes..."):
            try:
                res = requests.post(
                    f"{API_URL}/compare_resumes",
                    files={
                        "file1": (file1.name, file1.getvalue(), "application/octet-stream"),
                        "file2": (file2.name, file2.getvalue(), "application/octet-stream"),
                    },
                    timeout=120,
                )
                data = res.json()
            except Exception as e:
                st.error(f"Comparison failed: {e}")
                st.stop()

        sim = data.get("similarity_score", 0)
        sim_color = get_risk_color(sim)

        st.markdown("---")

        # Similarity gauge
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            fig = create_gauge_chart(sim, "Similarity %")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Flags
        flags = data.get("fraud_indicators", {})
        if flags.get("possible_duplicate"):
            st.markdown('<div class="alert-critical">🚨 <strong>POSSIBLE DUPLICATE</strong> — These resumes are near-identical!</div>', unsafe_allow_html=True)
        elif flags.get("high_similarity"):
            st.markdown('<div class="alert-warning">⚠️ <strong>HIGH SIMILARITY</strong> — Significant overlap detected.</div>', unsafe_allow_html=True)
        elif flags.get("same_contact"):
            st.markdown('<div class="alert-warning">📧 <strong>SHARED CONTACT INFO</strong> — Same email or phone found.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-safe">✅ <strong>NO CONCERNS</strong> — Resumes appear distinct.</div>', unsafe_allow_html=True)

        # Details
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**Resume 1:** {data.get('name1', 'N/A')} ({data.get('file1', '')})")
        with d2:
            st.markdown(f"**Resume 2:** {data.get('name2', 'N/A')} ({data.get('file2', '')})")

        if data.get("shared_emails"):
            st.warning(f"📧 Shared Emails: {', '.join(data['shared_emails'])}")
        if data.get("shared_phones"):
            st.warning(f"📱 Shared Phones: {', '.join(data['shared_phones'])}")
        if data.get("skills_overlap"):
            st.info(f"🎯 Shared Skills ({len(data['skills_overlap'])}): {', '.join(data['skills_overlap'][:15])}")


# ─── Page: Dashboard ─────────────────────────────────────
elif page == "📈 Dashboard":
    st.markdown("""
    <div class="main-header">
        <h1>📈 Analysis Dashboard</h1>
        <p>System statistics and fraud detection overview</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        stats = requests.get(f"{API_URL}/stats", timeout=3).json()
        history = requests.get(f"{API_URL}/history", timeout=3).json()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📄 Total Analyzed", stats.get("total_resumes_analyzed", 0))
        m2.metric("📧 Unique Emails", stats.get("unique_emails", 0))
        m3.metric("📱 Unique Phones", stats.get("unique_phones", 0))
        m4.metric("🧠 Embeddings", stats.get("embeddings_stored", 0))

        st.markdown("---")
        st.subheader("📋 Recent Analysis History")
        resumes = history.get("resumes", [])
        if resumes:
            df = pd.DataFrame(resumes)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No resumes analyzed yet. Upload some resumes to get started!")

        st.markdown("---")
        if st.button("🗑️ Reset All Data", type="secondary"):
            requests.delete(f"{API_URL}/reset", timeout=3)
            st.success("All data cleared!")
            st.rerun()

    except Exception as e:
        st.error("Cannot connect to backend API.")
        st.caption(f"Error: {e}")
