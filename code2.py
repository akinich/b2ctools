import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from io import BytesIO
import os
import zipfile
from PyPDF2 import PdfReader, PdfWriter

TOOL_NAME = "Label Generator"

# ====== SHIPPING LABELS LOGIC (EXISTING) ======
def wrap_text_to_width(text, font_name, font_size, max_width):
    words = text.split()
    if not words:
        return [""]
    lines = []
    current_line = words[0]
    for word in words[1:]:
        test_line = f"{current_line} {word}"
        if stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

def find_max_font_size_for_multiline(lines, max_width, max_height, font_name):
    font_size = 1
    while True:
        wrapped_lines = []
        for line in lines:
            wrapped_lines.extend(wrap_text_to_width(line, font_name, font_size, max_width))
        total_height = len(wrapped_lines) * font_size + (len(wrapped_lines) - 1) * 2
        max_line_width = max(stringWidth(line, font_name, font_size) for line in wrapped_lines)
        if max_line_width > (max_width - 4) or total_height > (max_height - 4):
            return max(font_size - 1, 1)
        font_size += 1

def draw_label_pdf(c, order_no, customer_name, font_name, width, height, font_override=0):
    DEFAULT_FONT_ADJUSTMENT = 2
    MIN_SPACING_RATIO = 0.1
    order_no_text = f"#{order_no.strip()}"
    customer_name_text = customer_name.strip().upper()
    min_spacing = height * MIN_SPACING_RATIO
    half_height = (height - min_spacing) / 2

    # Order # Section
    order_lines = [order_no_text]
    order_font_size = find_max_font_size_for_multiline(order_lines, width, half_height, font_name)
    order_font_size = max(order_font_size - DEFAULT_FONT_ADJUSTMENT + font_override, 1)
    c.setFont(font_name, order_font_size)
    wrapped_order = []
    for line in order_lines:
        wrapped_order.extend(wrap_text_to_width(line, font_name, order_font_size, width))
    total_height_order = len(wrapped_order) * order_font_size + (len(wrapped_order)-1)*2
    start_y_order = height - half_height + (half_height - total_height_order)/2
    for i, line in enumerate(wrapped_order):
        x = (width - stringWidth(line, font_name, order_font_size))/2
        y = start_y_order + (len(wrapped_order)-i-1)*(order_font_size + 2)
        c.drawString(x, y, line)

    # Horizontal Line
    line_y = half_height + min_spacing/2
    c.setLineWidth(0.5)
    c.line(2, line_y, width-2, line_y)

    # Customer Name Section (bottom)
    words = customer_name_text.split()
    if len(words) == 2:
        cust_lines = words
    else:
        cust_lines = [customer_name_text]

    line_font_sizes = []
    for line in cust_lines:
        max_height_per_line = half_height / len(cust_lines)
        fs = find_max_font_size_for_multiline([line], width, max_height_per_line, font_name)
        fs = max(fs - DEFAULT_FONT_ADJUSTMENT + font_override, 1)
        line_font_sizes.append(fs)

    total_height_cust = sum(line_font_sizes) + 2*(len(cust_lines)-1)
    start_y_cust = (half_height - total_height_cust)/2
    for i, line in enumerate(cust_lines):
        fs = line_font_sizes[i]
        c.setFont(font_name, fs)
        x = (width - stringWidth(line, font_name, fs))/2
        y = start_y_cust + (len(cust_lines)-i-1)*(fs + 2)
        c.drawString(x, y, line)

def create_shipping_pdf(df, font_name, width, height, font_override=0):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    for idx, row in df.iterrows():
        order_no = str(row["order #"]).strip()
        customer_name = str(row["name"]).strip()
        draw_label_pdf(c, order_no, customer_name, font_name, width, height, font_override)
        c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ====== MRP LABELS LOGIC (NEW) ======
def create_mrp_labels_pdf(df, mrp_folder):
    missing_files = []
    output_pdf = PdfWriter()
    for idx, row in df.iterrows():
        item_id = str(row["Item ID"]).strip()
        variation_id = str(row["Variation ID"]).strip()
        quantity = int(row["Quantity"]) if str(row["Quantity"]).strip().isdigit() else 1

        # Determine filename
        if variation_id == "0":
            filename = f"{item_id}.pdf"
            label_key = item_id
        else:
            filename = f"{variation_id}.pdf"
            label_key = variation_id

        label_path = os.path.join(mrp_folder, filename)

        if not os.path.isfile(label_path):
            missing_files.append(filename)
            continue

        try:
            reader = PdfReader(label_path)
            for _ in range(quantity):
                output_pdf.add_page(reader.pages[0])
        except Exception as e:
            missing_files.append(filename)

    buffer = BytesIO()
    if output_pdf.pages:
        output_pdf.write(buffer)
        buffer.seek(0)
    else:
        buffer = None # No valid labels
    return buffer, missing_files

# ====== MAIN STREAMLIT UI ======
def run():
    # === DEFAULT CONSTANTS ===
    DEFAULT_WIDTH_MM = 50
    DEFAULT_HEIGHT_MM = 30
    AVAILABLE_FONTS = [
        "Helvetica",
        "Helvetica-Bold",
        "Times-Roman",
        "Times-Bold",
        "Courier",
        "Courier-Bold"
    ]
    MRP_LABEL_FOLDER = "mrp_label"

    st.title("Excel to Shipping & MRP Label PDF Generator")
    st.write(
        "Upload your Excel file. Generates two PDFs: "
        "1) Shipping labels (`order` sheet) and 2) MRP labels (`Item summary` sheet) using existing PDFs in `mrp_label` folder. "
        "Both are zipped for download."
    )

    # --- User Inputs for Shipping Labels ---
    selected_font = st.selectbox("Select font", AVAILABLE_FONTS, index=AVAILABLE_FONTS.index("Courier-Bold"))
    font_override = st.slider("Font size override (+/- points)", min_value=-5, max_value=5, value=0)
    width_mm = st.number_input("Shipping Label width (mm)", min_value=10, max_value=500, value=DEFAULT_WIDTH_MM)
    height_mm = st.number_input("Shipping Label height (mm)", min_value=10, max_value=500, value=DEFAULT_HEIGHT_MM)
    remove_duplicates = st.checkbox("Remove duplicate shipping labels", value=True)

    # --- File Uploader ---
    uploaded_file = st.file_uploader("Upload Excel (.xlsx) file", type=["xlsx"])
    df_shipping = None
    df_mrp = None
    shipping_total_entries = shipping_duplicates_removed = 0

    # MRP label folder check
    if not os.path.isdir(MRP_LABEL_FOLDER):
        st.warning(f"Folder '{MRP_LABEL_FOLDER}' not found in app directory! Please add it and required PDFs before generating MRP labels.")

    excel_filename = uploaded_file.name if uploaded_file else "labels"
    zip_filename = os.path.splitext(excel_filename)[0] + ".zip"

    if uploaded_file:
        try:
            xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
            # --- SHIPPING LABELS ("order" sheet) ---
            if "order" in xls.sheet_names:
                df_shipping = pd.read_excel(xls, sheet_name="order")
                df_shipping.columns = [col.strip().lower() for col in df_shipping.columns]
                required_cols = ["order #", "name"]
                missing_cols = [col for col in required_cols if col not in df_shipping.columns]
                if missing_cols:
                    st.error(f"Missing required columns in 'order' sheet: {', '.join(missing_cols)}")
                    df_shipping = None
                else:
                    df_shipping["order #"] = df_shipping["order #"].astype(str).str.strip()
                    df_shipping["name"] = df_shipping["name"].astype(str).str.strip()
                    shipping_total_entries = len(df_shipping)
                    if remove_duplicates:
                        before_count = len(df_shipping)
                        df_shipping = df_shipping.drop_duplicates(subset=["order #", "name"], keep="first")
                        shipping_duplicates_removed = before_count - len(df_shipping)
            else:
                st.error("Sheet 'order' not found in Excel file.")

            # --- MRP LABELS ("Item summary" sheet) ---
            if "Item summary" in xls.sheet_names:
                df_mrp = pd.read_excel(xls, sheet_name="Item summary")
                required_cols_mrp = ["Item ID", "Variation ID", "Quantity"]
                missing_cols_mrp = [col for col in required_cols_mrp if col not in df_mrp.columns]
                if missing_cols_mrp:
                    st.error(f"Missing required columns in 'Item summary' sheet: {', '.join(missing_cols_mrp)}")
                    df_mrp = None
            else:
                st.error("Sheet 'Item summary' not found in Excel file.")

        except Exception as e:
            st.error(f"Error reading Excel file: {e}")

    # --- Preview/Summary of Shipping Labels ---
    if df_shipping is not None:
        df_preview = df_shipping.reset_index(drop=True)
        df_preview.index += 1
        st.write("Preview of Shipping Labels Data ('order' sheet):")
        st.dataframe(df_preview[["order #", "name"]])

        st.markdown("### Shipping Labels Summary")
        st.write(f"- Total entries in file: {shipping_total_entries}")
        st.write(f"- Duplicates removed: {shipping_duplicates_removed}")
        st.write(f"- Labels/pages to be generated: {len(df_shipping)}")

    # --- Generate PDFs and ZIP ---
    if st.button("Generate ZIP with Shipping & MRP Labels"):
        if df_shipping is None or df_mrp is None:
            st.warning("No valid data found in one or both sheets!")
        else:
            with st.spinner("Generating PDFs and ZIP..."):
                # --- Generate Shipping PDF ---
                shipping_buffer = create_shipping_pdf(
                    df_shipping,
                    selected_font,
                    width_mm * mm,
                    height_mm * mm,
                    font_override
                )

                # --- Generate MRP Labels PDF ---
                mrp_buffer, missing_mrp_files = create_mrp_labels_pdf(
                    df_mrp,
                    MRP_LABEL_FOLDER
                )

                # --- Prepare ZIP ---
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    # Add shipping PDF
                    zf.writestr("shipping labels.pdf", shipping_buffer.read())
                    # Add MRP labels PDF if there are valid pages
                    if mrp_buffer:
                        zf.writestr("mrp_labels.pdf", mrp_buffer.read())
                    else:
                        zf.writestr("mrp_labels.pdf", b"")  # Empty PDF if none found
                    # Add summary of missing files
                    summary_text = "Missing MRP PDFs:\n" + "\n".join(missing_mrp_files) if missing_mrp_files else "All required MRP PDFs found."
                    zf.writestr("missing_mrp_labels.txt", summary_text)

                zip_buf.seek(0)

            st.success("ZIP generated!")
            st.write("Summary of missing MRP label PDFs:")
            if missing_mrp_files:
                st.error("\n".join(missing_mrp_files))
            else:
                st.info("All required MRP PDFs found.")

            st.download_button(
                label="Download ZIP",
                data=zip_buf,
                file_name=zip_filename,
                mime="application/zip"
            )

if __name__ == "__main__":
    run()
