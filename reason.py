import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import io

# 1. Column name mapping provided by you (Returns Data)
COLUMN_MAPPING = {
    'flipkart': {
        'sku_col': 'SKU',
        'reason_col': 'Return Sub-reason',
        'qty_col': 'Quantity'
    },
    'ajio': {
        'sku_col': 'SELLER SKU',
        'reason_col': 'Cust Return Reason',
        'qty_col': 'Return QTY'
    },
    'amazon': {
        'sku_col': 'sku',
        'reason_col': 'reason',
        'qty_col': 'quantity'
    },
    'meesho': {
        'sku_col': 'SKU',
        'reason_col': 'Detailed Return Reason'
    },
    'firstcry': {
        'sku_col': 'VendorStyleCode',
        'reason_col': 'Subreason',
        'qty_col': 'Quantity'
    },
    'amazon_flex': {
        'sku_col': 'Item SkuCode',
        'reason_col': 'Return Reason',
        'qty_col': 'Total Received Items'
    }
}

# Mapping for display names
DISPLAY_NAME_MAPPING = {
    'amazon': 'Amazon Warehouse',
    'flipkart': 'Flipkart',
    'ajio': 'Ajio',
    'meesho': 'Meesho',
    'firstcry': 'Firstcry',
    'amazon_flex': 'Amazon Flex'
}

# --- Helper Function: Get platform from filename ---
def get_platform_from_name(filename_lower):
    if 'amazon_flex' in filename_lower or 'amazon flex' in filename_lower:
        return 'amazon_flex'
    elif 'amazon' in filename_lower:
        return 'amazon'
    elif 'flipkart' in filename_lower:
        return 'flipkart'
    elif 'meesho' in filename_lower:
        return 'meesho'
    elif 'ajio' in filename_lower:
        return 'ajio'
    elif 'firstcry' in filename_lower:
        return 'firstcry'
    return None

# --- Helper Function: Extract data from a file object (Returns Data) ---
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

    except KeyError as e:
        st.error(f"Error processing {filename_for_error_msg}: Column '{e}' not found.")
        if df is not None:
            st.error(f"Columns found in file: {list(df.columns)}")
        st.warning("Please check 'COLUMN_MAPPING' in the code. Note: Column names are case-sensitive and space-sensitive.")
        return None
    except Exception as e:
        st.error(f"General error processing {filename_for_error_msg}: {e}.")
        return None

# 2. Main File processing function (Handles ZIP files for Returns Data)
def process_returns_files(uploaded_files):
    all_data_list = []
    
    for uploaded_file in uploaded_files:
        filename = ""
        try:
            filename = uploaded_file.name.lower()
        except Exception:
            continue
        
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
                                if temp_df is not None:
                                    all_data_list.append(temp_df)
            except Exception as e:
                st.error(f"Failed to process ZIP file {uploaded_file.name}: {e}")
        
        elif filename.endswith('.csv') or filename.endswith('.xlsx'):
            platform = get_platform_from_name(filename)
            if platform:
                temp_df = extract_data(uploaded_file, platform, filename)
                if temp_df is not None:
                    all_data_list.append(temp_df)
            else:
                st.warning(f"Skipping file (platform not recognized): {filename}")
                
    if not all_data_list:
        return pd.DataFrame(columns=['Final_SKU', 'Final_Reason', 'Platform', 'Final_Qty'])

    master_df = pd.concat(all_data_list, ignore_index=True)
    master_df = master_df[master_df['Final_Qty'] > 0]
    master_df['Final_SKU'] = master_df['Final_SKU'].astype(str)
    master_df['Final_Reason'] = master_df['Final_Reason'].astype(str)
    
    return master_df

# --- NEW: Function to process Sales/Order Data (Grouped by SKU AND Platform) ---
def process_sales_data(sales_file):
    if not sales_file:
        return None
    
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
        
        # We need MSKU, Customer Shipments, and Platform from the Sales File
        required_cols = ['MSKU', 'Customer Shipments', 'Platform'] 
        if not all(col in sales_df.columns for col in required_cols):
            st.error("Sales file must contain 'MSKU', 'Customer Shipments', and 'Platform' columns.")
            return None

        sales_df['Platform'] = sales_df['Platform'].apply(lambda x: x.strip())
        
        # Group by SKU AND Platform
        total_orders_platform_df = sales_df.groupby(['MSKU', 'Platform'])['Customer Shipments'].sum().reset_index()
        total_orders_platform_df.columns = ['Final_SKU', 'Platform', 'Total_Orders']
        
        total_orders_platform_df['Final_SKU'] = total_orders_platform_df['Final_SKU'].astype(str)
        total_orders_platform_df['Total_Orders'] = pd.to_numeric(total_orders_platform_df['Total_Orders'], errors='coerce').fillna(0).astype(int)
        
        total_orders_sum = total_orders_platform_df['Total_Orders'].sum()
        st.sidebar.success(f"Sales Data Processed. Total Orders counted: {total_orders_sum}")
        
        return total_orders_platform_df

    except Exception as e:
        st.sidebar.error(f"Error processing Sales Data: {e}")
        return None
# --- END NEW FUNCTION ---

# --- Helper function to convert DataFrame to CSV for download ---
@st.cache_data
def convert_df_to_csv(df):
    # index=False ensures the index column (A column) is not written to the CSV file
    return df.to_csv(index=False).encode('utf-8')

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🛍️ Online Seller Return Analysis Dashboard")

# 3. File Uploaders in sidebar
st.sidebar.header("Step 1: Upload Returns Data")
uploaded_returns_files = st.sidebar.file_uploader(
    "Upload Returns files (.csv, .xlsx, or .zip)",
    accept_multiple_files=True,
    type=['xlsx', 'csv', 'zip'],
    key='returns_uploader'
)

st.sidebar.header("Step 2: Upload Sales/Order Data")
st.sidebar.caption("Must contain 'MSKU', 'Customer Shipments', and 'Platform' columns.")
uploaded_sales_file = st.sidebar.file_uploader(
    "Upload Single Sales/Order File (for Return %)",
    type=['xlsx', 'csv'],
    key='sales_uploader'
)
# --- End Uploaders ---

if uploaded_returns_files:
    master_df = process_returns_files(uploaded_returns_files)
    total_orders_platform_df = process_sales_data(uploaded_sales_file) # Process Sales data grouped by SKU & Platform
    
    if not master_df.empty:
        st.success(f"Successfully processed {len(uploaded_returns_files)} returns files/archives. Total returned items: {master_df['Final_Qty'].sum()}")
        
        filtered_df = master_df.copy()
        
        st.header("Overall Return Analysis")
        
        # --- Cross-Filtering Logic (Multiselect Slicers) ---
        
        # 1. Pehle teeno filters ke liye data banao
        sku_data = filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        sku_data.columns = ['SKU', 'Total Quantity']
        sku_data['SKU_with_Count'] = sku_data['SKU'] + " (" + sku_data['Total Quantity'].astype(str) + ")"
        
        reason_data = filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        reason_data.columns = ['Reason', 'Total Quantity']
        reason_data['Reason_with_Count'] = reason_data['Reason'] + " (" + reason_data['Total Quantity'].astype(str) + ")"
        
        platform_data = filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
        platform_data.columns = ['Platform', 'Total Quantity']
        platform_data['Platform_with_Count'] = platform_data['Platform'] + " (" + platform_data['Total Quantity'].astype(str) + ")"

        # 2. Multiselect lists banao 
        sku_list_for_multiselect = list(sku_data['SKU_with_Count'])
        reason_list_for_multiselect = list(reason_data['Reason_with_Count'])
        platform_list_multiselect = list(platform_data['Platform_with_Count'])
        
        # 3. Ab teeno filters ko TOP par dikhao (USING st.multiselect)
        st.subheader("Cross-Slicers (Select Multiple Options)")
        col1, col2, col3 = st.columns(3)
        with col1:
            sku_search_list = st.multiselect(
                "Filter by SKU:", 
                options=sku_list_for_multiselect, 
                default=[],
                key="sku_search"
            )
        with col2:
            reason_search_list = st.multiselect(
                "Filter by Reason:", 
                options=reason_list_for_multiselect,
                default=[], 
                key="reason_search"
            )
        with col3:
            platform_search_list = st.multiselect(
                "Filter by Platform:", 
                options=platform_list_multiselect,
                default=[], 
                key="platform_search"
            )

        # 4. Ab ek FINAL filtered DataFrame banao
        final_filtered_df = filtered_df.copy()

        if sku_search_list:
            selected_sku_names = [s.split(' (')[0] for s in sku_search_list]
            final_filtered_df = final_filtered_df[final_filtered_df['Final_SKU'].isin(selected_sku_names)]

        if reason_search_list:
            selected_reason_names = [r.split(' (')[0] for r in reason_search_list]
            final_filtered_df = final_filtered_df[final_filtered_df['Final_Reason'].isin(selected_reason_names)]
            
        if platform_search_list:
            selected_platform_names = [p.split(' (')[0] for p in platform_search_list]
            final_filtered_df = final_filtered_df[final_filtered_df['Platform'].isin(selected_platform_names)]
            
        st.divider()
        st.subheader(f"Filtered Summary Tables (Total Items: {final_filtered_df['Final_Qty'].sum()})")

        # --- REASON PIVOTING LOGIC ---
        TOP_N_REASONS = 5 
        
        # 1. Group by SKU and Reason, summing the quantities
        reason_agg = final_filtered_df.groupby(['Final_SKU', 'Final_Reason'])['Final_Qty'].sum().reset_index()
        
        # 2. Rank reasons within each SKU based on quantity
        reason_agg['Rank'] = reason_agg.groupby('Final_SKU')['Final_Qty'].rank(method='first', ascending=False)
        
        # Filter for top N reasons (Top 5)
        top_reasons = reason_agg[reason_agg['Rank'] <= TOP_N_REASONS].copy()
        
        # Create column names: 'Reason 1 (Qty)', 'Reason 2 (Qty)', etc.
        top_reasons['New_Col_Name'] = 'Reason ' + top_reasons['Rank'].astype(int).astype(str) + ' (Qty)'
        
        # Create a combined string for Reason and Quantity: "Reason Name (Qty)"
        top_reasons['Reason_Qty_Combined'] = top_reasons['Final_Reason'] + ' (' + top_reasons['Final_Qty'].astype(str) + ')'
        
        # Pivot the data to get reasons in separate columns
        sku_reasons_pivot = top_reasons.pivot(
            index='Final_SKU', 
            columns='New_Col_Name', 
            values='Reason_Qty_Combined'
        ).reset_index()
        sku_reasons_pivot.rename(columns={'Final_SKU': 'SKU'}, inplace=True)
        
        sku_reasons_pivot = sku_reasons_pivot.fillna('')
        
        # Ensure all Top N columns exist, even if empty for some SKUs, and define the order
        reason_cols_order = [f'Reason {i} (Qty)' for i in range(1, TOP_N_REASONS + 1)]
        for col in reason_cols_order:
            if col not in sku_reasons_pivot.columns:
                sku_reasons_pivot[col] = ''
                
        sku_reasons_pivot = sku_reasons_pivot[['SKU'] + reason_cols_order]
        # --- END REASON PIVOTING LOGIC ---


        # 5. Ab neeche teeno tables dikhao
        res1, res2, res3 = st.columns(3)
        
        with res1:
            # --- MANUAL INPUTS FOR RETURN PERCENTAGE RANGE ---
            st.caption("Filter SKUs by Return % Range (0.00% to 100.00%)")
            col_min, col_max = st.columns(2)
            
            with col_min:
                min_pct = st.number_input(
                    "Minimum Return %",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="min_pct_input"
                )
            with col_max:
                max_pct = st.number_input(
                    "Maximum Return %",
                    min_value=0.0,
                    max_value=100.0,
                    value=100.0,
                    step=0.01,
                    format="%.2f",
                    key="max_pct_input"
                )
            
            # Error handling for input
            if min_pct > max_pct:
                st.error("Minimum % value cannot be greater than Maximum % value.")
                min_pct, max_pct = 0.0, 100.0 
                
            st.caption("Filtered SKUs (Return vs. Orders)")
            
            sku_display_data = final_filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            sku_display_data.columns = ['SKU', 'Return Qty'] 
            
            # --- Return Percentage Calculation (Platform Filtered) ---
            if total_orders_platform_df is not None:
                
                # Filter Order Data by selected platforms
                orders_filtered_by_platform = total_orders_platform_df.copy()
                if platform_search_list:
                    selected_platform_names = [p.split(' (')[0] for p in platform_search_list]
                    orders_filtered_by_platform = orders_filtered_by_platform[
                        orders_filtered_by_platform['Platform'].isin(selected_platform_names)
                    ]
                
                # Aggregate filtered orders by SKU for the merge
                total_orders_for_merge = orders_filtered_by_platform.groupby('Final_SKU')['Total_Orders'].sum().reset_index()
                total_orders_for_merge.columns = ['SKU', 'Total Orders'] 
                
                # Merge with SKU returns data
                sku_display_data = pd.merge(
                    sku_display_data, 
                    total_orders_for_merge, 
                    on='SKU', 
                    how='left'
                )
                
                sku_display_data['Total Orders'] = sku_display_data['Total Orders'].fillna(0).astype(int)
                
                # Calculate return percentage as a raw float for filtering
                sku_display_data['Return_Pct_Raw'] = np.where(
                    sku_display_data['Total Orders'] > 0,
                    (sku_display_data['Return Qty'] / sku_display_data['Total Orders']) * 100,
                    0.0
                )
                
                # --- APPLYING THE MANUAL RETURN PERCENTAGE FILTER ---
                sku_display_data = sku_display_data[
                    (sku_display_data['Return_Pct_Raw'] >= min_pct) & 
                    (sku_display_data['Return_Pct_Raw'] <= max_pct)
                ]
                # --- END APPLYING FILTER ---
                
                # Format the percentage column for display (00.00%)
                sku_display_data['Return %'] = sku_display_data['Return_Pct_Raw'].apply(lambda x: f"{x:.2f}%")
                
                # --- MERGE PIVOTED REASONS DATA HERE (FOR EXPORT) ---
                sku_display_data = pd.merge(
                    sku_display_data,
                    sku_reasons_pivot,
                    on='SKU',
                    how='left'
                ).fillna('') # Fill NaN (where no reason data) with empty strings
                
                # --- FINAL DISPLAY DATA (ONLY CORE COLUMNS) ---
                display_cols = ['SKU', 'Total Orders', 'Return Qty', 'Return %']
                
                # Display the data
                st.dataframe(
                    sku_display_data[display_cols], 
                    use_container_width=True, 
                    height=500
                )
                st.caption(f"Note: Top {TOP_N_REASONS} Reasons are included in **separate columns** in the **CSV download** only.")
                
            else:
                # Agar Sales file upload nahi hui, toh sirf returns data dikhao
                # Merge Reasons data for export if sales data is missing
                sku_display_data = pd.merge(
                    sku_display_data.rename(columns={'Return Qty': 'Total Quantity'}),
                    sku_reasons_pivot,
                    on='SKU',
                    how='left'
                ).fillna('')
                
                display_cols = ['SKU', 'Total Quantity']
                st.dataframe(
                    sku_display_data[display_cols], 
                    use_container_width=True, 
                    height=500
                )
                st.caption(f"Note: Top {TOP_N_REASONS} Reasons are included in **separate columns** in the **CSV download** only.")
            
        with res2:
            st.caption("Filtered Reasons")
            reason_display_data = final_filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            reason_display_data.columns = ['Reason', 'Total Quantity']
            st.dataframe(reason_display_data, use_container_width=True, height=500)
            
        with res3:
            st.caption("Filtered Platforms")
            platform_display_data = final_filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            platform_display_data.columns = ['Platform', 'Total Quantity']
            st.dataframe(platform_display_data, use_container_width=True, height=500)
            
        # --- Download Filtered Aggregated Results ---
        st.divider()
        st.subheader("Download Filtered Aggregated Results")
        st.caption("The downloaded SKUs CSV will include the hidden reason columns.")
        
        filter_down_col1, filter_down_col2, filter_down_col3, filter_down_col4 = st.columns(4)
        
        with filter_down_col1:
            # We convert the final displayed SKU data (which includes all pivoted reason columns)
            csv_data_sku = convert_df_to_csv(sku_display_data)
            st.download_button(
                label="Download Filtered SKUs (CSV) ⬇️",
                data=csv_data_sku,
                file_name='filtered_sku_summary_with_separate_reasons.csv',
                mime='text/csv',
                help=f"Downloads the SKUs summary, including separate columns for Top {TOP_N_REASONS} Reasons (Qty)."
            )
            
        with filter_down_col2:
            csv_data_reason = convert_df_to_csv(reason_display_data)
            st.download_button(
                label="Download Filtered Reasons (CSV) ⬇️",
                data=csv_data_reason,
                file_name='filtered_reason_summary.csv',
                mime='text/csv',
                help="Downloads the visible Filtered Reasons table."
            )
            
        with filter_down_col3:
            csv_data_platform = convert_df_to_csv(platform_display_data)
            st.download_button(
                label="Download Filtered Platforms (CSV) ⬇️",
                data=csv_data_platform,
                file_name='filtered_platform_summary.csv',
                mime='text/csv',
                help="Downloads the visible Filtered Platforms table."
            )
        # --- END Download Filtered Aggregated Results ---

    else:
        st.warning("No data found after processing. Please check your files or column names.")
else:
    st.info("Please upload your **Returns Data** and **Sales Data** from the sidebar to start the analysis.")
