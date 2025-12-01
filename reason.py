import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import io
import plotly.express as px
import xlsxwriter
import streamlit.components.v1 as components

# --- Page Config ---
st.set_page_config(page_title="Return Analysis Dashboard", page_icon="⚡", layout="wide")

# --- 1. REACT BITS DITHER BACKGROUND & DARK THEME CSS ---
st.markdown("""
<style>
    /* --- DARK THEME OVERRIDES --- */
    .stApp {
        background-color: #111111; /* Fallback color */
    }
    
    /* Text Colors */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide Header/Footer for clean look */
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* --- GLASSMORPHISM CARDS --- */
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        color: white;
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        border-color: #61dafb; /* React Blue Glow */
        box-shadow: 0 10px 20px rgba(0,0,0,0.5);
    }
    div[data-testid="metric-container"] label {
        color: #aaaaaa !important;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #ffffff !important;
    }

    /* Tables Dark Mode */
    div[data-testid="stDataFrame"] {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 10px;
    }

    /* Canvas Background Container */
    #dither-canvas-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: -1; /* Behind everything */
        pointer-events: none; /* Click through */
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. JAVASCRIPT FOR DITHER EFFECT (Injecting via Component) ---
dither_html = """
<!DOCTYPE html>
<html>
<head>
<style>
    body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #0e0e0e; }
    canvas { display: block; }
</style>
</head>
<body>
<canvas id="canvas"></canvas>
<script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    
    let width, height;
    let time = 0;
    
    // Configuration for the Dither/Wave Effect
    const gap = 25; // Distance between dots
    const baseRadius = 1.5; // Size of dots
    const waveSpeed = 0.02;
    const waveFreq = 0.05;
    
    function resize() {
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = width;
        canvas.height = height;
    }
    
    function draw() {
        // Clear background with slight fade for trail effect (optional, using solid here)
        ctx.fillStyle = '#0e0e0e'; 
        ctx.fillRect(0, 0, width, height);
        
        ctx.fillStyle = '#444444'; // Dot color (Greyish to look like Dither)
        
        for (let x = 0; x < width; x += gap) {
            for (let y = 0; y < height; y += gap) {
                // Calculate wave math
                const dist = Math.sqrt((x - width/2)**2 + (y - height/2)**2);
                const angle = dist * waveFreq - time;
                
                // Sine wave determines dot size
                const radius = baseRadius + Math.sin(angle) * 1.5;
                const opacity = (Math.sin(angle) + 1) / 2; // 0 to 1
                
                if (radius > 0) {
                    ctx.beginPath();
                    ctx.arc(x, y, Math.abs(radius), 0, Math.PI * 2);
                    // Dynamic Color based on wave
                    ctx.fillStyle = `rgba(100, 100, 100, ${0.3 + opacity * 0.5})`; 
                    ctx.fill();
                }
            }
        }
        
        time += waveSpeed;
        requestAnimationFrame(draw);
    }
    
    window.addEventListener('resize', resize);
    resize();
    draw();
</script>
</body>
</html>
"""

# Injecting the background script
components.html(dither_html, height=0, scrolling=False)


# --- UTILITY FUNCTIONS ---
@st.cache_data
def convert_df_to_excel_formatted(df, sheet_name='SKU_Summary'):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            (max_row, max_col) = df.shape 
            worksheet.add_table(0, 0, max_row, max_col - 1, {
                'columns': [{'header': col} for col in df.columns],
                'style': 'Table Style Medium 9'
            })
            worksheet.freeze_panes(1, 0)
            for i, col in enumerate(df.columns):
                worksheet.set_column(i, i, 20)
                if col == 'Return % (Decimal)':
                    percent_format = workbook.add_format({'num_format': '0.00%'})
                    worksheet.set_column(i, i, 20, percent_format)
    except Exception as e:
        st.error(f"Excel formatting failed. Using default engine.")
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name=sheet_name, engine='openpyxl')
        output.seek(0)
        return output.getvalue()
    return output.getvalue()

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
        return total_orders_platform_df
    except Exception as e:
        st.sidebar.error(f"Error processing Sales Data: {e}")
        return None

# --- SIDEBAR ---
st.sidebar.title("🔧 Settings")
st.sidebar.info("Upload files to activate the dashboard.")

uploaded_returns_files = st.sidebar.file_uploader(
    "1. Upload Returns", accept_multiple_files=True, type=['xlsx', 'csv', 'zip'], key='returns_uploader'
)

uploaded_sales_file = st.sidebar.file_uploader(
    "2. Upload Sales (Optional)", type=['xlsx', 'csv'], key='sales_uploader'
)

template_data = {'MSKU': ['SKU_1', 'SKU_2'], 'Customer Shipments': [10, 5], 'Platform': ['Amazon', 'Flipkart']}
st.sidebar.download_button(
    label="📄 Get Sales Template",
    data=pd.DataFrame(template_data).to_csv(index=False).encode('utf-8'),
    file_name='sales_data_template.csv',
    mime='text/csv'
)

# --- MAIN APP ---
st.title("⚡ Return Analytics Hub")
st.markdown("Interactive dashboard with live insights.")

if uploaded_returns_files:
    master_df = process_returns_files(uploaded_returns_files)
    total_orders_platform_df = process_sales_data(uploaded_sales_file)
    
    if not master_df.empty:
        # KPI Calculation
        total_returns = master_df['Final_Qty'].sum()
        unique_skus = master_df['Final_SKU'].nunique()
        
        total_sales_count = 0
        return_percent_val = 0
        if total_orders_platform_df is not None:
            total_sales_count = total_orders_platform_df['Total_Orders'].sum()
            if total_sales_count > 0:
                return_percent_val = (total_returns / total_sales_count) * 100

        st.markdown("### 🚀 Overview")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Returns", f"{total_returns:,}")
        kpi2.metric("Unique SKUs", f"{unique_skus}")
        kpi3.metric("Return Rate", f"{return_percent_val:.2f}%" if total_sales_count > 0 else "N/A")
        kpi4.metric("Top Platform", master_df.groupby('Platform')['Final_Qty'].sum().idxmax())

        st.markdown("---")

        # Charts (Dark Mode Optimized)
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            sku_chart = master_df.groupby('Final_SKU')['Final_Qty'].sum().nlargest(10).reset_index()
            fig1 = px.bar(sku_chart, x='Final_SKU', y='Final_Qty', title="Top 10 High Return SKUs",
                          color='Final_Qty', color_continuous_scale='Viridis', template="plotly_dark")
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_c2:
            plat_chart = master_df.groupby('Platform')['Final_Qty'].sum().reset_index()
            fig2 = px.pie(plat_chart, values='Final_Qty', names='Platform', title="Platform Share",
                          hole=0.5, template="plotly_dark", color_discrete_sequence=px.colors.sequential.RdBu)
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        
        # Processing for Table
        # Filters
        st.markdown("### 🔍 Deep Dive")
        with st.expander("Filter Options", expanded=True):
            f1, f2, f3 = st.columns(3)
            sel_skus = f1.multiselect("SKU", master_df['Final_SKU'].unique())
            sel_reasons = f2.multiselect("Reason", master_df['Final_Reason'].unique())
            sel_platforms = f3.multiselect("Platform", master_df['Platform'].unique())

        filtered_df = master_df.copy()
        if sel_skus: filtered_df = filtered_df[filtered_df['Final_SKU'].isin(sel_skus)]
        if sel_reasons: filtered_df = filtered_df[filtered_df['Final_Reason'].isin(sel_reasons)]
        if sel_platforms: filtered_df = filtered_df[filtered_df['Platform'].isin(sel_platforms)]

        # Pivot logic
        TOP_N_REASONS = 10
        reason_agg = filtered_df.groupby(['Final_SKU', 'Final_Reason'])['Final_Qty'].sum().reset_index()
        reason_agg['Rank'] = reason_agg.groupby('Final_SKU')['Final_Qty'].rank(method='first', ascending=False)
        top_reasons = reason_agg[reason_agg['Rank'] <= TOP_N_REASONS].copy()
        top_reasons['Col'] = 'Reason ' + top_reasons['Rank'].astype(int).astype(str)
        top_reasons['Val'] = top_reasons.apply(lambda x: f"{x['Final_Reason']} ({x['Final_Qty']})", axis=1)
        
        sku_reasons_pivot = top_reasons.pivot(index='Final_SKU', columns='Col', values='Val').reset_index().rename(columns={'Final_SKU':'SKU'}).fillna('')
        
        main_sku = filtered_df.groupby('Final_SKU')['Final_Qty'].sum().reset_index().rename(columns={'Final_SKU':'SKU', 'Final_Qty':'Return Qty'})
        
        final_df = main_sku
        if total_orders_platform_df is not None:
            sales_agg = total_orders_platform_df.groupby('Final_SKU')['Total_Orders'].sum().reset_index().rename(columns={'Final_SKU':'SKU'})
            final_df = pd.merge(main_sku, sales_agg, on='SKU', how='left').fillna(0)
            final_df['Return %'] = np.where(final_df['Total_Orders']>0, final_df['Return Qty']/final_df['Total_Orders'], 0)
            final_df['Display %'] = final_df['Return %'].apply(lambda x: f"{x:.2%}")

        final_export = pd.merge(final_df, sku_reasons_pivot, on='SKU', how='left').fillna('')
        
        st.dataframe(
            final_export, 
            use_container_width=True, 
            height=500,
            column_config={
                "Return %": st.column_config.ProgressColumn("Rate", format="%.2f%%", min_value=0, max_value=1)
            }
        )
        
        # Downloads
        c1, c2 = st.columns(2)
        c1.download_button("Download CSV", final_export.to_csv(index=False).encode('utf-8'), "data.csv", "text/csv", use_container_width=True)
        c2.download_button("Download Excel", convert_df_to_excel_formatted(final_export.drop(columns=['Display %'], errors='ignore') if 'Display %' in final_export.columns else final_export), "data.xlsx", use_container_width=True)

    else:
        st.warning("No Data Processed")
else:
    st.info("Waiting for file upload...")
