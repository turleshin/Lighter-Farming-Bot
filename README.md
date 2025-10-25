## Lighter Farming Bot

This repository contains a simple trading bot example (`bot.py`) that uses the Lighter SDK to place market orders, take-profits and stop-losses. The bot is interactive and prompts for credentials and parameters at startup.

### Summary
- Language: Python
- Purpose: Example automated trading loop that places market entries and TP/SL orders using the `SignerClient` from the Lighter SDK.

### Requirements
- Python 3.10 or newer
- A Lighter SDK installation (see options below)

### Quick install (Windows PowerShell)
1. Open PowerShell and navigate to this project folder (the folder that contains `bot.py`).

2. Create and activate a virtual environment:

```powershell
python3 -m venv .venv
source venv/bin/activate
```

3. Upgrade pip and install dependencies:

```powershell
python3 -m pip install --upgrade pip
pip install git+https://github.com/elliottech/lighter-python.git
```

If the Lighter SDK is published to PyPI under a known name you can alternatively `pip install lighter` (replace name/version accordingly).

### Configuration
When you run the bot it will prompt for the following values:

- Login Address (L1 Wallet Address)
- API Private Key
- API Key Index (integer)
- Orders Per Hour (float)
- Leverage (float)

Default parameters (edit `BotConfig` inside `bot.py` if you need different defaults):

- Market: `ETH`
- Base amount: `150` (this bot uses integer base units; check the SDK docs for units)
- Take-profit percent: `0.25%` (0.0025)
- Stop-loss percent: `0.15%` (0.0015)
- Base API URL: `https://mainnet.zklighter.elliot.ai` (change in `BotConfig` if you want testnet)

Security note: Keep your API private key secret. Do not commit it into source control.

### Run
In the activated virtual environment run:

```powershell
python3 bot.py
```

Stop the bot with Ctrl+C.

### Troubleshooting
- ImportError: If Python can't find the `lighter` package, install the SDK (either from PyPI or the local `../lighter-python` folder).
- No account found: Ensure the L1 wallet address is associated with a subaccount on the Lighter dashboard.
- Authentication errors: Check your API private key and key index. Ensure the SDK endpoint (base_url) is reachable.

### Notes & next steps
- This example uses a hardcoded market id (`0`) — replace the market lookup logic with the SDK call to fetch the correct market id if needed.
- Consider providing configuration via environment variables or a config file for automation instead of interactive prompts.

You can checkout Lighter SDK repo for more infomations: https://github.com/elliottech/lighter-python
