import streamlit as st
import pandas as pd
from PyPDF2 import PdfMerger
import os
from pathlib import Path
import io

TOOL_NAME = "MRP Label PDF Merger"

def run():
    st.set_page_config(page_title="MRP Label Merger", page_icon="📄", layout="wide")

    st.title("📄 MRP Label PDF Merger")
    st.markdown("Upload an Excel file to merge MRP label PDFs based on quantities")

    # File uploader
    uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type=['xlsx'])

    if uploaded_file is not None:
        try:
            # Read Excel file
            excel_file = pd.ExcelFile(uploaded_file)
            
            # Check if "Item Summary" sheet exists
            if "Item Summary" not in excel_file.sheet_names:
                st.error("❌ Error: Sheet 'Item Summary' not found in the Excel file!")
                st.info(f"Available sheets: {', '.join(excel_file.sheet_names)}")
                st.stop()
            
            # Read the Item Summary sheet
            df = pd.read_excel(uploaded_file, sheet_name="Item Summary")
            
            # Create a mapping of lowercase column names to original column names
            column_mapping = {col.lower().strip(): col for col in df.columns}
            
            # Check for required columns (case-insensitive)
            required_columns_lower = ["item id", "variation id", "quantity"]
            required_columns_display = ["Item ID", "Variation ID", "Quantity"]
            
            missing_columns = []
            column_map = {}
            
            for req_col_lower, req_col_display in zip(required_columns_lower, required_columns_display):
                if req_col_lower in column_mapping:
                    column_map[req_col_display] = column_mapping[req_col_lower]
                else:
                    missing_columns.append(req_col_display)
            
            if missing_columns:
                st.error(f"❌ Error: Missing required columns: {', '.join(missing_columns)}")
                st.info(f"Available columns: {', '.join(df.columns.tolist())}")
                st.stop()
            
            # Rename columns to standardized names for easier processing
            df = df.rename(columns={
                column_map["Item ID"]: "Item ID",
                column_map["Variation ID"]: "Variation ID",
                column_map["Quantity"]: "quantity"
            })
            
            # Remove empty rows (rows where all required columns are NaN)
            df = df.dropna(subset=["Item ID", "Variation ID", "quantity"], how='all')
            
            # Process button
            if st.button("🚀 Process and Merge PDFs", type="primary"):
                with st.spinner("Processing PDFs..."):
                    merger = PdfMerger()
                    total_pages = 0
                    processed_items = 0
                    missing_pdfs = []
                    errors = []
                    
                    # Path to mrp_label folder
                    label_folder = Path("mrp_label")
                    
                    if not label_folder.exists():
                        st.error("❌ Error: 'mrp_label' folder not found in the current directory!")
                        st.stop()
                    
                    # Progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Process each row
                    for idx, row in df.iterrows():
                        try:
                            item_id = row["Item ID"]
                            variation_id = row["Variation ID"]
                            quantity = row["quantity"]
                            
                            # Skip if quantity is 0, NaN, or negative
                            if pd.isna(quantity) or quantity <= 0:
                                continue
                            
                            # Convert to int
                            quantity = int(quantity)
                            
                            # Determine which ID to use
                            if pd.notna(variation_id) and variation_id != 0:
                                use_id = int(variation_id)
                            else:
                                use_id = int(item_id)
                            
                            # PDF file path
                            pdf_path = label_folder / f"{use_id}.pdf"
                            
                            # Check if PDF exists
                            if not pdf_path.exists():
                                missing_pdfs.append(use_id)
                                continue
                            
                            # Merge the PDF 'quantity' times
                            for _ in range(quantity):
                                merger.append(str(pdf_path))
                                total_pages += 1
                            
                            processed_items += 1
                            
                        except Exception as e:
                            errors.append(f"Row {idx + 2}: {str(e)}")
                        
                        # Update progress
                        progress = (idx + 1) / len(df)
                        progress_bar.progress(progress)
                        status_text.text(f"Processing: {idx + 1}/{len(df)} rows")
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Generate output filename
                    excel_filename = uploaded_file.name.replace('.xlsx', '')
                    output_filename = f"mrp_labels_{excel_filename}.pdf"
                    
                    # Save merged PDF to bytes
                    pdf_bytes = io.BytesIO()
                    merger.write(pdf_bytes)
                    merger.close()
                    pdf_bytes.seek(0)
                    
                    # Display summary
                    st.success("✅ Processing Complete!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Items Processed", processed_items)
                    with col2:
                        st.metric("Total Pages", total_pages)
                    with col3:
                        st.metric("Missing PDFs", len(missing_pdfs))
                    
                    # Show missing PDFs
                    if missing_pdfs:
                        st.warning("⚠️ The following Item/Variation IDs were not found:")
                        st.code(", ".join(map(str, missing_pdfs)))
                    
                    # Show errors if any
                    if errors:
                        st.error("❌ Errors encountered:")
                        for error in errors:
                            st.text(error)
                    
                    # Download button
                    if total_pages > 0:
                        st.download_button(
                            label="📥 Download Merged PDF",
                            data=pdf_bytes,
                            file_name=output_filename,
                            mime="application/pdf",
                            type="primary"
                        )
                    else:
                        st.warning("⚠️ No PDFs were merged. Please check your data and PDF files.")
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)

    else:
        st.info("👆 Please upload an Excel file to get started")
        
        # Instructions
        with st.expander("📖 Instructions"):
            st.markdown("""
            ### How to use:
            1. **Upload Excel File**: Click the upload button and select your .xlsx file
            2. **Required Sheet**: Make sure your Excel file has a sheet named "Item Summary"
            3. **Required Columns**: 
               - `Item ID`: The item identifier
               - `Variation ID`: The variation identifier (use 0 if no variation)
               - `quantity`: Number of times to include the label
            4. **PDF Files**: Place all PDF files in a folder named `mrp_label` in the same directory as this script
            5. **File Naming**: PDF files should be named as `{ID}.pdf` (e.g., `7413.pdf`)
            
            ### Logic:
            - If `Variation ID` is 0 or empty, the script uses `Item ID`
            - If `Variation ID` is not 0, the script uses `Variation ID`
            - The corresponding PDF is merged based on the quantity specified
            
            ### Output:
            - Merged PDF named: `mrp_labels_{your_excel_filename}.pdf`
            - Summary of processed items and missing PDFs
            """)

if __name__ == "__main__":
    run()
