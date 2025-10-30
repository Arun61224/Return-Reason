import streamlit as st
import pandas as pd

# 1. Aapke diye gaye column names ka mapping
COLUMN_MAPPING = {
    'flipkart': {
        # --- UPDATE YAHAN KIYA HAI ---
        'sku_col': 'sku',  # 'SKU' ko 'sku' (lowercase) kar diya hai
        # -----------------------------
        'reason_col': 'Retrun Sub-reason'
    },
    'ajio': {
        'sku_col': 'SELLER SKU',
        'reason_col': 'Cust Return Reason'
    },
    'amazon': {
        'sku_col': 'sku',
        'reason_col': 'reason'
    },
    'meesho': {
        'sku_col': 'SKU',
        'reason_col': 'Detailed Return Reason'
    }
}

# 2. File processing function
def process_files(uploaded_files):
    all_data_list = []
    
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name.lower()
        platform = None
        
        if 'amazon' in filename:
            platform = 'amazon'
        elif 'flipkart' in filename:
            platform = 'flipkart'
        elif 'meesho' in filename:
            platform = 'meesho'
        elif 'ajio' in filename:
            platform = 'ajio'
        
        if platform:
            df = None # Initialize df here
            try:
                # Platform ke hisaab se mapping nikalo
                mapping = COLUMN_MAPPING[platform]
                
                # File ko read karo (Excel ya CSV)
                if filename.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                else:
                    df = pd.read_csv(uploaded_file)
                
                # --- Extra spaces hatane ke liye ---
                df.columns = df.columns.str.strip()
                # ------------------------------------
                
                # Sirf zaroori columns select karo aur rename karo
                temp_df = df[[mapping['sku_col'], mapping['reason_col']]].copy()
                temp_df.rename(columns={
                    mapping['sku_col']: 'Final_SKU',
                    mapping['reason_col']: 'Final_Reason'
                }, inplace=True)
                
                temp_df['Platform'] = platform.capitalize()
                all_data_list.append(temp_df)

            # --- Error ko behtar tareeke se dikhane ke liye ---
            except KeyError as e:
                st.error(f"Error processing {filename}: Column {e} nahi mila.")
                if df is not None:
                    st.error(f"File ke andar yeh columns mile hain: {list(df.columns)}")
                st.warning("Please code mein 'COLUMN_MAPPING' ko upar di gayi list ke hisaab se theek karo.")
            # -----------------------------------------------------------
            except Exception as e:
                st.error(f"Error processing {filename}: {e}.")
                
    if not all_data_list:
        return pd.DataFrame(columns=['Final_SKU', 'Final_Reason', 'Platform'])

    # Saare data ko ek final DataFrame mein combine karo
    master_df = pd.concat(all_data_list, ignore_index=True)
    master_df.dropna(subset=['Final_SKU', 'Final_Reason'], inplace=True)
    master_df['Final_SKU'] = master_df['Final_SKU'].astype(str)
    master_df['Final_Reason'] = master_df['Final_Reason'].astype(str)
    
    return master_df

# --- Streamlit App ka UI (BAAKI SAB SAME) ---
st.set_page_config(layout="wide")
st.title("🛍️ Online Seller Return Analysis Dashboard")

# 3. File Uploader
st.header("Step 1: Upload Files")
uploaded_files = st.file_uploader(
    "Upload all your return reports (Amazon, Flipkart, Ajio, Meesho)",
    accept_multiple_files=True,
    type=['xlsx', 'csv']
)

# 4. Jab files upload ho jaayein, tab dashboard dikhao
if uploaded_files:
    master_df = process_files(uploaded_files)
    
    if not master_df.empty:
        st.success(f"Successfully processed {len(uploaded_files)} files. Total {len(master_df)} returns found.")
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
        
        # --- Dashboard UI ---
        
        if not selected_sku:
            st.header("Overall Return Analysis")
            st.info("Select an SKU from the sidebar to see a detailed breakdown.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Top 10 Most Returned SKUs")
                top_skus = filtered_df['Final_SKU'].value_counts().head(10)
                st.bar_chart(top_skus)

            with col2:
                st.subheader("Top 10 Return Reasons (Overall)")
                top_reasons = filtered_df['Final_Reason'].value_counts().head(10)
                st.bar_chart(top_reasons)
            
            st.subheader("Returns by Platform")
            platform_counts = filtered_df['Platform'].value_counts()
            st.bar_chart(platform_counts)
        
        else:
            st.header(f"Deep-Dive for SKU: {selected_sku}")
            
            sku_specific_df = filtered_df[filtered_df['Final_SKU'] == selected_sku]
            
            total_returns = sku_specific_df.shape[0]
            st.metric("Total Returns for this SKU", total_returns)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Return Reasons")
                reason_counts = sku_specific_df['Final_Reason'].value_counts()
                st.bar_chart(reason_counts)
            
            with col2:
                st.subheader("Returns by Platform")
                platform_counts = sku_specific_df['Platform'].value_counts()
                st.bar_chart(platform_counts)
                
            st.subheader("Raw Return Data for this SKU")
            st.dataframe(sku_specific_df)

    else:
        st.warning("No data found after processing. Please check your files.")
else:
    st.info("Please upload your return files to start the analysis.")
