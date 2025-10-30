
import streamlit as st
import pandas as pd
import numpy as np
import zipfile  # ZIP file processing
import io         # Memory I/O

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
    },
    # --- NAYA PORTAL ADD KIYA HAI ---
    'amazon_flex': {
        'sku_col': 'Item SkuCode',
        'reason_col': 'Return Reason',
        'qty_col': 'Total Received Items'
    }
    # ---------------------------------
}

# Mapping for display names
DISPLAY_NAME_MAPPING = {
    'amazon': 'Amazon Warehouse',
    'flipkart': 'Flipkart',
    'ajio': 'Ajio',
    'meesho': 'Meesho',
    'firstcry': 'Firstcry',
    'amazon_flex': 'Amazon Flex' # <-- Display naam add kiya
}

# --- Helper Function: Get platform from filename (UPDATED) ---
def get_platform_from_name(filename_lower):
    # 'amazon_flex' ko pehle check karna zaroori hai
    if 'amazon_flex' in filename_lower:
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
# --- END OF UPDATE ---

# --- Helper Function: Extract data from a file object (FIXED) ---
def extract_data(file_object, platform, filename_for_error_msg):
    df = None
    try:
        mapping = COLUMN_MAPPING[platform]
        
        # Read the file (Excel or CSV)
        if filename_for_error_msg.lower().endswith('.xlsx'):
            df = pd.read_excel(file_object, engine='openpyxl')
        else:
            df = pd.read_csv(file_object)
        
        # --- YEH HAI FIX (Extra space ke liye) ---
        # Column names ko force karke clean karo
        df.columns = [str(col).strip() for col in df.columns]
        # --- END OF FIX ---
        
        qty_col_name = mapping.get('qty_col') 
        
        if qty_col_name:
            # Clean SKU/Reason column names ko mapping se check karo
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
            # Clean SKU/Reason column names ko mapping se check karo
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

# 2. Main File processing function (Handles ZIP files)
def process_files(uploaded_files):
    all_data_list = []
    
    for uploaded_file in uploaded_files:
        filename = ""
        try:
            file_name_attr = uploaded_file.name
            if isinstance(file_name_attr, list):
                filename = file_name_attr[0].lower()
            else:
                filename = file_name_attr.lower()
        except Exception as e:
            st.error(f"Error getting file name: {e}")
            continue 
        
        # --- Check for ZIP file ---
        if filename.endswith('.zip'):
            st.info(f"Processing ZIP file: {uploaded_file.name}")
            try:
                # Read zip file in memory
                with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue()), 'r') as zf:
                    # Loop over all files inside the zip
                    for internal_filename in zf.namelist():
                        # Ignore Mac system files
                        if internal_filename.startswith('__MACOSX') or not (internal_filename.lower().endswith('.csv') or internal_filename.lower().endswith('.xlsx')):
                            continue
                        
                        platform = get_platform_from_name(internal_filename.lower())
                        
                        if platform:
                            # Process the file from inside the zip
                            with zf.open(internal_filename) as f:
                                temp_df = extract_data(f, platform, internal_filename)
                                if temp_df is not None:
                                    all_data_list.append(temp_df)
                        else:
                            st.warning(f"Skipping file in ZIP (platform not recognized): {internal_filename}")
            except Exception as e:
                st.error(f"Failed to process ZIP file {uploaded_file.name}: {e}")
        
        # --- Logic for Single files ---
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

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("🛍️ Online Seller Return Analysis Dashboard")

# 3. File Uploader (Only item in sidebar)
st.sidebar.header("Step 1: Upload Files")
uploaded_files = st.sidebar.file_uploader(
    "Upload .csv, .xlsx, or a single .zip file",
    accept_multiple_files=True,
    type=['xlsx', 'csv', 'zip']
)

# 4. When files are uploaded, show the dashboard
if uploaded_files:
    master_df = process_files(uploaded_files)
    
    if not master_df.empty:
        st.success(f"Successfully processed {len(uploaded_files)} files/archives. Total returned items: {master_df['Final_Qty'].sum()}")
        st.divider()

        # Sidebar filters hata diye gaye hain
        filtered_df = master_df.copy()
        
        st.header("Overall Return Analysis")
        
        # --- Cross-Filtering Logic ---
        
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

        # 2. Dropdown lists banao
        sku_list_for_dropdown = ["Select an SKU..."] + list(sku_data['SKU_with_Count'])
        reason_list_for_dropdown = ["Select a Reason..."] + list(reason_data['Reason_with_Count'])
        platform_list_dropdown = ["Select a Platform..."] + list(platform_data['Platform_with_Count'])
        
        # Session state ko check karo (Error fix)
        if 'sku_search' not in st.session_state or st.session_state.sku_search not in sku_list_for_dropdown:
            st.session_state.sku_search = "Select an SKU..."
        if 'reason_search' not in st.session_state or st.session_state.reason_search not in reason_list_for_dropdown:
            st.session_state.reason_search = "Select a Reason..."
        if 'platform_search' not in st.session_state or st.session_state.platform_search not in platform_list_dropdown:
            st.session_state.platform_search = "Select a Platform..."

        # 3. Ab teeno filters ko TOP par dikhao
        st.subheader("Cross-Filters")
        col1, col2, col3 = st.columns(3)
        with col1:
            sku_search = st.selectbox("Search/Select SKU:", options=sku_list_for_dropdown, key="sku_search")
        with col2:
            reason_search = st.selectbox("Search/Select Reason:", options=reason_list_for_dropdown, key="reason_search")
        with col3:
            platform_search = st.selectbox("Search/Select Platform:", options=platform_list_dropdown, key="platform_search")

        # 4. Ab ek FINAL filtered DataFrame banao
        final_filtered_df = filtered_df.copy()
        
        if sku_search != "Select an SKU...":
            selected_sku_name = sku_data[sku_data['SKU_with_Count'] == sku_search]['SKU'].values[0]
            final_filtered_df = final_filtered_df[final_filtered_df['Final_SKU'] == selected_sku_name]
        
        if reason_search != "Select a Reason...":
            selected_reason_name = reason_data[reason_data['Reason_with_Count'] == reason_search]['Reason'].values[0]
            final_filtered_df = final_filtered_df[final_filtered_df['Final_Reason'] == selected_reason_name]
            
        if platform_search != "Select a Platform...":
            selected_platform_name = platform_data[platform_data['Platform_with_Count'] == platform_search]['Platform'].values[0]
            final_filtered_df = final_filtered_df[final_filtered_df['Platform'] == selected_platform_name]
            
        st.divider()
        st.subheader("Filtered Results")

        # 5. Ab neeche teeno tables dikhao
        res1, res2, res3 = st.columns(3)
        
        with res1:
            st.caption("Filtered SKUs")
            sku_display_data = final_filtered_df.groupby('Final_SKU')['Final_Qty'].sum().sort_values(ascending=False).reset_index()
            sku_display_data.columns = ['SKU', 'Total Quantity']
            st.dataframe(sku_display_data, use_container_width=True, height=500)
            
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

    else:
        # Yeh tab dikhega jab file upload hai, lekin data process nahi hua
        st.warning("No data found after processing. Please check your files or column names.")
else:
    # Yeh default message hai
    st.info("Please upload your return files from the sidebar to start the analysis.")
