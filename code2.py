import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from io import BytesIO


TOOL_NAME = "Shipping Label Generator"

def run():
    # === DEFAULT CONSTANTS ===
    DEFAULT_WIDTH_MM = 50
    DEFAULT_HEIGHT_MM = 30
    FONT_ADJUSTMENT = 2  # for printer safety
    MIN_SPACING_RATIO = 0.1  # 10% of label height as minimum spacing

    # Built-in fonts
    AVAILABLE_FONTS = [
        "Helvetica",
        "Helvetica-Bold",
        "Times-Roman",
        "Times-Bold",
        "Courier",
        "Courier-Bold"
    ]

    # === HELPER FUNCTIONS ===
    def wrap_text_to_width(text, font_name, font_size, max_width):
        """Wrap a single line of text into multiple lines that fit within max_width."""
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
        """Draw order number and customer name on PDF label with minimum spacing."""
        order_no_text = f"#{order_no.strip()}"
        customer_name_text = customer_name.strip().upper()  # <--- convert to all caps

        # Calculate minimum spacing
        min_spacing = height * MIN_SPACING_RATIO
        half_height = (height - min_spacing) / 2  # top and bottom sections

        # --- Order # Section (top) ---
        order_lines = [order_no_text]
        order_font_size = find_max_font_size_for_multiline(order_lines, width, half_height, font_name)
        order_font_size = max(order_font_size - FONT_ADJUSTMENT + font_override, 1)
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

        # --- Horizontal Line with spacing ---
        line_y = half_height + min_spacing/2
        c.setLineWidth(0.5)
        c.line(2, line_y, width-2, line_y)

        # --- Customer Name Section (bottom) ---
        words = customer_name_text.split()
        if len(words) == 2:
            cust_lines = words
        else:
            cust_lines = [customer_name_text]

        line_font_sizes = []
        for line in cust_lines:
            max_height_per_line = half_height / len(cust_lines)
            fs = find_max_font_size_for_multiline([line], width, max_height_per_line, font_name)
            fs = max(fs - FONT_ADJUSTMENT + font_override, 1)
            line_font_sizes.append(fs)

        total_height_cust = sum(line_font_sizes) + 2*(len(cust_lines)-1)
        start_y_cust = (half_height - total_height_cust)/2
        for i, line in enumerate(cust_lines):
            fs = line_font_sizes[i]
            c.setFont(font_name, fs)
            x = (width - stringWidth(line, font_name, fs))/2
            y = start_y_cust + (len(cust_lines)-i-1)*(fs + 2)
            c.drawString(x, y, line)

    def create_pdf(df, font_name, width, height, font_override=0):
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

    # === STREAMLIT UI ===
    st.title("Excel/CSV to Label PDF Generator (Order # + Name)")
    st.write("Generates PDF labels with Order # on top (#prefix) and Name below, separated by a horizontal line. Names with exactly 2 words are split into 2 lines. Minimum spacing ensures visual balance.")

    # --- User Inputs ---
    selected_font = st.selectbox("Select font", AVAILABLE_FONTS, index=AVAILABLE_FONTS.index("Courier-Bold"))
    font_override = st.slider("Font size override (+/- points)", min_value=-5, max_value=5, value=0)
    width_mm = st.number_input("Label width (mm)", min_value=10, max_value=500, value=DEFAULT_WIDTH_MM)
    height_mm = st.number_input("Label height (mm)", min_value=10, max_value=500, value=DEFAULT_HEIGHT_MM)
    remove_duplicates = st.checkbox("Remove duplicate labels", value=True)

    # --- File Uploader ---
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
    df = None
    total_entries = duplicates_removed = 0

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file, engine="openpyxl")
            st.success("File loaded successfully!")

            # Normalize column names
            df.columns = [col.strip().lower() for col in df.columns]
            required_cols = ["order #", "name"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                st.error(f"Missing required columns: {', '.join(missing_cols)}")
                df = None

            # Strip whitespace
            if df is not None:
                df["order #"] = df["order #"].astype(str).str.strip()
                df["name"] = df["name"].astype(str).str.strip()

                # Summary before removing duplicates
                total_entries = len(df)

                # Remove duplicates if checkbox checked
                if remove_duplicates:
                    before_count = len(df)
                    df = df.drop_duplicates(subset=["order #", "name"], keep="first")
                    duplicates_removed = before_count - len(df)

        except Exception as e:
            st.error(f"Error reading file: {e}")

    if df is not None:
        # Preview with index starting from 1
        df_preview = df.reset_index(drop=True)
        df_preview.index += 1
        st.write("Preview of data:")
        st.dataframe(df_preview[["order #", "name"]])

        # Summary section
        st.markdown("### Summary")
        st.write(f"- Total entries in file: {total_entries}")
        st.write(f"- Duplicates removed: {duplicates_removed}")
        st.write(f"- Labels/pages to be generated: {len(df)}")

        if st.button("Generate PDF"):
            if df.empty:
                st.warning("No valid data found!")
            else:
                with st.spinner("Generating PDF..."):
                    pdf_buffer = create_pdf(df, selected_font, width_mm*mm, height_mm*mm, font_override)
                st.success("PDF generated!")
                st.download_button(
                    label="Download PDF",
                    data=pdf_buffer,
                    file_name="labels.pdf",
                    mime="application/pdf"
                )
