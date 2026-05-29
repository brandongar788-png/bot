from binance.client import Client
import config
from indicadores import calcular_rsi, calcular_ema, calcular_score_entrada
from regimen import DetectorRegimen
from market_data import obtener_contexto_completo

c = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
c.timestamp_offset = c.get_server_time()['serverTime'] - __import__('time').time().__int__() * 1000

velas   = c.get_klines(symbol='BTCUSDT', interval='15m', limit=100)
velas5m = c.get_klines(symbol='BTCUSDT', interval='5m',  limit=100)
velas1h = c.get_klines(symbol='BTCUSDT', interval='1h',  limit=100)

c15 = [float(v[4]) for v in velas]
h15 = [float(v[2]) for v in velas]
l15 = [float(v[3]) for v in velas]
v15 = [float(v[5]) for v in velas]
c5  = [float(v[4]) for v in velas5m]
c1h = [float(v[4]) for v in velas1h]

rsi   = calcular_rsi(c15)
ema9  = calcular_ema(c15, 9)
ema21 = calcular_ema(c15, 21)
score, detalles, _ = calcular_score_entrada(c15, v15, h15, l15)

detector = DetectorRegimen()
regimen  = detector.analizar(c5, c15, c1h)

contexto = obtener_contexto_completo()

print("=" * 50)
print("DIAGNÓSTICO DEL BOT")
print("=" * 50)
print(f"RSI actual        : {rsi}")
print(f"EMA9 / EMA21      : {ema9} / {ema21}")
print(f"Score actual      : {score}/100")
print(f"Régimen mercado   : {regimen['regimen']}")
print(f"Score mínimo hoy  : {regimen['score_minimo']}")
print(f"RSI máximo hoy    : {regimen['rsi_compra']}")
print(f"Fear & Greed      : {contexto['fear_greed_valor']} ({contexto['fear_greed_texto']})")
print(f"Señal mercado     : {contexto['señal_mercado']}")
print(f"Puede operar      : {regimen['operar']}")
print("-" * 50)
print("Detalle del score:")
for k, v in detalles.items():
    print(f"  {k}: {v}")
print("=" * 50)
print("¿POR QUÉ NO ENTRA?")
if score < regimen['score_minimo']:
    print(f"  Score {score} < mínimo {regimen['score_minimo']}")
if rsi > regimen['rsi_compra']:
    print(f"  RSI {rsi} > máximo permitido {regimen['rsi_compra']}")
if not regimen['operar']:
    print(f"  Régimen {regimen['regimen']} no permite operar")
if contexto['señal_mercado'] == 'VENDER':
    print(f"  Fear&Greed dice no operar")
print("=" * 50)
