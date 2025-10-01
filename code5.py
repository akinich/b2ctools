TOOL_NAME = "WooCommerce All Products Downloader"

def run():
    import streamlit as st
    import requests
    import pandas as pd
    from io import BytesIO

    st.set_page_config(page_title="WooCommerce All Products", layout="wide")
    st.title("Fetch All WooCommerce Products with Attributes")

    # WooCommerce API credentials
    WC_API_URL = st.secrets.get("WC_API_URL", "https://sustenance.co.in/wp-json/wc/v3")
    WC_CONSUMER_KEY = st.secrets.get("WC_CONSUMER_KEY")
    WC_CONSUMER_SECRET = st.secrets.get("WC_CONSUMER_SECRET")

    if st.button("Fetch All Products"):
        with st.spinner("Fetching products..."):
            all_rows = []
            page = 1

            while True:
                response = requests.get(
                    f"{WC_API_URL}/products",
                    params={
                        "per_page": 100,
                        "page": page,
                        "status": "any",  # include drafts, pending, published, etc.
                        "order": "asc",
                        "orderby": "id"
                    },
                    auth=(WC_CONSUMER_KEY, WC_CONSUMER_SECRET)
                )

                if response.status_code != 200:
                    st.error(f"Error fetching products: {response.status_code} - {response.text}")
                    break

                products = response.json()
                if not products:
                    break

                for p in products:
                    # Base product info
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

                page += 1

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
