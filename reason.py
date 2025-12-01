# 3. File Uploaders in sidebar
st.sidebar.header("Step 1: Upload Returns Data")

# --- DOWNLOAD TEMPLATE SECTION ---
with st.sidebar.expander("📥 Download Return Data Templates"):
    st.caption("Download sample templates showing the required column format for each platform.")
    
    # Create sample templates for each platform
    template_platform = st.selectbox(
        "Select Platform Template:",
        options=['flipkart', 'ajio', 'amazon', 'meesho', 'firstcry', 'amazon_flex'],
        format_func=lambda x: DISPLAY_NAME_MAPPING.get(x, x.capitalize()),
        key='template_platform'
    )
    
    # Generate sample data for selected platform
    mapping = COLUMN_MAPPING[template_platform]
    
    if mapping.get('qty_col'):
        template_data = {
            mapping['sku_col']: ['SKU001', 'SKU002', 'SKU003'],
            mapping['reason_col']: ['Size Issue', 'Quality Issue', 'Wrong Product'],
            mapping['qty_col']: [1, 2, 1]
        }
    else:
        template_data = {
            mapping['sku_col']: ['SKU001', 'SKU002', 'SKU003'],
            mapping['reason_col']: ['Size Issue', 'Quality Issue', 'Wrong Product']
        }
    
    template_df = pd.DataFrame(template_data)
    template_csv = template_df.to_csv(index=False).encode('utf-8')
    
    display_name = DISPLAY_NAME_MAPPING.get(template_platform, template_platform.capitalize())
    st.download_button(
        label=f"Download {display_name} Template (CSV) ⬇️",
        data=template_csv,
        file_name=f'{template_platform}_return_template.csv',
        mime='text/csv',
        help=f"Downloads a sample template with required columns: {', '.join(template_data.keys())}"
    )
# --- END DOWNLOAD TEMPLATE SECTION ---

uploaded_returns_files = st.sidebar.file_uploader(
    "Upload Returns files (.csv, .xlsx, or .zip)",
    accept_multiple_files=True,
    type=['xlsx', 'csv', 'zip'],
    key='returns_uploader'
)
