"""
Streamlit Application for School Detention and On‑Call Monitoring
================================================================

This Streamlit app provides a simple way for school data managers and
administrators to visualise detention and on‑call incident data.  You
can upload CSV/Excel files exported from your MIS (e.g. Arbor) or
provide a public Google Sheets link.  The app will calculate key
metrics (totals, attendance rates, breakdowns) and render interactive
tables and charts for day‑to‑day and strategic monitoring.

How to run the app
------------------

Install the dependencies if you haven't already:

```
pip install streamlit pandas altair
```

Then launch the app with:

```
streamlit run detention_dashboard_app.py
```

Once running, open your browser to the local URL displayed in the
terminal.  You can then upload your data files or specify a Google
Sheets link and explore the dashboards.
"""

import datetime
from typing import Optional

import pandas as pd
import streamlit as st
import altair as alt


def load_data_from_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> Optional[pd.DataFrame]:
    """Load a DataFrame from an uploaded file (Excel or CSV)."""
    if uploaded_file is None:
        return None
    try:
        # Use file name to decide how to read
        filename = uploaded_file.name.lower()
        if filename.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            # Try loading the first sheet by default
            return pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return None
    except Exception as exc:
        st.error(f"Error reading file: {exc}")
        return None


def load_data_from_url(url: str) -> Optional[pd.DataFrame]:
    """Load a DataFrame from a public link.

    The link may refer to a Google Sheet, a CSV file or an Excel file.
    For Google Sheets, the function automatically converts the edit
    URL into a CSV export if possible.  If the link appears to
    reference an Excel file (ending with ``.xls`` or ``.xlsx``), the
    function uses :func:`pandas.read_excel` to load it directly.
    Otherwise the link is treated as a CSV and read via
    :func:`pandas.read_csv`.
    """
    if not url:
        return None
    try:
        url = url.strip()
        # Google Sheets: convert edit link to CSV export
        if "docs.google.com" in url and "/edit" in url:
            try:
                sheet_id = url.split("/d/")[1].split("/")[0]
                url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            except Exception:
                pass
        # Decide how to read based on file extension or query string
        lower = url.lower()
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return pd.read_excel(url)
        # default to csv
        return pd.read_csv(url)
    except Exception as exc:
        st.error(f"Error loading data from URL: {exc}")
        return None


def prepare_detentions(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalise the detentions DataFrame.

    Ensures the expected columns exist and parses dates.
    """
    # Standardise expected column names
    rename_map = {
        'Student': 'Student',
        'Year': 'Year',
        'Reg. Form': 'Reg Form',
        'House': 'House',
        'Reason': 'Reason',
        'Detention Type': 'Detention Type',
        'Issued Date': 'Issued Date',
        'Issued By': 'Issued By',
        'Detention Date': 'Detention Date',
        'Detention Attendance': 'Detention Attendance',
    }
    # Standardise whitespace in column names
    df.columns = df.columns.str.strip()
    df = df.rename(columns=rename_map)
    # Attempt to normalise the attendance column name
    if 'Detention Attendance' not in df.columns:
        # Find any column with 'attendance' in its name (case insensitive)
        attendance_candidates = [c for c in df.columns if 'attendance' in c.lower()]
        if attendance_candidates:
            df = df.rename(columns={attendance_candidates[0]: 'Detention Attendance'})
    # Parse date fields
    for col in ['Issued Date', 'Detention Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def prepare_oncall(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalise the on‑call DataFrame.

    Ensures the expected columns exist and parses date/time.
    """
    rename_map = {
        'Date/Time': 'DateTime',
        'Reported by': 'Reported By',
        'Location': 'Location',
        'Comments': 'Comments',
        'Type': 'Type',
        'Students involved': 'Students',
        'Event': 'Event',
        'Assigned to': 'Assigned To',
        'Status': 'Status',
    }
    df = df.rename(columns=rename_map)
    if 'DateTime' in df.columns:
        df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
    return df


def render_detentions_dashboard(df: pd.DataFrame) -> None:
    """Render the detentions dashboard components on the Streamlit app."""
    st.header("Detentions Dashboard")
    if df.empty:
        st.info("No detentions data available.")
        return
    # Summary metrics
    total_detentions = len(df)
    # Compute attended count; if the attendance column is missing, default to zero
    if 'Detention Attendance' in df.columns:
        attended = (df['Detention Attendance'].astype(str).str.contains("Present", case=False, na=False)).sum()
    else:
        attended = 0
    attendance_rate = attended / total_detentions if total_detentions else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Detentions", total_detentions)
    col2.metric("Attended", attended)
    col3.metric("Attendance Rate", f"{attendance_rate:.1%}")
    # Year group breakdown
    with st.expander("Year Group Breakdown"):
        if 'Year' in df.columns:
            breakdown = (
                df.groupby('Year')
                .agg(Issued=('Student', 'count'), Attended=('Detention Attendance', lambda x: (x=='Present').sum()))
                .reset_index()
            )
            breakdown['Attendance Rate'] = breakdown['Attended'] / breakdown['Issued']
            st.dataframe(breakdown)
            chart = (
                alt.Chart(breakdown)
                .mark_bar()
                .encode(
                    x=alt.X('Year:N', title='Year Group'),
                    y=alt.Y('Issued:Q', title='Issued Count'),
                    color=alt.value('#007bff'),
                    tooltip=['Year', 'Issued', 'Attended', alt.Tooltip('Attendance Rate:Q', format='.1%')]
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("The 'Year' column is missing from detentions data.")
    # Daily monitoring
    with st.expander("Daily Monitoring"):
        if 'Issued Date' in df.columns:
            daily = (
                df.dropna(subset=['Issued Date'])
                .assign(Date=lambda x: x['Issued Date'].dt.date)
                .groupby('Date')
                .agg(Issued=('Student', 'count'), Attended=('Detention Attendance', lambda x: (x=='Present').sum()))
                .reset_index()
            )
            daily['Attendance Rate'] = daily['Attended'] / daily['Issued']
            st.dataframe(daily)
            line = (
                alt.Chart(daily)
                .mark_line()
                .encode(
                    x=alt.X('Date:T', title='Date'),
                    y=alt.Y('Issued:Q', title='Detentions Issued'),
                    tooltip=['Date', 'Issued', 'Attended', alt.Tooltip('Attendance Rate:Q', format='.1%')]
                )
                .properties(height=300)
            )
            st.altair_chart(line, use_container_width=True)
        else:
            st.warning("The 'Issued Date' column is missing from detentions data.")


def render_oncall_dashboard(df: pd.DataFrame) -> None:
    """Render the on‑call dashboard components on the Streamlit app."""
    st.header("On‑Call Dashboard")
    if df.empty:
        st.info("No on‑call data available.")
        return
    # Summary metrics
    total_calls = len(df)
    resolved = (df['Status'].str.contains('Resolved', na=False)).sum()
    unresolved = (df['Status'].str.contains('Unresolved', na=False)).sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Incidents", total_calls)
    col2.metric("Resolved", resolved)
    col3.metric("Unresolved", unresolved)
    # Type breakdown
    with st.expander("Incident Type Breakdown"):
        if 'Type' in df.columns:
            type_counts = df['Type'].value_counts().reset_index().rename(columns={'index': 'Type', 'Type': 'Count'})
            st.dataframe(type_counts)
            bar = (
                alt.Chart(type_counts)
                .mark_bar()
                .encode(
                    x=alt.X('Type:N', title='Incident Type'),
                    y=alt.Y('Count:Q', title='Count'),
                    color=alt.value('#28a745'),
                    tooltip=['Type', 'Count']
                )
                .properties(height=300)
            )
            st.altair_chart(bar, use_container_width=True)
        else:
            st.warning("The 'Type' column is missing from on‑call data.")
    # Daily monitoring
    with st.expander("Daily Monitoring"):
        if 'DateTime' in df.columns:
            daily = (
                df.dropna(subset=['DateTime'])
                .assign(Date=lambda x: x['DateTime'].dt.date)
                .groupby('Date')
                .agg(Incidents=('DateTime', 'count'))
                .reset_index()
            )
            st.dataframe(daily)
            line = (
                alt.Chart(daily)
                .mark_line(color='#dc3545')
                .encode(
                    x=alt.X('Date:T', title='Date'),
                    y=alt.Y('Incidents:Q', title='On‑Call Incidents'),
                    tooltip=['Date', 'Incidents']
                )
                .properties(height=300)
            )
            st.altair_chart(line, use_container_width=True)
        else:
            st.warning("The 'Date/Time' column is missing from on‑call data.")


def main() -> None:
    st.title("School Behaviour Monitoring Dashboard")
    st.write(
        "Upload your detentions and on‑call data or provide a Google Sheets link. "
        "The app will calculate attendance rates, breakdowns and trend charts automatically."
    )
    # --- Data input section ---
    st.subheader("Upload Files")
    file_cols = st.columns(2)
    with file_cols[0]:
        det_file = st.file_uploader(
            "Detentions Data (Excel or CSV)",
            type=["csv", "xlsx", "xls"],
            key="detentions_file",
        )
    with file_cols[1]:
        on_file = st.file_uploader(
            "On‑Call Data (Excel or CSV)",
            type=["csv", "xlsx", "xls"],
            key="oncall_file",
        )

    st.markdown("""
    ---
    #### Or load data from a live link
    Enter a direct URL to a public Google Sheet, CSV, or Excel file exported
    from your MIS (e.g., Arbor, Power BI, SharePoint).  The app will
    attempt to fetch the file and parse it automatically.
    """)
    link_cols = st.columns(2)
    with link_cols[0]:
        det_sheet_url = st.text_input(
            "Detentions link",
            placeholder="https://...",
            key="detentions_url",
        )
    with link_cols[1]:
        on_sheet_url = st.text_input(
            "On‑Call link",
            placeholder="https://...",
            key="oncall_url",
        )
    # Load data
    det_df = None
    on_df = None
    if det_file is not None:
        det_df = load_data_from_file(det_file)
    elif det_sheet_url:
        det_df = load_data_from_url(det_sheet_url)
    if on_file is not None:
        on_df = load_data_from_file(on_file)
    elif on_sheet_url:
        on_df = load_data_from_url(on_sheet_url)
    # Prepare and render dashboards
    if det_df is not None:
        det_df = prepare_detentions(det_df)
        render_detentions_dashboard(det_df)
    if on_df is not None:
        on_df = prepare_oncall(on_df)
        render_oncall_dashboard(on_df)
    if det_df is None and on_df is None:
        st.info(
            "Please upload data files or provide Google Sheets links to see the dashboards."
        )


if __name__ == "__main__":
    main()