import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Resume Fraud Detection Engine", page_icon="🛡️", layout="wide")

st.title("🛡️ Resume Fraud Detection Engine")
st.caption("HackWith AI 2025 | AI-Based Resume Validation")

jd_text_input = st.text_area(
    "Paste Job Description (optional but recommended)",
    placeholder="Paste JD here for better similarity checks...",
    height=180,
)

uploaded_file = st.file_uploader("Upload resume", type=["pdf", "docx"])

if uploaded_file is not None:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    data = {"jd_text": jd_text_input}

    with st.spinner("Analyzing resume and calculating fraud risk..."):
        try:
            response = requests.post(f"{API_BASE}/validate_resume", files=files, data=data, timeout=180)
            response.raise_for_status()
            result = response.json()

            risk_score = int(result.get("risk_score", 0))
            risk_level = result.get("risk_level", "LOW RISK")

            st.metric("Risk Score", f"{risk_score}/100")

            color_map = {
                "HIGH RISK": "#fde2e2",
                "REVIEW REQUIRED": "#fff7db",
                "LOW RISK": "#e7f8ec",
            }
            color = color_map.get(risk_level, "#f3f4f6")

            st.markdown(
                f"""
                <div style="background-color: {color}; padding: 12px; border-radius: 8px; border: 1px solid #e5e7eb; margin-bottom: 12px;">
                    <strong>Risk Level:</strong> {risk_level}
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("Contact Risk", result.get("contact_score", 0))
            col2.metric("Timeline Risk", result.get("timeline_score", 0))
            col3.metric("Similarity Risk", result.get("similarity_score", 0))

            st.subheader("Signal Details")
            with st.expander("View parsed signal data", expanded=False):
                st.json(result.get("signal_details", {}))

            st.subheader("🤖 AI Explanation")
            st.info(result.get("llm_explanation", "Explanation unavailable - review signals manually."))

        except requests.exceptions.ConnectionError:
            st.error("Backend unreachable. Start FastAPI server at http://localhost:8000")
        except requests.exceptions.RequestException as exc:
            st.error(f"API error: {exc}")
        except ValueError:
            st.error("Invalid response from backend.")

st.subheader("📋 Previous Submissions")
try:
    reports_resp = requests.get(f"{API_BASE}/all_reports", timeout=30)
    reports_resp.raise_for_status()
    reports = reports_resp.json()
    if reports:
        st.dataframe(reports, use_container_width=True)
    else:
        st.info("No submissions yet.")
except requests.exceptions.ConnectionError:
    st.error("Backend unreachable. Start FastAPI server at http://localhost:8000")
except requests.exceptions.RequestException as exc:
    st.error(f"Could not fetch previous submissions: {exc}")
except ValueError:
    st.error("Invalid previous submissions response.")
