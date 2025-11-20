import streamlit as st
import os
from pathlib import Path
import pdfplumber
import re
import pandas as pd
import io # Required for handling in-memory files from st.file_uploader
import time # Not strictly necessary for this logic, but kept for completeness

# --- Core Logic and Patterns (Unmodified from your script) ---

outward_pattern = r"Outward taxable supplies.*?(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})"
outward_zero_pattern = r"\(b\) Outward taxable supplies \(zero rated\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
outward_nil_pattern = r"\(c \)\s*Other outward supplies \(nil rated, exempted\)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"
inward_pattern = r"\(d\) Inward supplies \(liable to reverse charge\)\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})"
non_gst_pattern = r"\(e\) Non-GST outward supplies\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)\s*([\d\.\-]+)"

month_to_index = {
    "April": 1, "May": 2, "June": 3, "July": 4, "August": 5,
    "September": 6, "October": 7, "November": 8, "December": 9,
    "January": 10, "February": 11, "March": 12
}

def extract_data_from_pdf_content(file_content, pdf_name):
    """
    Processes a single PDF file's content (as bytes/buffer) and extracts the required data.
    Returns a DataFrame row or None on error.
    """
    try:
        # pdfplumber.open() can take a file-like object (like io.BytesIO)
        with pdfplumber.open(file_content) as pdf:
            if not pdf.pages:
                st.warning(f"Skipping **{pdf_name}**: File contains no pages.")
                return None

            first_page = pdf.pages[0]
            # Use 'precision' for potential better extraction in Streamlit environment
            text = first_page.extract_text(x_tolerance=1, y_tolerance=1)
            
            # Initialize all variables for safety
            outward_sales, outward_igst, outward_cgst, outward_sgst, outward_cess = 0.0, 0.0, 0.0, 0.0, 0.0
            outward_zero_sales, outward_zero_igst, outward_zero_cgst, outward_zero_sgst, outward_zero_cess = 0.0, 0.0, 0.0, 0.0, 0.0
            outward_nil_sales, outward_nil_igst, outward_nil_cgst, outward_nil_sgst, outward_nil_cess = 0.0, 0.0, 0.0, 0.0, 0.0
            inward_sales, inward_igst, inward_cgst, inward_sgst, inward_cess = 0.0, 0.0, 0.0, 0.0, 0.0
            non_gst_sales, non_gst_igst, non_gst_cgst, non_gst_sgst, non_gst_cess = 0.0, 0.0, 0.0, 0.0, 0.0
            GSTIN, FY, Month, Month_Index = "N/A", "N/A", "N/A", "N/A"

            # 1. Outward taxable supplies
            outward_match = re.search(outward_pattern, text, re.DOTALL)
            if outward_match:
                outward_sales = float(outward_match.group(1))
                outward_igst = float(outward_match.group(2))
                outward_cgst = float(outward_match.group(3))
                outward_sgst = float(outward_match.group(4))
                outward_cess = float(outward_match.group(5))
                        
            # 2. Outward taxable supplies (zero rated)
            outward_zero_match = re.search(outward_zero_pattern, text, re.DOTALL)
            if outward_zero_match:
                # Replace '-' with '0.00' and convert to float
                outward_zero_sales = float(outward_zero_match.group(1).replace('-', '0.00'))
                outward_zero_igst = float(outward_zero_match.group(2).replace('-', '0.00'))
                outward_zero_cgst = float(outward_zero_match.group(3).replace('-', '0.00'))
                outward_zero_sgst = float(outward_zero_match.group(4).replace('-', '0.00'))
                outward_zero_cess = float(outward_zero_match.group(5).replace('-', '0.00'))

            # 3. Other outward supplies (nil rated, exempted)
            outwad_nil_match = re.search(outward_nil_pattern, text, re.DOTALL)
            if outwad_nil_match:
                # Replace '-' with '0.00' and convert to float
                outward_nil_sales = float(outwad_nil_match.group(1).replace('-', '0.00'))
                outward_nil_igst = float(outwad_nil_match.group(2).replace('-', '0.00'))
                outward_nil_cgst = float(outwad_nil_match.group(3).replace('-', '0.00'))
                outward_nil_sgst = float(outwad_nil_match.group(4).replace('-', '0.00'))
                outward_nil_cess = float(outwad_nil_match.group(5).replace('-', '0.00'))

            # 4. Inward supplies (liable to reverse charge)
            inward_match = re.search(inward_pattern, text, re.DOTALL)
            if inward_match:
                inward_sales = float(inward_match.group(1))
                inward_igst = float(inward_match.group(2))
                inward_cgst = float(inward_match.group(3))
                inward_sgst = float(inward_match.group(4))
                inward_cess = float(inward_match.group(5))

            # 5. Non-GST outward supplies
            non_gst_match = re.search(non_gst_pattern, text, re.DOTALL)
            if non_gst_match:
                # Replace '-' with '0.00' and convert to float
                non_gst_sales = float(non_gst_match.group(1).replace('-', '0.00'))
                non_gst_igst = float(non_gst_match.group(2).replace('-', '0.00'))
                non_gst_cgst = float(non_gst_match.group(3).replace('-', '0.00'))
                non_gst_sgst = float(non_gst_match.group(4).replace('-', '0.00'))
                non_gst_cess = float(non_gst_match.group(5).replace('-', '0.00'))

            # --- Calculation ---
            # Your original calculation logic is preserved
            sales = outward_sales + outward_zero_sales + outward_nil_sales - inward_sales + non_gst_sales
            igst = outward_igst + outward_zero_igst + outward_nil_igst - inward_igst + non_gst_igst
            cgst = outward_cgst + outward_zero_cgst + outward_nil_cgst - inward_cgst + non_gst_cgst
            sgst = outward_sgst + outward_zero_sgst + outward_nil_sgst - inward_sgst + non_gst_sgst
            cess = outward_cess + outward_zero_cess + outward_nil_cess - inward_cess + non_gst_cess
            total = sales + igst + cgst + sgst + cess

            # --- Header Extraction ---
            GSTIN_pattern = r"GSTIN of the supplier\s*([A-Z0-9]+)"
            GSTIN_match = re.search(GSTIN_pattern, text)
            GSTIN = GSTIN_match.group(1).strip() if GSTIN_match else "N/A"

            fy_match = re.search(r"Year\s*(\d{4}-\d{2})", text)
            FY = fy_match.group(1) if fy_match else "N/A"

            month_match = re.search(r"Period\s*([A-Za-z]+)", text)
            Month = month_match.group(1).strip() if month_match else "N/A"

            Month_Index = month_to_index.get(Month, "N/A")

            # --- Result DataFrame ---
            data = {
                'GSTIN': [GSTIN],
                'FY': [FY],
                'MONTH': [Month],
                'Month_Index': [Month_Index],
                'Sales': [sales],
                'IGST': [igst],
                'CGST': [cgst],
                'SGST': [sgst],
                'Cess': [cess],
                'Total':[total],
            }
            return pd.DataFrame(data)
            
    except Exception as e:
        st.error(f"An error occurred while processing **{pdf_name}**: {e}")
        return None

def process_uploaded_files(uploaded_files):
    """
    Handles the iteration over uploaded files in a Streamlit context.
    """
    master = pd.DataFrame()
    
    # Use a progress bar for user feedback
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, uploaded_file in enumerate(uploaded_files):
        pdf_name = uploaded_file.name
        status_text.text(f"Processing file {i + 1} of {len(uploaded_files)}: {pdf_name}")
        
        # Read the file content into an in-memory buffer (BytesIO)
        file_content = io.BytesIO(uploaded_file.read())
        
        # Extract data
        data_row = extract_data_from_pdf_content(file_content, pdf_name)
        
        if data_row is not None:
            master = pd.concat([master, data_row], ignore_index=True)
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(uploaded_files))

    progress_bar.empty()
    status_text.text("Processing complete!")
    
    if not master.empty:
        # Apply the final sorting and deduplication logic from your original script
        master = master.sort_values(by=['FY','Month_Index','GSTIN'])
        master = master.drop_duplicates(subset=['FY','Month_Index','GSTIN'], keep='last')
        
        return master
    else:
        st.warning("No data was successfully extracted from the uploaded files.")
        return pd.DataFrame()

# --- Streamlit App Interface ---

def main():
    st.set_page_config(
        page_title="GSTR-3B PDF Consolidation Tool",
        layout="wide"
    )
    
    st.title("📄 GSTR-3B PDF Consolidation Tool")
    st.markdown("Upload multiple GSTR-3B PDFs to consolidate key financial figures into a single table and export as CSV.")

    # File Uploader component
    uploaded_files = st.file_uploader(
        "Upload GSTR-3B PDF Files", 
        type=["pdf"], 
        accept_multiple_files=True,
        help="Select all the GSTR-3B PDF files you wish to process in one go."
    )

    if uploaded_files:
        st.info(f"**{len(uploaded_files)}** PDF files ready for processing.")
        
        # Button to trigger the processing
        if st.button("🚀 Consolidate Data"):
            
            final_df = process_uploaded_files(uploaded_files)
            
            if not final_df.empty:
                st.success("Data Consolidation Successful!")
                
                # Display the resulting DataFrame
                st.subheader("Consolidated Data Summary")
                st.dataframe(final_df)
                
                # Provide a download button for the CSV file
                # Use io.StringIO to create a CSV buffer in memory
                csv_buffer = io.StringIO()
                final_df.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    label="Download GST_Summary.csv",
                    data=csv_buffer.getvalue(),
                    file_name="GST_Summary.csv",
                    mime="text/csv"
                )
    else:
        st.markdown(
            """
            *Awaiting file upload...*
            """
        )

if __name__ == "__main__":
    main()