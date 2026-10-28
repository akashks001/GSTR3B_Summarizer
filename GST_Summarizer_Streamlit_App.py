import streamlit as st
import pdfplumber
import re
import pandas as pd
import io

st.set_page_config(page_title="GSTR-3B PDF Consolidation Tool", layout="wide")

outward_pattern = r"Outward taxable supplies.*?(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})"
outward_zero_pattern = r"\(b\)\s*Outward taxable supplies\s*\(zero rated\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
outward_nil_pattern = r"\(c\s*\)\s*Other outward supplies\s*\(nil rated,\s*exempted\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
inward_pattern = r"\(d\)\s*Inward supplies\s*\(liable to reverse charge\)\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})"
non_gst_pattern = r"\(e\)\s*Non-GST outward supplies\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"

month_to_index = {
    "April": 1, "May": 2, "June": 3, "July": 4, "August": 5,
    "September": 6, "October": 7, "November": 8, "December": 9,
    "January": 10, "February": 11, "March": 12
}

def extract_data_from_pdf_content(file_bytes, pdf_name):
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                st.warning(f"File {pdf_name} has no pages.")
                return None

            first_page = pdf.pages[0]
            text = first_page.extract_text(x_tolerance=1, y_tolerance=1) or ""

            outward_sales = outward_igst = outward_cgst = outward_sgst = outward_cess = 0.0
            outward_zero_sales = outward_zero_igst = outward_zero_cgst = outward_zero_sgst = outward_zero_cess = 0.0
            outward_nil_sales = outward_nil_igst = outward_nil_cgst = outward_nil_sgst = outward_nil_cess = 0.0
            inward_sales = inward_igst = inward_cgst = inward_sgst = inward_cess = 0.0
            non_gst_sales = non_gst_igst = non_gst_cgst = non_gst_sgst = non_gst_cess = 0.0

            outward_match = re.search(outward_pattern, text, re.DOTALL)
            if outward_match:
                outward_sales, outward_igst, outward_cgst, outward_sgst, outward_cess = map(float, outward_match.groups())

            outward_zero_match = re.search(outward_zero_pattern, text, re.DOTALL)
            if outward_zero_match:
                cleaned_vals = [float(x.replace('-', '0.00')) for x in outward_zero_match.groups()]
                outward_zero_sales, outward_zero_igst, outward_zero_cgst, outward_zero_sgst, outward_zero_cess = cleaned_vals

            outward_nil_match = re.search(outward_nil_pattern, text, re.DOTALL)
            if outward_nil_match:
                cleaned_vals = [float(x.replace('-', '0.00')) for x in outward_nil_match.groups()]
                outward_nil_sales, outward_nil_igst, outward_nil_cgst, outward_nil_sgst, outward_nil_cess = cleaned_vals

            inward_match = re.search(inward_pattern, text, re.DOTALL)
            if inward_match:
                inward_sales, inward_igst, inward_cgst, inward_sgst, inward_cess = map(float, inward_match.groups())

            non_gst_match = re.search(non_gst_pattern, text, re.DOTALL)
            if non_gst_match:
                cleaned_vals = [float(x.replace('-', '0.00')) for x in non_gst_match.groups()]
                non_gst_sales, non_gst_igst, non_gst_cgst, non_gst_sgst, non_gst_cess = cleaned_vals

            sales = outward_sales + outward_zero_sales + outward_nil_sales - inward_sales + non_gst_sales
            igst = outward_igst + outward_zero_igst + outward_nil_igst - inward_igst + non_gst_igst
            cgst = outward_cgst + outward_zero_cgst + outward_nil_cgst - inward_cgst + non_gst_cgst
            sgst = outward_sgst + outward_zero_sgst + outward_nil_sgst - inward_sgst + non_gst_sgst
            cess = outward_cess + outward_zero_cess + outward_nil_cess - inward_cess + non_gst_cess
            total = sales + igst + cgst + sgst + cess

            gstin_match = re.search(r"GSTIN of the supplier\s*([A-Z0-9]+)", text)
            gstin = gstin_match.group(1).strip() if gstin_match else "N/A"

            fy_match = re.search(r"Year\s*(\d{4}-\d{2})", text)
            fy = fy_match.group(1) if fy_match else "N/A"

            month_match = re.search(r"Period\s*([A-Za-z]+)", text)
            month = month_match.group(1).strip() if month_match else "N/A"
            month_index = month_to_index.get(month, "N/A")

            return pd.DataFrame([{
                'GSTIN': gstin, 'FY': fy, 'MONTH': month, 'Month_Index': month_index,
                'Sales': sales, 'IGST': igst, 'CGST': cgst, 'SGST': sgst, 'Cess': cess, 'Total': total
            }])
    except Exception as e:
        st.error(f"Failed parsing {pdf_name}: {e}")
        return None

# --- App UI with Session Storage for Mobile ---

st.title("📄 GSTR-3B PDF Consolidation Tool")
st.markdown(":red[**AFTER CONSOLIDATION, PLEASE ENSURE DATA CORRECTNESS BY CHECKING ONE FILE MANUALLY.**]")

# Initialize state to preserve files across mobile browser backgrounding/refreshes
if "file_vault" not in st.session_state:
    st.session_state.file_vault = {}  # {filename: bytes}

# Single-file uploader (reliable on Android)
new_file = st.file_uploader(
    "Upload GSTR-3B PDF",
    type=None,
    accept_multiple_files=False,
    key="mobile_uploader",
    help="Important: On Android, select from 'Downloads' or 'Internal Storage', never from 'Recent'."
)

# Store newly selected file into the persistent vault immediately
if new_file is not None:
    if new_file.name.lower().endswith(".pdf"):
        new_file.seek(0)
        file_bytes = new_file.read()
        if len(file_bytes) > 0:
            st.session_state.file_vault[new_file.name] = file_bytes
            st.toast(f"Added: {new_file.name}", icon="✅")
    else:
        st.error("Selected file is not a PDF.")

# Vault Controls & Display
total_files = len(st.session_state.file_vault)

if total_files > 0:
    st.write(f"### Files ready for consolidation ({total_files})")
    for name in list(st.session_state.file_vault.keys()):
        st.write(f"• `{name}`")

    col1, col2 = st.columns([1, 1])
    with col1:
        start_processing = st.button("🚀 Consolidate All Added Files", type="primary", use_container_width=True)
    with col2:
        if st.button("🗑️ Clear All Files", use_container_width=True):
            st.session_state.file_vault.clear()
            st.rerun()

    if start_processing:
        master = pd.DataFrame()
        bar = st.progress(0)
        
        for idx, (pdf_name, pdf_bytes) in enumerate(st.session_state.file_vault.items()):
            row = extract_data_from_pdf_content(pdf_bytes, pdf_name)
            if row is not None:
                master = pd.concat([master, row], ignore_index=True)
            bar.progress((idx + 1) / total_files)
            
        bar.empty()

        if not master.empty:
            master = master.sort_values(by=['FY', 'Month_Index', 'GSTIN']).drop_duplicates(subset=['FY', 'Month_Index', 'GSTIN'], keep='last')
            st.dataframe(master, use_container_width=True)

            csv = master.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download GST_Summary.csv",
                data=csv,
                file_name="GST_Summary.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("Could not extract any data from the files.")
else:
    st.info("Pick your first PDF above. You can add more PDFs one by one without losing previous ones.")
