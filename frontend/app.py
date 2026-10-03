"""DataRefinery: Streamlit frontend (Upload screen)."""

import pandas as pd
import streamlit as st

from api_client import ApiError, get_health, get_session_records, upload_dataset

st.set_page_config(page_title="DataRefinery", page_icon="🧹", layout="wide")


def render_sidebar() -> None:
    st.sidebar.header("System status")
    try:
        health = get_health()
        st.sidebar.success(f"Backend online ({health['environment']})")
    except ApiError as exc:
        st.sidebar.error(str(exc))
    st.sidebar.caption(
        "Demonstration system. Uses synthetic data only. "
        "Do not upload real personal information."
    )


def render_upload_section() -> None:
    st.subheader("1. Upload a dataset")
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"],
        help="Required columns: family_id, full_name, cnic, phone, district, address",
    )

    if uploaded_file is None:
        return

    if st.button("Create processing session", type="primary"):
        with st.spinner("Validating and storing the dataset..."):
            try:
                session = upload_dataset(uploaded_file.name, uploaded_file.getvalue())
            except ApiError as exc:
                st.error(f"Upload rejected: {exc}")
                return
        st.session_state["current_session"] = session
        st.success("File validated and processing session created.")


def render_session_summary() -> None:
    session = st.session_state.get("current_session")
    if session is None:
        return

    st.subheader("2. Processing session")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Records", f"{session['row_count']:,}")
    col2.metric("Columns", session["column_count"])
    col3.metric("File size", f"{session['file_size_bytes'] / 1024:.1f} KB")
    col4.metric("Status", session["status"])

    st.caption(f"Session ID: `{session['id']}` · File: {session['original_filename']}")
    st.write("**Detected columns:** " + ", ".join(session["columns"]))

    st.subheader("3. Preview of stored records (original values)")
    try:
        records = get_session_records(session["id"], limit=20)
    except ApiError as exc:
        st.error(str(exc))
        return

    preview = pd.DataFrame([record["original_data"] for record in records])
    preview.insert(0, "row", [record["row_number"] for record in records])
    st.dataframe(preview, use_container_width=True, hide_index=True)
    st.caption("Values are shown exactly as uploaded. Cleaning begins on Day 2.")


def main() -> None:
    st.title("🧹 DataRefinery")
    st.caption("Automated Data Cleaning & Quality Management System")
    render_sidebar()
    render_upload_section()
    render_session_summary()


main()