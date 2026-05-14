import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Settlement Analysis Dashboard", layout="wide")

@st.cache_data(show_spinner=False)
def load_and_clean_data(file_contents, file_name):
    if file_name.endswith('.xlsx'):
        df = pd.read_excel(file_contents, header=None, engine='calamine')
    else:
        df = pd.read_csv(file_contents, header=None, encoding='ISO-8859-1')

    start_row = 0
    for i in range(len(df)):
        row_values = df.iloc[i].astype(str).tolist()
        if any(k in str(val).upper() for val in row_values for k in ["TRANSACTION ID", "MERCHANT NAME", "CAPTURE DATE"]):
            start_row = i
            break
    
    clean_df = df.iloc[start_row:].copy()
    clean_df.columns = clean_df.iloc[0]
    clean_df = clean_df[1:].reset_index(drop=True)
    clean_df.columns = [str(col).strip() for col in clean_df.columns]
    clean_df = clean_df.loc[:, ~clean_df.columns.str.contains('^Unnamed|^nan|^NaT', na=False)]

    for col in clean_df.select_dtypes(include=['number']).columns:
        clean_df[col] = clean_df[col].fillna(0)
    for col in clean_df.select_dtypes(exclude=['number']).columns:
        clean_df[col] = clean_df[col].fillna("Unknown")
        
    return clean_df

head_l, head_r = st.columns([3, 1])

with head_l:
    st.title("Settlement & Payout Analysis")

with head_r:
    my_file = st.file_uploader("Upload Excel or CSV", type=['xlsx', 'csv'], label_visibility="collapsed")

file_log_path = "processed_files.txt"

if my_file is not None:
    try:
        data = load_and_clean_data(my_file, my_file.name)

        
        if os.path.exists(file_log_path):
            with open(file_log_path, "r") as f:
                already_processed = f.read().splitlines()
        else:
            already_processed = []

        def find_col(keywords):
            for col in data.columns:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return None

        amt_col = find_col(['Trans Amount', 'Transaction AMOUNT'])
        net_col = find_col(['Net Settlement Amount', 'NET AMOUNT AFTER E COM TAX'])
        tax_col = find_col(['FED', 'Tax on APPS Charges'])
        bank_col = find_col(['Bank Name', 'Bank'])
        status_col = find_col(['Status'])
        merch_col = find_col(['Merchant Name'])

        for col in [amt_col, net_col, tax_col]:
            if col:
                data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

        total_vol = data[amt_col].sum() if amt_col else 0
        net_vol = data[net_col].sum() if net_col else 0
        tax_vol = data[tax_col].sum() if tax_col else 0
        
        success_percent = 100.0
        if status_col:
            success_count = len(data[data[status_col].astype(str).str.contains('Success', case=False)])
            success_percent = (success_count / len(data)) * 100 if len(data) > 0 else 0
        
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Volume", f"Rs {total_vol:,.2f}")
            c2.metric("Net Settlement", f"Rs {net_vol:,.2f}")
            c3.metric("Total Tax", f"Rs {tax_vol:,.2f}")
            c4.metric("Success Rate", f"{success_percent:.1f}%", delta="Normal", delta_color="normal") 
        
        tab1, tab2 = st.tabs(["Analytics Overview", "Data Explorer"])

        with tab1:
            l, r = st.columns(2)
            with l:
                if merch_col and amt_col:
                    show_perc = st.checkbox("Show Market Share (%)")
                    merchant_data = data.groupby(merch_col)[amt_col].sum().sort_values(ascending=False)
                    if show_perc:
                        st.subheader("Market Share by Merchant")
                        merchant_perc = ((merchant_data / total_vol) * 100) if total_vol > 0 else merchant_data
                        st.bar_chart(merchant_perc, horizontal=True, color="#00d4ff")
                    else:
                        st.subheader("Top 10 Merchants")
                        st.bar_chart(merchant_data.head(10), horizontal=True, color="#00d4ff")

            with r:
                if bank_col:
                    st.subheader("Volume by Bank")
                    bank_data = data[bank_col].astype(str).str.upper().value_counts().head(10)
                    st.bar_chart(bank_data, horizontal=True, color="#2ecc71")

        with tab2:
            search_term = st.text_input("Quick Search Merchant Name", placeholder="Type to filter...")
            display_df = data.copy()
            if search_term and merch_col:
                display_df = display_df[display_df[merch_col].str.contains(search_term, case=False, na=False)]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        if my_file.name not in already_processed:
            clean_name = os.path.splitext(my_file.name)[0]
            processed_filename = f"{clean_name}_processed_data.csv"
            data.to_csv(processed_filename, index=False)
            with open(file_log_path, "a") as f:
                f.write(my_file.name + "\n")
            st.success(f"Log Updated: {processed_filename}")

    except Exception as err:
        st.error(f"Error processing file: {err}")
else:
    st.info("Dashboard is empty. Please upload a file to begin.")