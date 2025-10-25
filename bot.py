import asyncio
import time
from decimal import Decimal
from lighter import (
    ApiClient, 
    AccountApi, 
    OrderApi, 
    TransactionApi, 
    SignerClient, 
    Configuration,
)

# --- SECTION 1: CONFIGURATION ---
class BotConfig:
    """A centralized configuration object for the trading bot."""
    def __init__(self):
        print("--- Bot Configuration ---")
        self.l1_address = input("Enter Login Address (L1 Wallet Address): ").strip()
        self.api_private_key = input("Enter API Private Key: ").strip()
        self.api_key_index = int(input("Enter API Key Index: "))
        self.orders_per_hour = float(input("Enter Orders Per Hour: "))
        self.leverage = float(input("Enter Leverage: "))
        print("-------------------------\n")

        # Static Parameters
        self.market = 'ETH'  # Full market symbol
        self.base_amount = 150  # Forced base amount, adjust as needed to avoid overflow
        self.tp_percent = 0.0025  # 0.2%
        self.sl_percent = 0.0015  # 0.2%
        self.base_url = "https://mainnet.zklighter.elliot.ai"
        
        if self.orders_per_hour <= 0:
            print("Warning: orders_per_hour is zero or negative. Bot will only run one cycle.")
            self.sleep_duration = float('inf')
        else:
            self.sleep_duration = 3600.0 / self.orders_per_hour
        self.failed_order_sleep = 30.0  # Sleep duration for failed orders

# --- SECTION 2: HELPER FUNCTIONS ---
async def get_last_trade_price(order_api: OrderApi, market_id: int) -> float:
    """Fetches the last trade price for a given market ID."""
    try:
        recent_trades = await order_api.recent_trades(market_id=market_id, limit=1)
        if recent_trades and recent_trades.trades:
            last_price = float(recent_trades.trades[0].price)
            print(f"Fetched last trade price for market ETH-USDC : ${last_price}")
            return last_price
        else:
            print(f"Warning: Could not fetch recent trades for market {market_id}.")
            return None
    except Exception as e:
        print(f"Error fetching last trade price: {e}")
        return None

client_order_counter = 1  # Global counter for unique client_order_index

async def place_market_order(signer_client: SignerClient, market_id: int, price: float, config: BotConfig) -> tuple:
    """Places a market order, TP, and SL using SignerClient."""
    global client_order_counter
    try:
        base_amount = config.base_amount
        
        market_coi = client_order_counter
        client_order_counter += 1
        print()
        print(f"Creating market order: BUY {config.market}-USDC amount {base_amount/10000} at Market price: {price}")
        tx_market = await signer_client.create_order(
            market_index=market_id,
            client_order_index=market_coi,
            base_amount=base_amount,
            order_type=signer_client.ORDER_TYPE_MARKET,
            price=int((price + 0.5) * 100),  # Assuming 2 decimal precision, with slippage
            time_in_force=signer_client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            reduce_only=False,
            order_expiry=0,
            is_ask=False
        )
        
        tp_price = price * (1 + config.tp_percent)
        tp_trigger = int(tp_price * 100)
        tp_limit_price = int(tp_price * 100)
        tp_coi = client_order_counter
        client_order_counter += 1
        tx_tp = await signer_client.create_tp_limit_order(
            market_index=market_id,
            client_order_index=tp_coi,
            base_amount=base_amount,
            trigger_price=tp_trigger,
            price=tp_limit_price,
            is_ask=True
        )
        
        sl_price = price * (1 - config.sl_percent)
        sl_trigger = int(sl_price * 100)
        sl_limit_price = int((sl_price - 0.2) * 100)  # Slightly worse
        sl_coi = client_order_counter
        client_order_counter += 1
        tx_sl = await signer_client.create_sl_limit_order(
            market_index=market_id,
            client_order_index=sl_coi,
            base_amount=base_amount,
            trigger_price=sl_trigger,
            price=sl_limit_price,
            is_ask=True
        )
        
        print(f"Successfully sent market order.")
        return tx_market, tp_coi, sl_coi
    except Exception as e:
        print(f"Error placing market order: {e}")
        return None, None, None

async def get_current_position(account_api: AccountApi, account_index: int, market_id: int) -> dict:
    """Fetches the current position for the market."""
    try:
        # Adjusted method name based on potential SDK differences
        account = await account_api.account(by="index", value=str(account_index))
        my_account = account.accounts[0]
        current_bal = my_account.total_asset_value
        print(f"Current Account Balance: {current_bal} USDC ")
        
        active_pos = my_account.positions
        for pos in active_pos:
            if float(pos.position) > 0.0:
                # Format the position string
                direction = "Long" if int(pos.sign) > 0 else "Short"
                position_str = f"| {direction} | {pos.symbol}/USDC | Size: {pos.position} | Entry: {pos.avg_entry_price} | uPNL: {pos.unrealized_pnl} |"
                
                # Calculate the length of the position string and create dashed line
                dash_line = "-" * len(position_str)
                
                # Print the formatted output with dynamic dashed lines
                print(dash_line)
                print(position_str)
                print(dash_line)
                
        return {'size': float(pos.position), 'entry_price': float(pos.avg_entry_price)} if active_pos else {'size': 0}
    except Exception as e:
        print(f"Error fetching position: {e}")
        return {'size': 0}

# --- SECTION 3: MAIN TRADING LOGIC ---
async def main():
    config = BotConfig()
    
    unauth_config = Configuration(host=config.base_url)
    unauth_client = ApiClient(configuration=unauth_config)
    account_api = AccountApi(unauth_client)
    unauth_order_api = OrderApi(unauth_client)

    # Step 1: Get Account Index (Unauthenticated)
    try:
        accounts = await account_api.accounts_by_l1_address(l1_address=config.l1_address)
        if not accounts or not accounts.sub_accounts:
            print("Error: No account found for the given L1 address. Please create a subaccount in the Lighter dashboard.")
            return
            
        account_index = accounts.sub_accounts[0].index
        print(f"Successfully found Account Index: {account_index} (Type: {type(account_index)})")
        
        if not isinstance(account_index, int):
            print(f"Fatal Error: Account Index is not an integer. Got: {account_index}")
            return
    except Exception as e:
        print(f"Fatal Error fetching account index: {e}")
        return
    # Step 1.5: Get Market ID from Market Symbol
    print(f"Fetching market ID for {config.market}...")
    market_id_int = 0  # Hardcoded; replace with actual market ID fetching if available
    print("Using market id default is 0")

    # Step 2: Initialize Signer Client (Authenticated)
    try:
        signer_client = SignerClient(
            url=config.base_url,
            private_key=config.api_private_key,
            account_index=account_index,
            api_key_index=config.api_key_index
        )
        err = signer_client.check_client()
        if err:
            print(f"Fatal Signer client error: {err}")
            return
        
        auth, err = signer_client.create_auth_token_with_expiry(SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY)
        if err:
            print(f"Fatal Auth token error: {err}")
            return
        print("Authentication successful. Bot is starting...")
    except Exception as e:
        print(f"Fatal Error during SignerClient init or auth: {e}")
        return

    # Step 3: Create Authenticated API Clients
    auth_config = Configuration(host=config.base_url)
    auth_api_client = ApiClient(
        configuration=auth_config, 
        header_name="Authorization", 
        header_value=f"Bearer {auth}"
    )
    
    order_api = OrderApi(auth_api_client)
    transaction_api = TransactionApi(auth_api_client)
    auth_account_api = AccountApi(auth_api_client)

    active_pairs = []  # List of {'tp_coi': int, 'sl_coi': int}

    while True:
        print("\n" + "="*50)
        print(f"[{time.ctime()}] New trading cycle.")
        print("Searching for a new entry...")
            
        price = await get_last_trade_price(order_api, market_id_int)
        if price is None:
            print("Could not get price. Sleeping for 30 seconds.")
            await asyncio.sleep(config.failed_order_sleep)
            continue

        # Monitor and clean up closed trades

        # Get current position (for logging)

        # Place new market order only if no position
        entry_response, tp_coi, sl_coi = await place_market_order(signer_client, market_id_int, price, config)
        if entry_response:
            print("Create market order successful !!")
            active_pairs.append({'tp_coi': tp_coi, 'sl_coi': sl_coi})
        else:
            print("Failed to enter position. Sleeping for 30 seconds.")
            await asyncio.sleep(config.failed_order_sleep)
            continue
        print()
        position1 = await get_current_position(auth_account_api, account_index, market_id_int)
        print(f"Cycle finished. Sleeping for {config.sleep_duration:.2f} seconds.")
        await asyncio.sleep(config.sleep_duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
