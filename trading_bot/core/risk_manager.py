class RiskManager:
    """
    Risk Manager for Joven Inversor Trading Bot.
    Handles position sizing, stop loss, take profit, and Break-Even trailing.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.risk_per_trade_pct = float(config.get("risk_per_trade_pct", 1.5)) / 100.0
        self.rr_ratio = float(config.get("risk_reward_ratio", 2.0))
        self.atr_mult = float(config.get("atr_sl_multiplier", 2.2))
        self.trailing_stop_enabled = config.get("trailing_stop", True)

    def calculate_trade_levels(self, entry_price: float, atr: float, signal_type: int, current_balance: float, ema50: float = None):
        """
        Calculate Stop Loss (SL), Take Profit (TP), and Position Size.
        Uses EMA50 as dynamic anchor if available, otherwise ATR multiplier.
        """
        risk_amount = current_balance * self.risk_per_trade_pct
        
        sl_distance = max(atr * self.atr_mult, entry_price * 0.008) # Min 0.8% SL
        
        if signal_type == 1: # LONG
            if ema50 is not None and ema50 < entry_price:
                # Place SL slightly below EMA 50 for extra buffer against market noise
                stop_loss = min(entry_price - sl_distance, ema50 * 0.996)
                sl_distance = entry_price - stop_loss
            else:
                stop_loss = entry_price - sl_distance
            take_profit = entry_price + (sl_distance * self.rr_ratio)
        else: # SHORT
            if ema50 is not None and ema50 > entry_price:
                stop_loss = max(entry_price + sl_distance, ema50 * 1.004)
                sl_distance = stop_loss - entry_price
            else:
                stop_loss = entry_price + sl_distance
            take_profit = entry_price - (sl_distance * self.rr_ratio)
            
        position_size_asset = risk_amount / sl_distance
        position_size_usd = position_size_asset * entry_price

        # Cap max exposure to 35% of total capital (or configured max_alloc) to prevent gap crash overexposure
        max_alloc_pct = float(self.config.get("max_position_alloc_pct", 0.35))
        position_size_usd = min(position_size_usd, current_balance * max_alloc_pct)
        position_size_asset = position_size_usd / entry_price

        return {
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "sl_distance": float(sl_distance),
            "risk_amount_usd": float(risk_amount),
            "position_size_asset": float(position_size_asset),
            "position_size_usd": float(position_size_usd)
        }

    def update_trailing_stop(self, current_price: float, entry_price: float, current_sl: float, signal_type: int, sl_distance: float):
        """
        Break-Even Trailing Stop Loss:
        Moves SL to Entry + Buffer ONLY when price has covered 1x Risk in profit.
        Does NOT trail tightly to allow trades to reach full Take Profit target.
        """
        if not self.trailing_stop_enabled:
            return current_sl

        buffer = sl_distance * 0.1
        
        if signal_type == 1: # LONG
            # Move to Break-Even if price >= Entry + 1.0x Risk
            if current_price >= entry_price + sl_distance:
                be_sl = entry_price + buffer
                return max(current_sl, be_sl)
        elif signal_type == -1: # SHORT
            if current_price <= entry_price - sl_distance:
                be_sl = entry_price - buffer
                return min(current_sl, be_sl)
                
        return current_sl
