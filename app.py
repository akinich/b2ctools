"""
Multi-Tool Dashboard - Dynamic module loader for Streamlit applications.

This dashboard automatically discovers and loads Python modules that follow the pattern
'code*.py' and contain a 'run()' function. Modules can optionally define:
- TOOL_NAME: Custom display name (str)
- TOOL_DESCRIPTION: Brief description shown in sidebar (str)
- TOOL_ORDER: Sort priority, lower numbers appear first (int, default: 999)
"""

import streamlit as st
import os
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import traceback

# Configuration constants
MODULE_PATTERN_PREFIX = 'code'
MODULE_PATTERN_SUFFIX = '.py'
DEFAULT_TOOL_ORDER = 999

# Set page config (must be first Streamlit command)
st.set_page_config(page_title="Multi-Tool Dashboard", layout="wide")


@st.cache_resource
def discover_and_load_modules() -> Tuple[Dict[str, Any], List[str]]:
    """
    Discover and load all valid tool modules.
    
    Returns:
        Tuple containing:
        - Dictionary mapping display names to module objects
        - List of error messages from failed module loads
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.resolve()
    
    # Find all matching module files
    module_files = [
        f for f in os.listdir(script_dir) 
        if f.startswith(MODULE_PATTERN_PREFIX) and f.endswith(MODULE_PATTERN_SUFFIX)
    ]
    
    modules = {}
    errors = []
    
    # Ensure script directory is in Python path
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    
    for file in sorted(module_files):
        module_name = file[:-3]  # Remove .py extension
        
        try:
            module_instance = importlib.import_module(module_name)
            
            # Validate that module has required 'run' function
            if not hasattr(module_instance, 'run'):
                errors.append(f"⚠️ Module '{module_name}' missing required 'run()' function")
                continue
            
            if not callable(getattr(module_instance, 'run')):
                errors.append(f"⚠️ Module '{module_name}' has 'run' but it's not callable")
                continue
            
            # Extract module metadata
            display_name = getattr(
                module_instance, 
                'TOOL_NAME', 
                module_name.replace('_', ' ').title()
            )
            description = getattr(module_instance, 'TOOL_DESCRIPTION', '')
            order = getattr(module_instance, 'TOOL_ORDER', DEFAULT_TOOL_ORDER)
            
            modules[display_name] = {
                'module': module_instance,
                'description': description,
                'order': order,
                'file': file
            }
            
        except Exception as e:
            error_msg = f"❌ Failed to load '{module_name}': {str(e)}"
            errors.append(error_msg)
            # Log full traceback for debugging
            print(f"\nError loading {module_name}:")
            traceback.print_exc()
    
    # Sort modules by order, then by name
    sorted_modules = dict(
        sorted(modules.items(), key=lambda x: (x[1]['order'], x[0]))
    )
    
    return sorted_modules, errors


def display_module_errors(errors: List[str]):
    """Display module loading errors in an expandable section."""
    if errors:
        with st.sidebar.expander(f"⚠️ Module Loading Issues ({len(errors)})", expanded=False):
            for error in errors:
                st.text(error)


def run_selected_module(module_data: Dict[str, Any], module_name: str):
    """
    Safely execute the selected module's run function.
    
    Args:
        module_data: Dictionary containing module information
        module_name: Display name of the module for error reporting
    """
    try:
        module_data['module'].run()
    except Exception as e:
        st.error(f"### Error running '{module_name}'")
        st.error(f"**Error type:** {type(e).__name__}")
        st.error(f"**Message:** {str(e)}")
        
        with st.expander("🔍 Full Error Traceback"):
            st.code(traceback.format_exc())
        
        st.info("💡 **Tip:** Check the module's code or contact the module developer.")


def main():
    """Main application entry point."""
    st.title("🛠️ Multi-Tool Dashboard")
    
    # Load modules (cached)
    modules, errors = discover_and_load_modules()
    
    # Display any loading errors in sidebar
    display_module_errors(errors)
    
    # Main application logic
    if modules:
        st.sidebar.title("Available Tools")
        
        # Create radio options with descriptions
        tool_names = list(modules.keys())
        
        # Add descriptions to help text if available
        help_text = "Select a tool from the list below"
        
        app_mode = st.sidebar.radio(
            "Choose a tool:",
            tool_names,
            help=help_text
        )
        
        # Display tool description if available
        if modules[app_mode]['description']:
            st.sidebar.markdown(f"*{modules[app_mode]['description']}*")
        
        st.sidebar.markdown("---")
        
        # Show module info in expander
        with st.sidebar.expander("ℹ️ Module Info"):
            st.text(f"File: {modules[app_mode]['file']}")
            st.text(f"Order: {modules[app_mode]['order']}")
        
        # Run the selected module
        run_selected_module(modules[app_mode], app_mode)
        
    else:
        st.info(
            f"""
            ### No tool modules found
            
            **To add tools:**
            1. Create Python files starting with `{MODULE_PATTERN_PREFIX}` (e.g., `code_my_tool.py`)
            2. Define a `run()` function in each file
            3. Optionally add metadata:
               - `TOOL_NAME = "My Tool"` - Custom display name
               - `TOOL_DESCRIPTION = "Does something cool"` - Brief description
               - `TOOL_ORDER = 1` - Sort priority (lower = higher in list)
            
            **Example:**
            ```python
            # code_example.py
            TOOL_NAME = "Example Tool"
            TOOL_DESCRIPTION = "A sample tool"
            TOOL_ORDER = 1
            
            def run():
                import streamlit as st
                st.write("Hello from Example Tool!")
            ```
            """
        )


if __name__ == "__main__":
    main()
