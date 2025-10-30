import streamlit as st
import pandas as pd
import numpy as np # We need numpy for data handling

# 1. Column name mapping provided by you
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
    }
}

# Mapping for display names
DISPLAY_NAME_MAPPING = {
    'amazon': 'Amazon Warehouse',
    'flipkart': 'Flipkart',
    'ajio': 'Ajio',
    'meesho': 'Meesho',
    'firstcry': 'Firstcry'
}

# 2. File processing function
def process_files(uploaded_files):
    all_data_list = []
    
    for uploaded_file in uploaded_files:
        filename = "" # Initialize empty filename
        
        # --- ERROR FIX ---
        try:
            file_name_attr = uploaded_file.name
            if isinstance(file_name_attr, list):
                filename = file_name_attr[0].lower()
            else:
                filename = file_name_attr.lower()
        except Exception as e:
            st.error(f"Error getting file name: {e}")
            continue 
        # --- END FIX ---
            
        platform = None
        
        # Identify platform from filename
        if 'amazon' in filename:
            platform = 'amazon'
        elif 'flipkart' in filename:
            platform = 'flipkart'
        elif 'meesho' in filename:
            platform = 'meesho'
        elif 'ajio' in filename:
            platform = 'ajio'
        elif 'firstcry' in filename:
            platform = 'firstcry'
        
        if platform:
            df = None
            try:
                mapping = COLUMN_MAPPING[platform]
                
                if filename.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                else:
                    df = pd.read_csv(uploaded_file)
                
                df.columns = df.columns.str.strip()
                
                qty_col_name = mapping.get('qty_col') 
                
                if qty_col_name:
                    cols_to_use = [mapping['sku_col'], mapping['reason_col'], qty_col_name]
                    temp_df = df[cols_to_use].copy()
                    temp_df.rename(columns={
                        mapping['sku_col']: 'Final_SKU',
                        mapping['reason_col']: 'Final_Reason',
                        qty_col_name: 'Final_Qty'
                    }, inplace=True)
                else:
                    cols_to_use = [mapping['sku_col'], mapping['reason_col']]
                    temp_df = df[cols_to_use].copy()
                    temp_df.rename(columns={
                        mapping['sku_col']: 'Final_SKU',
                        mapping['reason_col']: 'Final_Reason'
                    }, inplace=True)
                    temp_df['Final_Qty'] = 1 

                display_name = DISPLAY_NAME_MAPPING.get(platform, platform.capitalize())
                temp_df['Platform'] = display_name
                
                temp_df['Final_Qty'] = pd.to_numeric(temp_df['Final_Qty'], errors='coerce')
                temp_df.dropna(subset=['Final_SKU', 'Final_Reason', 'Final_Qty'], inplace=True)
                temp_df['Final_Qty'] = temp_df['Final_Qty'].astype(int)
                
                all_data_list.append(temp_df)

            except KeyError as e:
                st.error(f"Error processing {filename}: Column {e} not found.")
                if df is not None:
                    st.error(f"Columns found in the file: {list(df.columns)}")
                st.warning("Please correct the 'COLUMN_MAPPING' in the code.")
            except Exception as e:
                st.error(f"Error processing {filename}: {e}.")
                
    if not all_data_list:
        return pd.DataFrame(columns=['Final_SKU', 'Final_Reason', 'Platform', 'Final_Qty'])

    master_df = pd.concat(all_data_list, ignore_index=True)
    master_df = master_df[master_df['Final_Qty'] > 0]
    master_df['Final_SKU'] = master_df['Final_SKU'].astype(str)
    master_df['Final_Reason'] = master_df['Final_Reason'].astype(str)
    
    return master_df

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🛍️ Online Seller Return Analysis Dashboard")

# 3. File Uploader
st.header("Step 1: Upload Files")
uploaded_files = st.file_uploader(
    "Upload all your return reports (Amazon Warehouse, Flipkart, Ajio, Meesho, Firstcry)",
    accept_multiple_files=True,
    type=['xlsx', 'csv']
)

# 4. When files are uploaded, show the dashboard
if uploaded_files:
    master_df = process_files(uploaded_files)
    
    if not master_df.empty:
        st.success(f"Successfully processed {len(uploaded_files)} files. Total returned items: {master_df['Final_Qty'].sum()}")
        st.divider()

        # --- Sidebar Filters ---
        st.sidebar.header("Filters")
        
        all_platforms = master_df['Platform'].unique()
        selected_platforms = st.sidebar.multiselect(
            "Select Platform(s)",
            options=all_platforms,
            default=all_platforms
        )
        
        all_skus = sorted(master_df['Final_SKU'].unique())
        selected_sku = st.sidebar.selectbox(
            "Select SKU for Deep-Dive",
            options=all_skus,
            index=None,
            placeholder="Type or select an SKU..."
        )

        filtered_df = master_df[
            (master_df['Platform'].isin(selected_platforms))
        ]
        
        # --- Dashboard UI (Using Qty Sums) ---
        
        if not selected_sku:
            st.header("Overall Return Analysis")
            st.info("Select an SKU from the sidebar to see a detailed breakdown.")
            
            # --- UPDATE: Changed to 3 columns ---
            col1, col2, col3 = st.columns(3)
            # -----------------------------------
            
            with col1:
                st.subheader("All Returned SKUs (by total quantity)")
                all_skus_count = filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
                all_skus_count.columns = ['SKU', 'Total Quantity']
                
                all_skus_count['SKU_with_Count'] = all_skus_count['SKU'] + " (" + all_skus_count['Total Quantity'].astype(str) + ")"
                
                sku_list_for_dropdown = ["Select an SKU to filter..."] + list(all_skus_count['SKU_with_Count'])
                sku_search = st.selectbox("Search/Select SKU:", options=sku_list_for_dropdown, key="sku_search")
                
                df_to_display_sku = all_skus_count[['SKU', 'Total Quantity']] 

                if sku_search != "Select an SKU to filter...":
                    selected_sku_name = all_skus_count[all_skus_count['SKU_with_Count'] == sku_search]['SKU'].values[0]
                    filtered_sku_df = df_to_display_sku[df_to_display_sku['SKU'] == selected_sku_name]
                    st.dataframe(filtered_sku_df, use_container_width=True, height=500)
                else:
                    st.dataframe(df_to_display_sku, use_container_width=True, height=500)

            with col2:
                st.subheader("All Return Reasons (by total quantity)")
                all_reasons_count = filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
                all_reasons_count.columns = ['Reason', 'Total Quantity']
                
                all_reasons_count['Reason_with_Count'] = all_reasons_count['Reason'] + " (" + all_reasons_count['Total Quantity'].astype(str) + ")"
                
                reason_list_for_dropdown = ["Select a Reason to filter..."] + list(all_reasons_count['Reason_with_Count'])
                reason_search = st.selectbox("Search/Select Reason:", options=reason_list_for_dropdown, key="reason_search")
                
                df_to_display_reason = all_reasons_count[['Reason', 'Total Quantity']]
                
                if reason_search != "Select a Reason to filter...":
                    selected_reason_name = all_reasons_count[all_reasons_count['Reason_with_Count'] == reason_search]['Reason'].values[0]
                    filtered_reason_df = df_to_display_reason[df_to_display_reason['Reason'] == selected_reason_name]
                    st.dataframe(filtered_reason_df, use_container_width=True, height=500)
                else:
                    st.dataframe(df_to_display_reason, use_container_width=True, height=500)

            # --- NEW: Platform column added ---
            with col3:
                st.subheader("Returns by Platform (by total quantity)")
                platform_counts = filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
                platform_counts.columns = ['Platform', 'Total Quantity']
                
                platform_counts['Platform_with_Count'] = platform_counts['Platform'] + " (" + platform_counts['Total Quantity'].astype(str) + ")"
                
                platform_list_dropdown = ["Select a Platform to filter..."] + list(platform_counts['Platform_with_Count'])
                platform_search = st.selectbox("Search/Select Platform:", options=platform_list_dropdown, key="platform_search")
                
                df_to_display_platform = platform_counts[['Platform', 'Total Quantity']]
                
                if platform_search != "Select a Platform to filter...":
                    selected_platform_name = platform_counts[platform_counts['Platform_with_Count'] == platform_search]['Platform'].values[0]
                    filtered_platform_df = df_to_display_platform[df_to_display_platform['Platform'] == selected_platform_name]
                    st.dataframe(filtered_platform_df, use_container_width=True, height=500)
                else:
                    st.dataframe(df_to_display_platform, use_container_width=True, height=500)
            # --- END OF NEW COLUMN ---
        
        else:
            st.header(f"Deep-Dive for SKU: {selected_sku}")
            
            sku_specific_df = filtered_df[filtered_df['Final_SKU'] == selected_sku]
            
            total_returns = sku_specific_df['Final_Qty'].sum()
            st.metric("Total Returned Qty for this SKU", total_returns)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Return Reasons")
                reason_counts = sku_specific_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False)
                st.bar_chart(reason_counts) 
            
            with col2:
                st.subheader("Returns by Platform")
                platform_counts = sku_specific_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False)
                st.bar_chart(platform_counts)
                
            st.subheader("Raw Return Data for this SKU")
            st.dataframe(sku_specific_df[['Final_SKU', 'Final_Reason', 'Platform', 'Final_Qty']])

    else:
        st.warning("No data found after processing. Please check your files.")
else:
    st.info("Please upload your return files to start the analysis.")
