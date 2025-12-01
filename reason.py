st.sidebar.header("Step 2: Upload Sales/Order Data")
st.sidebar.caption("Must contain 'MSKU', 'Customer Shipments', and 'Platform' columns.")

# --- NEW ADDITION: Template Download Button ---
# Create a dummy dataframe for the template
template_data = {
    'MSKU': ['SKU_EXAMPLE_1', 'SKU_EXAMPLE_2'],
    'Customer Shipments': [10, 5],
    'Platform': ['Amazon', 'Flipkart']
}
template_df = pd.DataFrame(template_data)
template_csv = template_df.to_csv(index=False).encode('utf-8')

st.sidebar.download_button(
    label="📄 Download Sales Template (.csv)",
    data=template_csv,
    file_name='sales_data_template.csv',
    mime='text/csv',
    help="Click to download a sample CSV file with the required columns."
)
# --- END NEW ADDITION ---

uploaded_sales_file = st.sidebar.file_uploader(
    "Upload Single Sales/Order File (for Return %)",
    type=['xlsx', 'csv'],
    key='sales_uploader'
)
