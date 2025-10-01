Here’s your code with corrected indentation (Python):

```python
import streamlit as st
import requests
import pandas as pd
from io import BytesIO


TOOL_NAME = "All Products Downloader"

def run():
    st.set_page_config(page_title="WooCommerce All Products", layout="wide")
    st.title("Fetch All WooCommerce Products with Attributes")

    # WooCommerce API credentials
    WC_API_URL = st.secrets.get("WC_API_URL", "https://sustenance.co.in/wp-json/wc/v3")
    WC_CONSUMER_KEY = st.secrets.get("WC_CONSUMER_KEY")
    WC_CONSUMER_SECRET = st.secrets.get("WC_CONSUMER_SECRET")

    # --- Filter options ---
    st.sidebar.header("Product Filters")

    status_options = ["any", "publish", "pending", "draft", "private"]
    selected_status = st.sidebar.selectbox("Product Status", status_options, index=0)

    category_input = st.sidebar.text_input("Category (comma-separated names)")
    tag_input = st.sidebar.text_input("Tag (comma-separated names)")

    def get_category_ids(names):
        if not names.strip():
            return []
        resp = requests.get(
            f"{WC_API_URL}/products/categories",
            params={"per_page": 100},
            auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
        )
        if resp.status_code != 200:
            return []
        cats = resp.json()
        name_list = [n.strip().lower() for n in names.split(",") if n.strip()]
        return [c['id'] for c in cats if c['name'].lower() in name_list]

    def get_tag_ids(names):
        if not names.strip():
            return []
        resp = requests.get(
            f"{WC_API_URL}/products/tags",
            params={"per_page": 100},
            auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
        )
        if resp.status_code != 200:
            return []
        tags = resp.json()
        name_list = [n.strip().lower() for n in names.split(",") if n.strip()]
        return [t['id'] for t in tags if t['name'].lower() in name_list]

    if st.button("Fetch All Products"):
        with st.spinner("Fetching products..."):
            all_rows = []
            page = 1
            max_pages = 50  # Safety to prevent infinite loop

            # Prepare filter IDs
            cat_ids = get_category_ids(category_input)
            tag_ids = get_tag_ids(tag_input)

            progress = st.progress(0)
            total_fetched = 0

            while page <= max_pages:
                # Compose filter params
                params = {
                    "per_page": 100,
                    "page": page,
                    "status": selected_status,
                    "order": "asc",
                    "orderby": "id"
                }
                if cat_ids:
                    params["category"] = ",".join(map(str, cat_ids))
                if tag_ids:
                    params["tag"] = ",".join(map(str, tag_ids))

                response = requests.get(
                    f"{WC_API_URL}/products",
                    params=params,
                    auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
                )

                if response.status_code != 200:
                    st.error(f"Error fetching products: {response.status_code}")
                    break

                products = response.json()
                if not products:
                    break

                for p in products:
                    base_info = {
                        "ID": p.get("id"),
                        "Parent ID": None,
                        "Name": p.get("name"),
                        "SKU": p.get("sku"),
                        "Price": p.get("price"),
                        "Regular Price": p.get("regular_price"),
                        "Sale Price": p.get("sale_price"),
                        "Stock Quantity": p.get("stock_quantity"),
                        "Status": p.get("status"),
                        "Type": p.get("type"),
                        "Description": p.get("description"),
                        "Short Description": p.get("short_description"),
                        "Categories": ", ".join([c['name'] for c in p.get("categories", [])]),
                        "Tags": ", ".join([t['name'] for t in p.get("tags", [])]),
                        "Attributes": ", ".join([f"{a['name']}:{','.join(a['options'])}" for a in p.get("attributes", [])])
                    }
                    all_rows.append(base_info)

                    # Handle variable products
                    if p.get("type") == "variable":
                        var_page = 1
                        while True:
                            var_resp = requests.get(
                                f"{WC_API_URL}/products/{p['id']}/variations",
                                params={"per_page": 100, "page": var_page},
                                auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
                            )

                            if var_resp.status_code != 200:
                                st.warning(f"Error fetching variations for product {p['id']}")
                                break

                            variations = var_resp.json()
                            if not variations:
                                break

                            for v in variations:
                                var_info = {
                                    "ID": v.get("id"),
                                    "Parent ID": p.get("id"),
                                    "Name": v.get("name") or p.get("name"),
                                    "SKU": v.get("sku"),
                                    "Price": v.get("price"),
                                    "Regular Price": v.get("regular_price"),
                                    "Sale Price": v.get("sale_price"),
                                    "Stock Quantity": v.get("stock_quantity"),
                                    "Status": v.get("status"),
                                    "Type": v.get("type"),
                                    "Description": v.get("description"),
                                    "Short Description": v.get("short_description"),
                                    "Categories": ", ".join([c['name'] for c in p.get("categories", [])]),
                                    "Tags": ", ".join([t['name'] for t in p.get("tags", [])]),
                                    "Attributes": ", ".join([f"{a['name']}:{a.get('option','')}" for a in v.get("attributes", [])])
                                }
                                all_rows.append(var_info)

                            var_page += 1
                            time.sleep(0.1)  # Avoid hammering the API

                page += 1
                total_fetched += len(products)
                progress.progress(min(page / max_pages, 1.0))
                time.sleep(0.1)

            progress.empty()

            if all_rows:
                df_all = pd.DataFrame(all_rows)
                st.success(f"Fetched {len(df_all)} rows including variations.")
                st.dataframe(df_all, use_container_width=True)

                # --- Excel download ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_all.to_excel(writer, index=False, sheet_name="All Products")
                    workbook = writer.book
                    worksheet = writer.sheets["All Products"]
                    # Auto-width columns
                    for i, col in enumerate(df_all.columns):
                        max_len = max(df_all[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, max_len)
                output.seek(0)

                st.download_button(
                    label="Download as Excel",
                    data=output,
                    file_name="woocommerce_all_products.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No products found.")
```
