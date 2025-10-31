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
    events.append({"time": time
