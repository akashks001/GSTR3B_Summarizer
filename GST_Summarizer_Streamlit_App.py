import io
import re
import pandas as pd
import pdfplumber
import streamlit as st

# --- Regex Patterns ---
# Matches formatted numbers (handles optional commas, negative signs, and decimals)
NUM_PATTERN = r"([\d,]+\.?\d*|-)"

outward_pattern = (
    r"Outward taxable supplies[^\n\d]*"
    + r"\s+".join([NUM_PATTERN] * 5)
)
outward_zero_pattern = (
    r"\(b\)\s*Outward taxable supplies\s*\(zero rated\)\s*"
    + r"\s+".join([NUM_PATTERN] * 5)
)
outward_nil_pattern = (
    r"\(c\s*\)\s*Other outward supplies\s*\(nil rated,\s*exempted\)\s*"
    + r"\s+".join([NUM_PATTERN] * 5)
)
inward_pattern = (
    r"\(d\)\s*Inward supplies\s*\(liable to reverse charge\)\s*"
    + r"\s+".join([NUM_PATTERN] * 5)
)
non_gst_pattern = (
    r"\(e\)\s*Non-GST outward supplies\s*"
    + r"\s+".join([NUM_PATTERN] * 5)
)

month_to_index = {
    "April": 1, "May": 2, "June": 3, "July": 4, "August": 5,
    "September": 6, "October": 7, "November": 8, "December": 9,
    "January": 10, "February": 11, "March": 12
}

def parse_val(val_str: str) -> float:
    """Converts regex numeric matches to float, stripping commas and handling dashes."""
    cleaned = val_str.replace(",", "").replace("-", "0.0").strip()
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def extract_data_from_pdf_content(file_content, pdf_name):
    try:
        with pdfplumber.open(file_content) as pdf:
            if not pdf.pages:
                st.warning(f"Skipping **{pdf_name}**: File contains no pages.")
                return None

            first_page = pdf.pages[0]
            text = first_page.extract_text(x_tolerance=2, y_tolerance=2) or ""

            outward_sales = outward_igst = outward_cgst = outward_sgst = outward_cess = 0.0
            outward_zero_sales = outward_zero_igst = outward_zero_cgst = outward_zero_sgst = outward_zero_cess = 0.0
            outward_nil_sales = outward_nil_igst = outward_nil_cgst = outward_nil_sgst = outward_nil_cess = 0.0
            inward_sales = inward_igst = inward_cgst = inward_sgst = inward_cess = 0.0
            non_gst_sales = non_gst_igst = non_gst_cgst = non_gst_sgst = non_gst_cess = 0.0

            # 1. Outward taxable supplies
            m = re.search(outward_pattern, text, re.IGNORECASE)
            if m:
                outward_sales, outward_igst, outward_cgst, outward_sgst, outward_cess = [
                    parse_val(m.group(i)) for i in range(1, 6)
                ]

            # 2. Outward taxable supplies (zero rated)
            m = re.search(outward_zero_pattern, text, re.IGNORECASE)
            if m:
                outward_zero_sales, outward_zero_igst, outward_zero_cgst, outward_zero_sgst, outward_zero_cess = [
                    parse_val(m.group(i)) for i in range(1, 6)
                ]

            # 3. Other outward supplies (nil rated, exempted)
            m = re.search(outward_nil_pattern, text, re.IGNORECASE)
            if m:
                outward_nil_sales, outward_nil_igst, outward_nil_cgst, outward_nil_sgst, outward_nil_cess = [
                    parse_val(m.group(i)) for i in range(1, 6)
                ]

            # 4. Inward supplies (liable to reverse charge)
            m = re.search(inward_pattern, text, re.IGNORECASE)
            if m:
                inward_sales, inward_igst, inward_cgst, inward_sgst, inward_cess = [
                    parse_val(m.group(i)) for i in range(1, 6)
                ]

            # 5. Non-GST outward supplies
            m = re.search(non_gst_pattern, text, re.IGNORECASE)
            if m:
                non_gst_sales, non_gst_igst, non_gst_cgst, non_gst_sgst, non_gst_cess = [
                    parse_val(m.group(i)) for i in range(1, 6)
                ]

            # Calculations
            sales = outward_sales + outward_zero_sales + outward_nil_sales - inward_sales + non_gst_sales
            igst = outward_igst + outward_zero_igst + outward_nil_igst - inward_igst + non_gst_igst
            cgst = outward_cgst + outward_zero_cgst + outward_nil_cgst - inward_cgst + non_gst_cgst
            sgst = outward_sgst + outward_zero_sgst + outward_nil_sgst - inward_sgst + non_gst_sgst
            cess = outward_cess + outward_zero_cess + outward_nil_cess - inward_cess + non_gst_cess
            total = sales + igst + cgst + sgst + cess

            # Metadata extraction
            gstin_match = re.search(r"GSTIN\s*(?:of the supplier)?\s*[:\-]?\s*([0-9A-Z]{15})", text, re.IGNORECASE)
            gstin = gstin_match.group(1).strip() if gstin_match else "N/A"

            fy_match = re.search(r"Year\s*[:\-]?\s*(\d{4}-\d{2})", text, re.IGNORECASE)
            fy = fy_match.group(1) if fy_match else "N/A"

            month_match = re.search(r"Period\s*[:\-]?\s*([A-Za-z]+)", text, re.IGNORECASE)
            month = month_match.group(1).capitalize() if month_match else "N/A"
            month_index = month_to_index.get(month, 99)

            return pd.DataFrame([{
                "GSTIN": gstin,
                "FY": fy,
                "MONTH": month,
                "Month_Index": month_index,
                "Sales": sales,
                "IGST": igst,
                "CGST": cgst,
                "SGST": sgst,
                "Cess": cess,
                "Total": total,
            }])

    except Exception as e:
        st.error(f"Error parsing **{pdf_name}**: {e}")
        return None

def process_uploaded_files(uploaded_files):
    all_rows = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, f in enumerate(uploaded_files):
        status_text.text(f"Processing ({idx + 1}/{len(uploaded_files)}): {f.name}")
        f.seek(0)  # Rewind buffer before reading
        content = io.BytesIO(f.read())
        row = extract_data_from_pdf_content(content, f.name)
        if row is not None and not row.empty:
            all_rows.append(row)
        progress_bar.progress((idx + 1) / len(uploaded_files))

    progress_bar.empty()
    status_text.empty()

    if all_rows:
        master = pd.concat(all_rows, ignore_index=True)
        master = master.sort_values(by=["FY", "Month_Index", "GSTIN"])
        master = master.drop_duplicates(subset=["FY", "Month_Index", "GSTIN"], keep="last")
        return master
    return pd.DataFrame()

def main():
    st.set_page_config(page_title="GSTR-3B Consolidation Tool", layout="wide")
    st.title("📄 GSTR-3B PDF Consolidation Tool")

    if "consolidated_df" not in st.session_state:
        st.session_state.consolidated_df = None

    uploaded_files = st.file_uploader(
        "Upload GSTR-3B PDF Files",
        type=["pdf"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.info(f"{len(uploaded_files)} PDF(s) selected.")

        if st.button("🚀 Consolidate Data"):
            df = process_uploaded_files(uploaded_files)
            if not df.empty:
                st.session_state.consolidated_df = df
            else:
                st.warning("No tabular rows could be extracted. Please check the PDF format.")

    # Render results from session state to survive mobile reruns
    if st.session_state.consolidated_df is not None:
        st.success("Data Consolidation Successful!")
        st.dataframe(st.session_state.consolidated_df)

        csv_data = st.session_state.consolidated_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download GST_Summary.csv",
            data=csv_data,
            file_name="GST_Summary.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
