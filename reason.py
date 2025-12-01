import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import io
import xlsxwriter # <-- ENSURE THIS IS INSTALLED

# --- Excel Utility: Write with Table Formatting (FINAL, CORRECTED TABLE OBJECT VERSION) ---
@st.cache_data
def convert_df_to_excel_formatted(df, sheet_name='SKU_Summary'):
    output = io.BytesIO()
    
    # Using 'xlsxwriter' engine
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            
            # 1. Write the entire DataFrame (Headers and Data)
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            
            # Get the xlsxwriter objects
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # Get the dimensions of the dataframe (max_row is data rows + 1 (header))
            (max_row, max_col) = df.shape 
            
            # 2. Add a Table Object for Borders/Shading/Filters
            worksheet.add_table(0, 0, max_row, max_col - 1, {
                'columns': [{'header': col} for col in df.columns],
                'style': 'Table Style Medium 9'
            })
            
            # 3. Add Freeze Panes
            worksheet.freeze_panes(1, 0)

            # 4. Apply column width and Percentage Format
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, 20)
                if col == 'Return % (Decimal)':
                    percent_format = workbook.add_format({'num_format': '0.00%'})
                    worksheet.set_column(i, i, 20, percent_format)

    except Exception as e:
        st.error(f"Excel formatting failed. Please ensure 'xlsxwriter' is installed.")
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name=sheet_name, engine='openpyxl')
        output.seek(0)
        return output.getvalue()
        
    processed_data = output.getvalue()
    return processed_data

# 1. Column name mapping
COLUMN_MAPPING = {
    'flipkart': {'sku_col': 'SKU', 'reason_col': 'Return Sub-reason', 'qty_col': 'Quantity'},
    'ajio': {'sku_col': 'SELLER SKU', 'reason_col': 'Cust Return Reason', 'qty_col': 'Return QTY'},
    'amazon': {'sku_col': 'sku', 'reason_col': 'reason', 'qty_col': 'quantity'},
    'meesho': {'sku_col': 'SKU', 'reason_col': 'Detailed Return Reason'},
    'firstcry': {'sku_col': 'VendorStyleCode', 'reason_col': 'Subreason', 'qty_col': 'Quantity'},
    'amazon_flex': {'sku_col': 'Item SkuCode', 'reason_col': 'Return Reason', 'qty_col': 'Total Received Items'}
}

DISPLAY_NAME_MAPPING = {
    'amazon': 'Amazon Warehouse', 'flipkart': 'Flipkart', 'ajio': 'Ajio',
    'meesho': 'Meesho', 'firstcry': 'Firstcry', 'amazon_flex': 'Amazon Flex'
}

# --- Helper Functions ---
def get_platform_from_name(filename_lower):
    if 'amazon_flex' in filename_lower or 'amazon flex' in filename_lower: return 'amazon_flex'
    elif 'amazon' in filename_lower: return 'amazon'
    elif 'flipkart' in filename_lower: return 'flipkart'
    elif 'meesho' in filename_lower: return 'meesho'
    elif 'ajio' in filename_lower: return 'ajio'
    elif 'firstcry' in filename_lower: return 'firstcry'
    return None

def extract_data(file_object, platform, filename_for_error_msg):
    df = None
    try:
        mapping = COLUMN_MAPPING[platform]
        if filename_for_error_msg.lower().endswith('.xlsx'):
            df = pd.read_excel(file_object, engine='openpyxl')
        else:
            try:
                df = pd.read_csv(file_object)
            except UnicodeDecodeError:
                file_object.seek(0)
                df = pd.read_csv(file_object, encoding='latin1')
        
        df.columns = [str(col).strip() for col in df.columns]
        qty_col_name = mapping.get('qty_col') 
        
        if qty_col_name:
            clean_mapping = {
                'sku_col': mapping['sku_col'].strip(),
                'reason_col': mapping['reason_col'].strip(),
                'qty_col': mapping['qty_col'].strip()
            }
            cols_to_use = [clean_mapping['sku_col'], clean_mapping['reason_col'], clean_mapping['qty_col']]
            temp_df = df[cols_to_use].copy()
            temp_df.rename(columns={
                clean_mapping['sku_col']: 'Final_SKU',
                clean_mapping['reason_col']: 'Final_Reason',
                clean_mapping['qty_col']: 'Final_Qty'
            }, inplace=True)
        else:
            clean_mapping = {
                'sku_col': mapping['sku_col'].strip(),
                'reason_col': mapping['reason_col'].strip()
            }
            cols_to_use = [clean_mapping['sku_col'], clean_mapping['reason_col']]
            temp_df = df[cols_to_use].copy()
            temp_df.rename(columns={
                clean_mapping['sku_col']: 'Final_SKU',
                clean_mapping['reason_col']: 'Final_Reason'
            }, inplace=True)
            temp_df['Final_Qty'] = 1 

        display_name = DISPLAY_NAME_MAPPING.get(platform, platform.capitalize())
        temp_df['Platform'] = display_name
        
        temp_df['Final_Qty'] = pd.to_numeric(temp_df['Final_Qty'], errors='coerce')
        temp_df.dropna(subset=['Final_SKU', 'Final_Reason', 'Final_Qty'], inplace=True)
        temp_df['Final_Qty'] = temp_df['Final_Qty'].astype(int)
        
        return temp_df
    except Exception as e:
        st.error(f"Error processing {filename_for_error_msg}: {e}")
        return None

def process_returns_files(uploaded_files):
    all_data_list = []
    for uploaded_file in uploaded_files:
        filename = ""
        try:
            filename = uploaded_file.name.lower()
        except Exception: continue
        
        if filename.endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zf:
                    for internal_filename in zf.namelist():
                        if internal_filename.startswith('__MACOSX') or not (internal_filename.lower().endswith('.csv') or internal_filename.lower().endswith('.xlsx')):
                            continue
                        platform = get_platform_from_name(internal_filename.lower())
                        if platform:
                            with zf.open(internal_filename) as f:
                                temp_df = extract_data(f, platform, internal_filename)
                                if temp_df is not None: all_data_list.append(temp_df)
            except Exception as e:
                st.error(f"Failed to process ZIP file {uploaded_file.name}: {e}")
        
        elif filename.endswith('.csv') or filename.endswith('.xlsx'):
            platform = get_platform_from_name(filename)
            if platform:
                temp_df = extract_data(uploaded_file, platform, filename)
                if temp_df is not None: all_data_list.append(temp_df)
                
    if not all_data_list:
        return pd.DataFrame(columns=['Final_SKU', 'Final_Reason', 'Platform', 'Final_Qty'])

    master_df = pd.concat(all_data_list, ignore_index=True)
    master_df = master_df[master_df['Final_Qty'] > 0]
    master_df['Final_SKU'] = master_df['Final_SKU'].astype(str)
    master_df['Final_Reason'] = master_df['Final_Reason'].astype(str)
    return master_df

def process_sales_data(sales_file):
    if not sales_file: return None
    try:
        filename = sales_file.name.lower()
        if filename.endswith('.xlsx'):
            sales_df = pd.read_excel(sales_file, engine='openpyxl')
        else:
            try:
                sales_df = pd.read_csv(sales_file)
            except UnicodeDecodeError:
                sales_file.seek(0)
                sales_df = pd.read_csv(sales_file, encoding='latin1')

        sales_df.columns = [str(col).strip() for col in sales_df.columns]
        required_cols = ['MSKU', 'Customer Shipments', 'Platform'] 
        if not all(col in sales_df.columns for col in required_cols):
            st.error("Sales file must contain 'MSKU', 'Customer Shipments', and 'Platform' columns.")
            return None

        sales_df['Platform'] = sales_df['Platform'].apply(lambda x: x.strip())
        total_orders_platform_df = sales_df.groupby(['MSKU', 'Platform'])['Customer Shipments'].sum().reset_index()
        total_orders_platform_df.columns = ['Final_SKU', 'Platform', 'Total_Orders']
        total_orders_platform_df['Final_SKU'] = total_orders_platform_df['Final_SKU'].astype(str)
        total_orders_platform_df['Total_Orders'] = pd.to_numeric(total_orders_platform_df['Total_Orders'], errors='coerce').fillna(0).astype(int)
        st.sidebar.success(f"Sales Data Processed. Total Orders: {total_orders_platform_df['Total_Orders'].sum()}")
        return total_orders_platform_df
    except Exception as e:
        st.sidebar.error(f"Error processing Sales Data: {e}")
        return None

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🛍️ Online Seller Return Analysis Dashboard")

# 3. File Uploaders in sidebar
st.sidebar.header("Step 1: Upload Returns Data")
uploaded_returns_files = st.sidebar.file_uploader(
    "Upload Returns files (.csv, .xlsx, or .zip)",
    accept_multiple_files=True, type=['xlsx', 'csv', 'zip'], key='returns_uploader'
)

st.sidebar.header("Step 2: Upload Sales/Order Data")
st.sidebar.caption("Must contain 'MSKU', 'Customer Shipments', and 'Platform' columns.")

# --- TEMPLATE DOWNLOAD BUTTON ADDED HERE ---
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
# --- END TEMPLATE DOWNLOAD ---

uploaded_sales_file = st.sidebar.file_uploader(
    "Upload Single Sales/Order File (for Return %)",
    type=['xlsx', 'csv'], key='sales_uploader'
)

if uploaded_returns_files:
    master_df = process_returns_files(uploaded_returns_files)
    total_orders_platform_df = process_sales_data(uploaded_sales_file)
    
    if not master_df.empty:
        st.success(f"Successfully processed {len(uploaded_returns_files)} returns files. Total items: {master_df['Final_Qty'].sum()}")
        filtered_df = master_df.copy()
        
        st.header("Overall Return Analysis")
        
        sku_data = filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        sku_data.columns = ['SKU', 'Total Quantity']
        sku_data['SKU_with_Count'] = sku_data['SKU'] + " (" + sku_data['Total Quantity'].astype(str) + ")"
        
        reason_data = filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        reason_data.columns = ['Reason', 'Total Quantity']
        reason_data['Reason_with_Count'] = reason_data['Reason'] + " (" + reason_data['Total Quantity'].astype(str) + ")"
        
        platform_data = filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        platform_data.columns = ['Platform', 'Total Quantity']
        platform_data['Platform_with_Count'] = platform_data['Platform'] + " (" + platform_data['Total Quantity'].astype(str) + ")"

        st.subheader("Cross-Slicers (Select Multiple Options)")
        col1, col2, col3 = st.columns(3)
        with col1:
            sku_search_list = st.multiselect("Filter by SKU:", options=list(sku_data['SKU_with_Count']), default=[], key="sku_search")
        with col2:
            reason_search_list = st.multiselect("Filter by Reason:", options=list(reason_data['Reason_with_Count']), default=[], key="reason_search")
        with col3:
            platform_search_list = st.multiselect("Filter by Platform:", options=list(platform_data['Platform_with_Count']), default=[], key="platform_search")

        final_filtered_df = filtered_df.copy()
        if sku_search_list:
            final_filtered_df = final_filtered_df[final_filtered_df['Final_SKU'].isin([s.split(' (')[0] for s in sku_search_list])]
        if reason_search_list:
            final_filtered_df = final_filtered_df[final_filtered_df['Final_Reason'].isin([r.split(' (')[0] for r in reason_search_list])]
        if platform_search_list:
            final_filtered_df = final_filtered_df[final_filtered_df['Platform'].isin([p.split(' (')[0] for p in platform_search_list])]
            
        st.divider()
        st.subheader(f"Filtered Summary Tables (Total Items: {final_filtered_df['Final_Qty'].sum()})")

        TOP_N_REASONS = 10 
        reason_agg = final_filtered_df.groupby(['Final_SKU', 'Final_Reason'])['Final_Qty'].sum().reset_index()
        reason_agg['Rank'] = reason_agg.groupby('Final_SKU')['Final_Qty'].rank(method='first', ascending=False)
        top_reasons = reason_agg[reason_agg['Rank'] <= TOP_N_REASONS].copy()
        top_reasons['New_Col_Name'] = 'Reason ' + top_reasons['Rank'].astype(int).astype(str)
        top_reasons['Reason_Count_Combined'] = top_reasons.apply(lambda row: f"{row['Final_Reason']} ({row['Final_Qty']})" if row['Final_Qty'] > 1 else f"{row['Final_Reason']}", axis=1)
        
        sku_reasons_pivot = top_reasons.pivot(index='Final_SKU', columns='New_Col_Name', values='Reason_Count_Combined').reset_index()
        sku_reasons_pivot.rename(columns={'Final_SKU': 'SKU'}, inplace=True)
        sku_reasons_pivot = sku_reasons_pivot.fillna('')
        
        reason_cols_order = [f'Reason {i}' for i in range(1, TOP_N_REASONS + 1)]
        for col in reason_cols_order:
            if col not in sku_reasons_pivot.columns: sku_reasons_pivot[col] = ''
        sku_reasons_pivot = sku_reasons_pivot[['SKU'] + reason_cols_order]

        res1, res2, res3 = st.columns(3)
        
        with res1:
            st.caption("Filter SKUs by Return % Range")
            col_min, col_max = st.columns(2)
            with col_min: min_pct = st.number_input("Min Return %", 0.0, 100.0, 0.0, 0.01, format="%.2f")
            with col_max: max_pct = st.number_input("Max Return %", 0.0, 100.0, 100.0, 0.01, format="%.2f")
            
            sku_display_data = final_filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            sku_display_data.columns = ['SKU', 'Return Qty'] 
            sku_final_export_data = sku_display_data.copy()
            
            if total_orders_platform_df is not None:
                orders_filtered = total_orders_platform_df.copy()
                if platform_search_list:
                    orders_filtered = orders_filtered[orders_filtered['Platform'].isin([p.split(' (')[0] for p in platform_search_list])]
                total_orders_merge = orders_filtered.groupby('Final_SKU')['Total_Orders'].sum().reset_index()
                total_orders_merge.columns = ['SKU', 'Total Orders']
                
                sku_final_export_data = pd.merge(sku_final_export_data, total_orders_merge, on='SKU', how='left')
                sku_final_export_data['Total Orders'] = sku_final_export_data['Total Orders'].fillna(0).astype(int)
                
                sku_final_export_data['Return_Pct_Raw'] = np.where(
                    sku_final_export_data['Total Orders'] > 0,
                    (sku_final_export_data['Return Qty'] / sku_final_export_data['Total Orders']), 0.0
                )
                
                sku_final_export_data = sku_final_export_data[
                    (sku_final_export_data['Return_Pct_Raw'] * 100 >= min_pct) & 
                    (sku_final_export_data['Return_Pct_Raw'] * 100 <= max_pct)
                ].copy()
                
                sku_final_export_data['Return %'] = sku_final_export_data['Return_Pct_Raw'].apply(lambda x: f"{x * 100:.2f}%")
                sku_final_export_data = pd.merge(sku_final_export_data, sku_reasons_pivot, on='SKU', how='left').fillna('')
                st.dataframe(sku_final_export_data[['SKU', 'Total Orders', 'Return Qty', 'Return %']], use_container_width=True, height=500)
            else:
                sku_final_export_data = pd.merge(sku_final_export_data.rename(columns={'Return Qty': 'Total Quantity'}), sku_reasons_pivot, on='SKU', how='left').fillna('')
                st.dataframe(sku_final_export_data, use_container_width=True, height=500)

        with res2:
            st.caption("Filtered Reasons")
            reason_display = final_filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            reason_display.columns = ['Reason', 'Total Quantity']
            st.dataframe(reason_display, use_container_width=True, height=500)
            
        with res3:
            st.caption("Filtered Platforms")
            platform_display = final_filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            platform_display.columns = ['Platform', 'Total Quantity']
            st.dataframe(platform_display, use_container_width=True, height=500)
            
        st.divider()
        st.subheader("Download Filtered Results")
        
        cols = sku_final_export_data.columns.tolist()
        reason_cols = [col for col in cols if col.startswith('Reason ')]
        
        if 'Total Orders' in sku_final_export_data.columns:
            sku_final_export_csv = sku_final_export_data.drop(columns=['Return_Pct_Raw'], errors='ignore')
            sku_final_export_excel = sku_final_export_data.drop(columns=['Return %'], errors='ignore')
            sku_final_export_excel.rename(columns={'Return_Pct_Raw': 'Return % (Decimal)'}, inplace=True)
            
            order_csv = ['SKU', 'Total Orders', 'Return Qty', 'Return %'] + reason_cols
            order_excel = ['SKU', 'Total Orders', 'Return Qty', 'Return % (Decimal)'] + reason_cols
            
            final_csv_df = sku_final_export_csv[order_csv]
            final_excel_df = sku_final_export_excel[order_excel]
        else:
            order_cols = ['SKU', 'Total Quantity'] + reason_cols
            final_csv_df = sku_final_export_data[order_cols]
            final_excel_df = sku_final_export_data[order_cols]

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.download_button("Download Filtered SKUs (CSV) ⬇️", final_csv_df.to_csv(index=False).encode('utf-8'), 'sku_summary.csv', 'text/csv')
        with col_d2:
            st.download_button("Download Filtered SKUs (Excel) ⬇️", convert_df_to_excel_formatted(final_excel_df), 'sku_summary.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with col_d3:
            st.download_button("Download Reasons (CSV) ⬇️", reason_display.to_csv(index=False).encode('utf-8'), 'reason_summary.csv', 'text/csv')

    else:
        st.warning("No data found after processing.")
else:
    st.info("Please upload your **Returns Data** and **Sales Data** (Optional) from the sidebar.")
