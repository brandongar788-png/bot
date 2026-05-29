# ============================================================
#   BOT DE TRADING — DATOS DE MERCADO
#   market_data.py
#   APIs oficiales gratuitas sin Selenium
# ============================================================

import urllib.request
import json
from datetime import datetime

def obtener_fear_greed():
    """
    Fear & Greed Index de CoinGecko.
    0-25 = Miedo extremo (bueno para comprar)
    75-100 = Codicia extrema (bueno para vender)
    """
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            datos = json.loads(r.read())
        valor = int(datos["data"][0]["value"])
        clasificacion = datos["data"][0]["value_classification"]
        print(f"[MarketData] Fear & Greed: {valor} ({clasificacion})")
        return valor, clasificacion
    except Exception as e:
        print(f"[MarketData] Fear & Greed no disponible: {e}")
        return 50, "Neutral"

def obtener_datos_coingecko():
    """
    Datos de mercado de Bitcoin desde CoinGecko (gratis, sin API key).
    """
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            datos = json.loads(r.read())
        btc = datos["bitcoin"]
        return {
            "precio"         : btc["usd"],
            "cambio_24h"     : round(btc["usd_24h_change"], 2),
            "volumen_24h"    : btc["usd_24h_vol"],
            "market_cap"     : btc["usd_market_cap"],
        }
    except Exception as e:
        print(f"[MarketData] CoinGecko no disponible: {e}")
        return {}

def obtener_regimen_mercado(precios_1h, precios_4h):
    """
    Detecta si el mercado está en tendencia alcista, bajista o lateral.
    Compara EMAs de diferentes timeframes.
    """
    if len(precios_1h) < 21 or len(precios_4h) < 21:
        return "LATERAL"

    from indicadores import calcular_ema
    ema9_1h  = calcular_ema(precios_1h, 9)
    ema21_1h = calcular_ema(precios_1h, 21)
    ema9_4h  = calcular_ema(precios_4h, 9)
    ema21_4h = calcular_ema(precios_4h, 21)

    alcista_1h = ema9_1h > ema21_1h
    alcista_4h = ema9_4h > ema21_4h

    if alcista_1h and alcista_4h:
        return "ALCISTA"
    elif not alcista_1h and not alcista_4h:
        return "BAJISTA"
    else:
        return "LATERAL"

def obtener_contexto_completo():
    """
    Recopila todo el contexto de mercado de una vez.
    Sin Selenium, sin scraping, solo APIs oficiales.
    """
    fear_valor, fear_texto = obtener_fear_greed()
    coingecko = obtener_datos_coingecko()

    contexto = {
        "fear_greed_valor"  : fear_valor,
        "fear_greed_texto"  : fear_texto,
        "cambio_24h"        : coingecko.get("cambio_24h", 0),
        "volumen_24h"       : coingecko.get("volumen_24h", 0),
        "hora_analisis"     : datetime.now().strftime("%H:%M"),
    }

    # Interpretar Fear & Greed para el bot
    if fear_valor <= 25:
        contexto["señal_mercado"] = "COMPRAR"
        contexto["multiplicador"] = 1.3
    elif fear_valor <= 45:
        contexto["señal_mercado"] = "NEUTRO_POSITIVO"
        contexto["multiplicador"] = 1.1
    elif fear_valor <= 55:
        contexto["señal_mercado"] = "NEUTRO"
        contexto["multiplicador"] = 1.0
    elif fear_valor <= 75:
        contexto["señal_mercado"] = "NEUTRO_NEGATIVO"
        contexto["multiplicador"] = 0.8
    else:
        contexto["señal_mercado"] = "VENDER"
        contexto["multiplicador"] = 0.0  # No operar

    print(f"[MarketData] Contexto: {contexto['señal_mercado']} | Cambio 24h: {contexto['cambio_24h']}%")
    return contexto
