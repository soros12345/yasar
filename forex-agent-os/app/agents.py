from .models import AgentSignal, MarketSnapshot, Side, TradeIntent


class TrendAgent:
    name = "trend"

    def analyze(self, m: MarketSnapshot) -> AgentSignal:
        if m.ema_fast > m.ema_slow and m.rsi >= 52:
            return AgentSignal(agent=self.name, side=Side.BUY, confidence=min(0.9, 0.6 + (m.rsi - 50) / 100), reason="EMA trend bullish")
        if m.ema_fast < m.ema_slow and m.rsi <= 48:
            return AgentSignal(agent=self.name, side=Side.SELL, confidence=min(0.9, 0.6 + (50 - m.rsi) / 100), reason="EMA trend bearish")
        return AgentSignal(agent=self.name, side=Side.HOLD, confidence=0.5, reason="No clear EMA trend")


class MeanReversionAgent:
    name = "mean_reversion"

    def analyze(self, m: MarketSnapshot) -> AgentSignal:
        if m.rsi <= 30:
            return AgentSignal(agent=self.name, side=Side.BUY, confidence=0.72, reason="RSI oversold")
        if m.rsi >= 70:
            return AgentSignal(agent=self.name, side=Side.SELL, confidence=0.72, reason="RSI overbought")
        return AgentSignal(agent=self.name, side=Side.HOLD, confidence=0.45, reason="RSI neutral")


class EnsembleEngine:
    def __init__(self):
        self.agents = [TrendAgent(), MeanReversionAgent()]

    def decide(self, m: MarketSnapshot) -> tuple[list[AgentSignal], TradeIntent | None]:
        signals = [a.analyze(m) for a in self.agents]
        buy = sum(s.confidence for s in signals if s.side == Side.BUY)
        sell = sum(s.confidence for s in signals if s.side == Side.SELL)
        if max(buy, sell) < 0.65:
            return signals, None

        side = Side.BUY if buy > sell else Side.SELL
        confidence = min(0.95, max(buy, sell) / max(1, len(self.agents)))
        entry = m.ask if side == Side.BUY else m.bid
        sl_distance = 1.5 * m.atr
        tp_distance = 2.5 * m.atr
        stop_loss = entry - sl_distance if side == Side.BUY else entry + sl_distance
        take_profit = entry + tp_distance if side == Side.BUY else entry - tp_distance
        return signals, TradeIntent(symbol=m.symbol, side=side, confidence=confidence, entry=entry, stop_loss=stop_loss, take_profit=take_profit)
