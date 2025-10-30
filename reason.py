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
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("All Returned SKUs (by total quantity)")
                all_skus_count = filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
                all_skus_count.columns = ['SKU', 'Total Quantity']
                
                sku_search = st.text_input("Search SKU:", key="sku_search")
                
                # --- THIS IS THE FIX ---
                if sku_search:
                    # Use .apply() for a more robust search
                    search_term_lower = sku_search.lower()
                    filtered_sku_df = all_skus_count[all_skus_count['SKU'].apply(lambda x: search_term_lower in str(x).lower())]
                    st.dataframe(filtered_sku_df, use_container_width=True, height=500)
                else:
                    st.dataframe(all_skus_count, use_container_width=True, height=500)
                # --- END OF FIX ---

            with col2:
                st.subheader("All Return Reasons (by total quantity)")
                all_reasons_count = filtered_df.groupby('Final_Reason')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
                all_reasons_count.columns = ['Reason', 'Total Quantity']
                
                reason_search = st.text_input("Search Reason:", key="reason_search")
                
                # --- THIS IS THE FIX ---
                if reason_search:
                    # Use .apply() for a more robust search
                    search_term_lower = reason_search.lower()
                    filtered_reason_df = all_reasons_count[all_reasons_count['Reason'].apply(lambda x: search_term_lower in str(x).lower())]
                    st.dataframe(filtered_reason_df, use_container_width=True, height=500)
                else:
                    st.dataframe(all_reasons_count, use_container_width=True, height=500)
                # --- END OF FIX ---
            
            st.subheader("Returns by Platform (by total quantity)")
            platform_counts = filtered_df.groupby('Platform')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            platform_counts.columns = ['Platform', 'Total Quantity']
            st.dataframe(platform_counts, use_container_width=True)
        
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
