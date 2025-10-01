import streamlit as st
import os
import importlib

st.set_page_config(page_title="Multi-Tool Dashboard", layout="wide")
st.title("Multi-Tool Dashboard")

# --- Scan for modules ---
module_files = [f for f in os.listdir('.') if f.startswith('code') and f.endswith('.py')]
modules = {}

for file in sorted(module_files):
    module_name = file[:-3]  # remove .py
    try:
        mod = importlib.import_module(module_name)
        if hasattr(mod, 'run'):
            # Use a readable name by replacing underscores with spaces and capitalizing
            display_name = getattr(mod, 'TOOL_NAME', module_name.replace('_', ' ').title())
            modules[display_name] = mod
    except Exception as e:
        st.warning(f"Failed to load module {module_name}: {e}")

# --- Sidebar selector ---
if modules:
    app_mode = st.sidebar.radio("Select a tool:", list(modules.keys()))
    modules[app_mode].run()
else:
    st.info("No modules found with a 'run()' function.")
