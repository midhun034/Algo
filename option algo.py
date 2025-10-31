"""
Streamlit app: Algo vs Human Resting Order Simulation
File: streamlit_algo_simulation.py

How to use:
1. Create a new GitHub repository and add this file as `app.py` (or keep the name).
2. Add a `requirements.txt` with: streamlit, pandas, matplotlib
3. Run locally: `streamlit run streamlit_algo_simulation.py`

This app reproduces the scenario you described: an algorithmic market maker that
initially quotes a wide spread, sees a human resting buy, pushes the price up
through a series of trades, then sells into the resting buy when price reaches
a specified percentage above the fair price, and resets quotes.

The UI (sidebar) exposes parameters so you can tune the simulation, then view
an event log, a price/time chart, and download the event log as CSV for GitHub.

Note: This is an educational/stylized simulation and not a market microstructure
model. Use responsibly.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Algo vs Human Resting Order Simulator", layout="wide")

st.title("Algo vs Human Resting Order — Streamlit Simulator")
st.markdown("A simple, configurable simulation that demonstrates the behavior you described: an algo that pushes price up and sells into a resting human buy order.")

# Sidebar controls
st.sidebar.header("Simulation parameters")
fair_price = st.sidebar.number_input("Fair price", value=40.0, step=0.5, format="%.2f")
initial_bid = st.sidebar.number_input("Initial Algo Bid", value=20.0, step=0.5, format="%.2f")
initial_ask = st.sidebar.number_input("Initial Algo Ask", value=80.0, step=0.5, format="%.2f")
algo_bid_reset = st.sidebar.number_input("Algo Reset Bid", value=20.0, step=0.5, format="%.2f")
algo_ask_reset = st.sidebar.number_input("Algo Reset Ask", value=100.0, step=0.5, format="%.2f")
human_limit_price = st.sidebar.number_input("Human resting buy (limit) price", value=21.0, step=0.5, format="%.2f")
qty = st.sidebar.number_input("Quantity (contracts)", value=1, min_value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.markdown("**Price path configuration**")
# Offer a few presets or a manual typed list
preset = st.sidebar.selectbox("Price-step preset", options=["Aggressive climb","Slow climb","Custom"], index=0)
if preset == "Aggressive climb":
    default_steps = "22,25,30,35,40,42,45,48"
elif preset == "Slow climb":
    default_steps = "22,24,26,28,30,32,34,36,38,40,42,44,46,48"
else:
    default_steps = "22,25,30,35,40,42,45,48"

price_steps_text = st.sidebar.text_input("Comma-separated price ticks (algo-created)", value=default_steps)
try:
    price_step_sequence = [float(x.strip()) for x in price_steps_text.split(",") if x.strip()!='']
except Exception:
    st.sidebar.error("Invalid price steps — please enter comma-separated numbers.")
    st.stop()

take_profit_pct = st.sidebar.slider("Algo sell threshold (% above fair)", min_value=0, max_value=200, value=20)

run_sim = st.sidebar.button("Run simulation")

# Helper: run simulation
def simulate(fair_price, initial_bid, initial_ask, algo_bid_reset, algo_ask_reset, human_limit_price, price_step_sequence, take_profit_pct, qty):
    events = []
    time = 0
    best_bid = initial_bid
    best_ask = initial_ask
    last_price = None
    take_profit_threshold = fair_price * (1 + take_profit_pct / 100.0)

    events.append({"time": time, "actor": "market_start", "action": "set_quotes", "price": None, "best_bid": best_bid, "best_ask": best_ask, "note": "Initial wide spread provided by algo"})

    # Human posts a resting limit buy
    time += 1
    events.append({"time": time, "actor": "human", "action": "post_limit_buy", "price": human_limit_price, "best_bid": best_bid, "best_ask": best_ask, "note": "Human posts buy limit order; not filled immediately"})

    human_fill = None

    for p in price_step_sequence:
        time += 1
        last_price = p
        # Simplified quote update
        best_bid = max(algo_bid_reset, last_price - 2)
        best_ask = max(best_bid + 1, last_price + 2)
        events.append({"time": time, "actor": "algo", "action": "aggressive_buy", "price": last_price, "best_bid": best_bid, "best_ask": best_ask, "note": "Algo buying to push price up"})

        # If algo reaches threshold, sell into human's resting buy (fill at current last_price)
        if last_price >= take_profit_threshold:
            time += 1
            fill_price = last_price
            events.append({"time": time, "actor": "algo", "action": "sell_into_human", "price": fill_price, "best_bid": best_bid, "best_ask": best_ask, "note": "Algo sells into the human's resting buy, filling it at elevated price"})
            human_fill = {"time": time, "fill_price": fill_price, "qty": qty}
            time += 1
            best_bid = algo_bid_reset
            best_ask = algo_ask_reset
            events.append({"time": time, "actor": "algo", "action": "reset_quotes", "price": None, "best_bid": best_bid, "best_ask": best_ask, "note": "Algo returns to providing wide spread liquidity"}))
            break

    if human_fill is None:
        events.append({"time": time+1, "actor": "system", "action": "no_fill", "price": None, "best_bid": best_bid, "best_ask": best_ask, "note": "Human's resting buy never got filled in this simulation."})

    df = pd.DataFrame(events)

    # Compute P&L if filled
    if human_fill:
        buy_price = human_fill["fill_price"]
        pnl = (fair_price - buy_price) * human_fill["qty"]
        pnl_percent = (fair_price - buy_price) / buy_price * 100
    else:
        buy_price = None
        pnl = None
        pnl_percent = None

    summary = {
        "fair_price": fair_price,
        "human_limit_price": human_limit_price,
        "human_fill_price": buy_price,
        "human_pnl_per_contract": pnl,
        "human_pnl_percent": pnl_percent,
        "algo_reset_bid": best_bid,
        "algo_reset_ask": best_ask
    }

    return df, summary

# Run or show instructions
if run_sim:
    with st.spinner("Running simulation..."):
        df_events, summary = simulate(fair_price, initial_bid, initial_ask, algo_bid_reset, algo_ask_reset, human_limit_price, price_step_sequence, take_profit_pct, qty)

    st.subheader("Simulation summary")
    st.write(summary)

    st.subheader("Event log")
    st.dataframe(df_events)

    # Prepare price series for plotting
    price_series = df_events[~df_events['price'].isna()][['time','price']].set_index('time')
    if not price_series.empty:
        st.subheader("Price ticks (time series)")
        st.line_chart(price_series['price'])

    # Download button
    csv = df_events.to_csv(index=False)
    st.download_button(label="Download event log as CSV", data=csv, file_name="event_log.csv", mime="text/csv")

    st.markdown("---")
    st.info("If you'd like, I can: add Monte-Carlo runs, partial fills, or package this into a GitHub repo with a README and requirements.txt. Tell me which you'd like next.")
else:
    st.write("Adjust parameters on the left and click **Run simulation**.")
    st.caption("Defaults match the scenario you described: fair_price=40, algo initially quotes 20/80, human resting buy at 21, algo pushes to 48 (20% above fair) and sells into the resting buy.")
