import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from babel.numbers import format_currency

def format_inr(amount):
    return format_currency(amount, 'INR', locale='en_IN', format=u'¤#,##,##0',currency_digits=False)

# Load Data
@st.cache_data
def load_data():
    pay_matrix = pd.read_excel("7_cpc_pay_matrix.xlsx")
    pay_matrix['Pay_Position'] = pd.to_numeric(pay_matrix['Pay_Position'], errors='coerce')
    pay_matrix['CPC'] = '7CPC'
    pay_matrix=pay_matrix.dropna(subset="Basic_Pay")
    return pay_matrix

pay_matrix = load_data()

st.title("Indian Government Employees Pension Comparison: NPS vs UPS")
# User Inputs

st.caption("Ages and dates")
today_date = date.today()

dob=pd.to_datetime(
    st.date_input("Your Date of birth",
                  value=date(1990, 5, 23),
                  min_value=date(1960, 1, 1),
                  max_value=date(2050, 12, 31)
                  )
)

joining_date = pd.to_datetime(
    st.date_input("Date of Joining the department",
                  value=date(2023, 4, 11),
                  min_value=date(2004, 1, 1),
                  max_value=today_date
                  )
    )

retirement_age = st.number_input("Retirement Age", 50, 65, 60)

nps_corpus = st.number_input("Enter NPS Corpus as today(₹):", min_value=0)

st.divider()
st.caption("Grade pay and cell values")

unique_levels = sorted(pay_matrix['Level'].dropna().unique())
initial_level = st.selectbox("Current Pay Level", unique_levels,index=4)
initial_position = st.number_input("Current Pay Position cell", min_value=1, max_value=40, value=1)
date_of_increment = st.selectbox("Month of Annual Increment", ["January", "July"])

st.divider()
st.caption("Promotions")
num_promotions = st.number_input("Number of Promotions to be announced", 0, 10, 3)

promotion_plan = []
for i in range(num_promotions):
    st.divider()
    st.caption(f"Promotion {i+1}")
    interval = st.number_input(f"{i+1} Promotion after today years", 1, 40, (i+1)*6)
    next_level = st.selectbox(f"Next Pay Level for Promotion {i+1}", unique_levels, index=min(i+5, len(unique_levels)-1), key=f"promo_{i}")
    promotion_plan.append({"interval": interval, "level": next_level})

st.divider()
st.caption("Fitment factor=(1+DA Rate/100)*(1+Pay commision increase/100)")

pay_comm_increase = st.slider("Average Pay Commission Increase (%)", 10, 50, 15) / 100

st.divider()
st.caption("Various rate assumptions ")

current_da = st.number_input("Current DA RATE", min_value=40, max_value=80, value=55) / 100
da_increment_rate = st.slider("DA increment (%)", 1.0, 9.0, 3.0) / 100
nps_contribution_rate = st.number_input("Total NPS Contribution Rate (% of Basic + DA)", 10, 30, 10) / 100
nps_return = st.slider("NPS Annual Return Rate (%)", 5.0, 16.0, 8.0) / 100
annuity_pct = st.slider("% of Corpus Converted to Annuity", 40, 100, 40) / 100
annuity_rate = st.slider("Annual Annuity Rate (%)", 3.0, 9.0, 6.0) / 100
life_expectancy_year = st.slider("Expected Years to Live Beyond Retirement", min_value=1, max_value=50, value=20)


ups_corpus = nps_corpus


CPC_YEARS = {
    '8CPC': 2026,
    '9CPC': 2036,
    '10CPC': 2046,
    '11CPC': 2056,
    '12CPC':2066,
}

BASE_CPC = '7CPC'


def generate_cpc_tables(base_matrix, pay_comm_increase):
    all_cpc_tables = [base_matrix.copy()]
    cpc_years = CPC_YEARS.copy()
    prev_cpc = BASE_CPC
    for cpc, cpc_start_year in cpc_years.items():
        prev_cpc_table = all_cpc_tables[-1]       
        fitment = (1 + current_da) * (1 + pay_comm_increase)
        new_table = prev_cpc_table.copy()
        new_table['Basic_Pay'] = (new_table['Basic_Pay'] * fitment).round(-2)
        new_table['CPC'] = cpc
        all_cpc_tables.append(new_table)
    return pd.concat(all_cpc_tables, ignore_index=True)

pay_matrix_full = generate_cpc_tables(pay_matrix, pay_comm_increase)



# --- Simulation Timeline ---
retire_year = dob.year + retirement_age 
retire_date = datetime(retire_year, joining_date.month, joining_date.day)

months = pd.date_range(start=joining_date, end=retire_date, freq='MS')

q_upon_300=len(months)/300
if q_upon_300 >1:
    q_upon_300=1

number_of_six_months = len(months)/6

months = pd.date_range(start=today_date, end=retire_date, freq='MS')

life_expectancy_date=datetime(retire_year+life_expectancy_year, dob.month, dob.day)
months_after_retirement=pd.date_range(start=retire_date, end=life_expectancy_date, freq='MS')

# --- Main Calculation Loop ---
records = []
level = initial_level
position = initial_position
current_cpc = BASE_CPC
cpc_years_sorted = [(BASE_CPC, joining_date.year)] + [(cpc, y) for cpc, y in CPC_YEARS.items()]
cpc_pointer = 0
basic_pay = pay_matrix_full.query("Level == @level and Pay_Position == @position and CPC == @current_cpc")['Basic_Pay'].values[0]


for i, month in enumerate(months):
    year = month.year
    is_jan = month.month == 1
    is_july = month.month == 7
    pay_commission_applied = ""
    
    # DA increases every Jan and July at 2%
    if is_jan or is_july:
        current_da += da_increment_rate

    # Switch CPC if month/year matches new CPC cycle
    if (cpc_pointer + 1 < len(cpc_years_sorted)) and (year == cpc_years_sorted[cpc_pointer + 1][1]) and is_jan:
        cpc_pointer += 1
        current_cpc = cpc_years_sorted[cpc_pointer][0]
        fitment = (1 + current_da) * (1 + pay_comm_increase)
        pay_commission_applied = f"Pay commission:{current_cpc} with fitment factor:{fitment:,.2f}"
        # Fetch new Basic Pay from the new CPC matrix
        basic_pay_new = pay_matrix_full.query(
         "Level == @level and Pay_Position == @position and CPC == @current_cpc"
            )['Basic_Pay']
        if not basic_pay_new.empty:
            basic_pay = basic_pay_new.values[0]
       # Reset DA after each CPC
        current_da = 0.0

    
    da_amt = basic_pay * current_da
    total_emoluments = basic_pay + da_amt

    # Increment
    if (date_of_increment == "January" and is_jan) or (date_of_increment == "July" and is_july):
        next_position = position + 1
        new_pay = pay_matrix_full.query("Level == @level and Pay_Position == @next_position and CPC == @current_cpc")['Basic_Pay']
        if not new_pay.empty:
            basic_pay = new_pay.values[0]
            position = next_position
    
    years_since_today = year - today_date.year
    
    # Check if any promotion is scheduled at this year mark
    for promo in promotion_plan:
        if promo['interval'] == years_since_today and is_jan:

            next_position = position + 1
            new_pay = pay_matrix_full.query("Level == @level and Pay_Position == @next_position and CPC == @current_cpc")['Basic_Pay']
            if not new_pay.empty:
                basic_pay = new_pay.values[0]
                position = next_position
                
            next_level = promo['level']
            cell=1
            while(True):
                promoted_pay = pay_matrix_full.query("Level == @next_level and Pay_Position == @cell and CPC == @current_cpc")['Basic_Pay']
                if(promoted_pay.values[0]< basic_pay):
                    cell+=1
                else:
                    break  
            if not promoted_pay.empty:
                level = next_level
                basic_pay = promoted_pay.values[0]
                position = cell


    # NPS corpus
    monthly_contribution_nps = total_emoluments * (nps_contribution_rate + 0.14)
    nps_corpus = (nps_corpus + monthly_contribution_nps) * ((1 + nps_return) ** (1 / 12))

    monthly_contribution_ups = total_emoluments * (nps_contribution_rate + 0.1)
    ups_corpus = (ups_corpus + monthly_contribution_ups) * ((1 + nps_return) ** (1 / 12))

    records.append({
        "Month": month.strftime("%b-%Y"),
        "Year": year,
        "Level": level,
        "Position": position,
        "CPC": current_cpc,
        "Basic Pay": round(basic_pay),
        "DA Rate %": round(current_da*100),
        "DA Amount":format_inr(da_amt),
        "Total Emoluments": format_inr(total_emoluments),
        "Monthly NPS Contribution": format_inr(monthly_contribution_nps),
        "NPS Corpus": format_inr(nps_corpus),
        "Monthly UPS Contribution": format_inr(monthly_contribution_ups),
        "UPS Corpus":format_inr(ups_corpus),
        "Pay Commission Applied": pay_commission_applied
    })

# --- Final Outputs ---
df = pd.DataFrame(records)

final_basic = basic_pay
avg_last_12_emoluments = df['Basic Pay'].tail(12).mean()
#sprint(avg_last_12_emoluments)

ups_pension = 0.5 * avg_last_12_emoluments*q_upon_300*annuity_pct
dr_on_pension =ups_pension*current_da
ups_lumpsum_six=number_of_six_months*avg_last_12_emoluments*(1+current_da)*0.1
ups_lumpsum_corpus=ups_corpus* (1-annuity_pct)

nps_pension = (nps_corpus * annuity_pct) * annuity_rate/12
nps_lumpsum_six=0.0
nps_lumpsum_corpus=nps_corpus*(1-annuity_pct)
nps_dr=0.0


# --- Results ---
st.subheader("Monthly Pay Progression Table")
st.dataframe(df)

# Pension Comparison Summary Table
comparison_data = {
    "UPS": [
        f"{format_inr(ups_corpus)}",
        f"{format_inr(ups_lumpsum_corpus)}",
        f"{format_inr(ups_lumpsum_six)}",
        f"{format_inr(ups_lumpsum_corpus+ups_lumpsum_six)}",
        f"{format_inr(ups_pension)}",
        f"{format_inr(dr_on_pension)}",
        f"{format_inr(dr_on_pension+ups_pension)}"
    ],
    "NPS": [
        f"{format_inr(nps_corpus)}",
        f"{format_inr(nps_lumpsum_corpus)}",
        f"{nps_lumpsum_six:,.0f}",
        f"{format_inr(nps_lumpsum_corpus+nps_lumpsum_six)}",
        f"{format_inr(nps_pension)}",
        f"{nps_dr:,.0f}",
        f"{format_inr(nps_dr+nps_pension)}",
        
    ]
}

comparison_df = pd.DataFrame(comparison_data, index=[
    "Total Corpus in pool(IC)",
    "Lumpsum at Retirement",
    "Lumpsum at Retirement for each completed six month",
    "Total Lumpusum at retirement",
    f"Monthly Basic Pension",
    f"DR on Monthly Pension(DR={current_da*100:,.0f}%)",
    f"Total Monthly Pension",
])

st.subheader("Pension Scheme Comparison at Retirement")
st.dataframe(comparison_df)

records_pen = []
com_nps=0
com_ups=0

for i, month in enumerate(months_after_retirement):
    year = month.year
    is_jan = month.month == 1
    is_july = month.month == 7
    if is_jan or is_july:
        current_da += da_increment_rate
        
    da_amt = ups_pension * current_da
    total_emoluments = ups_pension + da_amt

    com_ups += total_emoluments 
    com_nps += nps_pension


    records_pen.append({
        "Month": month.strftime("%b-%Y"),
        "Year": year,
        "UPS Pension Basic": format_inr(ups_pension),
        "DR Rate %": round(current_da*100),
        "DR Amount": format_inr(da_amt),
        "Total Montlhy UPS": format_inr(total_emoluments),
        "Comulative UPS": format_inr(com_ups),
        "Monthly NPS Pension": format_inr(nps_pension),
        "Comulative NPS":format_inr(com_nps),       
        
    })

total_nps_paid=com_nps+nps_lumpsum_corpus
total_ups_paid=com_ups+ups_lumpsum_corpus+ups_lumpsum_six


# --- Final Outputs ---
df = pd.DataFrame(records_pen)
st.subheader("Pension Scheme Comparison after Retirement")
st.dataframe(df)

st.subheader("All benefits")
st.markdown(f"**Total Amount Paid in NPS:** {format_inr(total_nps_paid)}+ after death {format_inr(nps_corpus * annuity_pct)}")
st.markdown(f"**Total Amount Paid in UPS:** {format_inr(total_ups_paid)}")


