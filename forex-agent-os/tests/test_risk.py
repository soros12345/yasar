from app.models import AccountState, MarketSnapshot, Side, TradeIntent
from app.risk import RiskEngine


def market():
    return MarketSnapshot(symbol="EURUSD", bid=1.1000, ask=1.1001, atr=0.0010, ema_fast=1.1010, ema_slow=1.0990, rsi=58, volatility_pct=0.5)


def account():
    return AccountState(balance=10000, equity=10000, daily_pnl=0, peak_equity=10000, open_positions=0)


def intent(confidence=0.8):
    return TradeIntent(symbol="EURUSD", side=Side.BUY, confidence=confidence, entry=1.1001, stop_loss=1.0986, take_profit=1.1026)


def test_approves_normal_trade():
    assert RiskEngine().evaluate(intent(), market(), account()).approved


def test_rejects_low_confidence():
    assert RiskEngine().evaluate(intent(0.5), market(), account()).reason == "low_confidence"


def test_kill_switch_blocks_trade():
    engine = RiskEngine()
    engine.kill_switch = True
    assert engine.evaluate(intent(), market(), account()).reason == "kill_switch"


def test_daily_loss_limit_blocks_trade():
    a = account()
    a.daily_pnl = -250
    assert RiskEngine().evaluate(intent(), market(), a).reason == "daily_loss_limit"
