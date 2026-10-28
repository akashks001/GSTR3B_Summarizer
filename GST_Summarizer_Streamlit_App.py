import streamlit as st
import pdfplumber
import re
import pandas as pd
import io

st.set_page_config(page_title="GSTR-3B PDF Consolidation Tool", layout="wide")

outward_pattern = r"Outward taxable supplies.*?(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})"
outward_zero_pattern = r"\(b\) Outward taxable supplies \(zero rated\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
outward_nil_pattern = r"\(c\)\s*Other outward supplies \(nil rated, exempted\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
inward_pattern = r"\(d\) Inward supplies \(liable to reverse charge\)\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})"
non_gst_pattern = r"\(e\) Non-GST outward supplies\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"

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
                outward_zero_sales, outward_zero_igst, outward_zero_cgst, outward_zero_sgst, outward_zero_cess = [
                    float(x.replace('-', '0.00')) for x in outward_zero_match.groups()
                ]

            outward_nil_match = re.search(outward_nil_pattern, text, re.DOTALL)
            if outward_nil_match:
                outward_nil_sales, outward_nil_igst, outward_nil_cgst, outward_nil_sgst, outward_nil_cess = [
                    float(x.replace('-', '0.00')) for x in outward_nil_match.groups()
                ]

            inward_match = re.search(inward_pattern, text, re.DOTALL)
            if inward_match:
                inward_sales, inward_igst, inward_cgst, inward_sgst, inward_cess = map(float, inward_match.groups())

            non_gst_match = re.search(non_gst_pattern, text, re.DOTALL)
            if non_gst_match:
                non_gst_sales, non_gst_igst, non_gst_cgst, non_gst_sgst, non_gst_cess = [
                    float(x.replace('-', '0.00')) for x in non_gst_match.groups()
                ]

            sales = outward_sales + outward_zero_sales + outward_nil_sales - inward_sales + non_gst_sales
            igst = outward_igst + outward_zero_igst + outward_nil_igst - inward_igst + non_gst_igst
            cgst = outward_cgst + outward_zero_cgst + outward_nil_cgst - inward_cgst + non_gst_cgst
            sgst = outward_sgst + outward_zero_sgst + outward_nil_sgst - inward_sgst + non_gst_sgst
            cess = outward_cess + outward_zero_cess + outward_nil_cess - inward_cess + non_gst_cess
            total = sales + igst + cgst + sgst + cess

            GSTIN_match = re.search(r"GSTIN of the supplier\s*([A-Z0-9]+)", text)
            GSTIN = GSTIN_match.group(1).strip() if GSTIN_match else "N/A"

            fy_match = re.search(r"Year\s*(\d{4}-\d{2})", text)
            FY = fy_match.group(1) if fy_match else "N/A"

            month_match = re.search(r"Period\s*([A-Za-z]+)", text)
            Month = month_match.group(1).strip() if month_match else "N/A"
            Month_Index = month_to_index.get(Month, "N/A")

            return pd.DataFrame([{
                'GSTIN': GSTIN, 'FY': FY, 'MONTH': Month, 'Month_Index': Month_Index,
                'Sales': sales, 'IGST': igst, 'CGST': cgst, 'SGST': sgst, 'Cess': cess, 'Total': total
            }])
    except Exception as e:
        st.error(f"Failed parsing {pdf_name}: {e}")
        return None

st.title("📄 GSTR-3B PDF Consolidation Tool")
st.markdown(":red[**AFTER CONSOLIDATION, PLEASE ENSURE DATA CORRECTNESS BY CHECKING ONE FILE MANUALLY.**]")

# Android fix: allow single or multiple toggle to prevent UI hang
mode = st.radio("Selection Mode", ["Single File", "Multiple Files"], horizontal=True)

# Android fix: type=None avoids mime filtering drops
raw_uploads = st.file_uploader(
    "Choose PDF File(s)", 
    type=None, 
    accept_multiple_files=(mode == "Multiple Files"),
    help="On mobile: Pick files from Internal Storage/Downloads, NOT from 'Recent'."
)

uploaded_files = []
if raw_uploads:
    if isinstance(raw_uploads, list):
        uploaded_files = [f for f in raw_uploads if f.name.lower().endswith(".pdf")]
    elif raw_uploads.name.lower().endswith(".pdf"):
        uploaded_files = [raw_uploads]

if uploaded_files:
    st.success(f"{len(uploaded_files)} PDF file(s) ready.")
    
    if st.button("🚀 Consolidate Data", use_container_width=True):
        master = pd.DataFrame()
        bar = st.progress(0)
        
        for i, up_file in enumerate(uploaded_files):
            up_file.seek(0)
            content = up_file.read()
            if not content:
                continue
            row = extract_data_from_pdf_content(content, up_file.name)
            if row is not None:
                master = pd.concat([master, row], ignore_index=True)
            bar.progress((i + 1
