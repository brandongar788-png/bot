# ============================================================
#   BOT DE TRADING — MOTOR DE INDICADORES TÉCNICOS
#   indicadores.py
#   Calcula todos los indicadores sin depender de IA
# ============================================================

import math

def calcular_ema(precios, periodo):
    if len(precios) < periodo:
        return 0.0
    k = 2 / (periodo + 1)
    ema = sum(precios[:periodo]) / periodo
    for p in precios[periodo:]:
        ema = p * k + ema * (1 - k)
    return round(ema, 2)

def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1:
        return 50.0
    cambios = [precios[i] - precios[i-1] for i in range(1, len(precios))]
    ganancias = [c if c > 0 else 0 for c in cambios[-periodo:]]
    perdidas  = [-c if c < 0 else 0 for c in cambios[-periodo:]]
    avg_g = sum(ganancias) / periodo
    avg_p = sum(perdidas) / periodo
    if avg_p == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_p)), 1)

def calcular_macd(precios):
    if len(precios) < 26:
        return 0.0, 0.0, 0.0
    ema12 = calcular_ema(precios, 12)
    ema26 = calcular_ema(precios, 26)
    macd  = ema12 - ema26
    # Señal = EMA 9 del MACD (simplificado)
    señal = macd * 0.2 + macd * 0.8
    histograma = macd - señal
    return round(macd, 2), round(señal, 2), round(histograma, 2)

def calcular_bollinger(precios, periodo=20):
    if len(precios) < periodo:
        return 0.0, 0.0, 0.0
    ultimos = precios[-periodo:]
    media   = sum(ultimos) / periodo
    varianza = sum((p - media) ** 2 for p in ultimos) / periodo
    desv    = math.sqrt(varianza)
    banda_sup = round(media + 2 * desv, 2)
    banda_inf = round(media - 2 * desv, 2)
    return round(media, 2), banda_sup, banda_inf

def calcular_atr(velas_high, velas_low, velas_close, periodo=14):
    if len(velas_close) < periodo + 1:
        return 0.0
    trs = []
    for i in range(1, len(velas_close)):
        tr = max(
            velas_high[i] - velas_low[i],
            abs(velas_high[i] - velas_close[i-1]),
            abs(velas_low[i] - velas_close[i-1])
        )
        trs.append(tr)
    return round(sum(trs[-periodo:]) / periodo, 2)

def calcular_volumen_relativo(volumenes, periodo=20):
    if len(volumenes) < periodo:
        return 1.0
    promedio = sum(volumenes[-periodo:]) / periodo
    actual   = volumenes[-1]
    if promedio == 0:
        return 1.0
    return round(actual / promedio, 2)

def detectar_patron_velas(abre, alto, bajo, cierre):
    """Detecta patrones básicos de velas japonesas."""
    cuerpo   = abs(cierre - abre)
    rango    = alto - bajo
    if rango == 0:
        return "NEUTRAL"

    # Martillo — posible rebote alcista
    if cierre > abre and (abre - bajo) > cuerpo * 2 and (alto - cierre) < cuerpo * 0.5:
        return "MARTILLO"

    # Estrella fugaz — posible caída
    if abre > cierre and (alto - abre) > cuerpo * 2 and (cierre - bajo) < cuerpo * 0.5:
        return "ESTRELLA_FUGAZ"

    # Vela alcista fuerte
    if cierre > abre and cuerpo > rango * 0.7:
        return "ALCISTA_FUERTE"

    # Vela bajista fuerte
    if abre > cierre and cuerpo > rango * 0.7:
        return "BAJISTA_FUERTE"

    # Doji — indecisión
    if cuerpo < rango * 0.1:
        return "DOJI"

    return "NEUTRAL"

def detectar_soporte_resistencia(precios, ventana=20):
    """Detecta niveles clave de soporte y resistencia."""
    if len(precios) < ventana:
        return 0.0, 0.0
    ultimos = precios[-ventana:]
    soporte     = min(ultimos)
    resistencia = max(ultimos)
    return round(soporte, 2), round(resistencia, 2)

def calcular_score_entrada(precios, volumenes, velas_high, velas_low):
    """
    Sistema de puntuación 0-100.
    Cada indicador aporta puntos. Si llega a 60 entra.
    No depende de IA para decidir.
    """
    score = 0
    detalles = {}

    precio_actual = precios[-1]

    # ── RSI (20 puntos) ──
    rsi = calcular_rsi(precios)
    if rsi < 30:
        score += 20
        detalles["RSI"] = f"Sobreventa extrema ({rsi}) +20"
    elif rsi < 45:
        score += 12
        detalles["RSI"] = f"Zona de compra ({rsi}) +12"
    elif rsi < 55:
        score += 5
        detalles["RSI"] = f"Neutral ({rsi}) +5"
    else:
        detalles["RSI"] = f"Sobrecompra ({rsi}) +0"

    # ── MACD (20 puntos) ──
    macd, señal, histograma = calcular_macd(precios)
    if histograma > 0 and macd > señal:
        score += 20
        detalles["MACD"] = f"Cruce alcista +20"
    elif histograma > 0:
        score += 10
        detalles["MACD"] = f"Momentum positivo +10"
    else:
        detalles["MACD"] = f"Momentum negativo +0"

    # ── Bollinger (20 puntos) ──
    media, banda_sup, banda_inf = calcular_bollinger(precios)
    if precio_actual <= banda_inf:
        score += 20
        detalles["BOLLINGER"] = f"Precio en banda inferior +20"
    elif precio_actual <= media:
        score += 10
        detalles["BOLLINGER"] = f"Precio bajo la media +10"
    else:
        detalles["BOLLINGER"] = f"Precio en zona alta +0"

    # ── Volumen (20 puntos) ──
    vol_rel = calcular_volumen_relativo(volumenes)
    if vol_rel > 1.5:
        score += 20
        detalles["VOLUMEN"] = f"Volumen alto x{vol_rel} +20"
    elif vol_rel > 1.0:
        score += 10
        detalles["VOLUMEN"] = f"Volumen normal x{vol_rel} +10"
    else:
        detalles["VOLUMEN"] = f"Volumen bajo x{vol_rel} +0"

    # ── Soporte/Resistencia (20 puntos) ──
    soporte, resistencia = detectar_soporte_resistencia(precios)
    distancia_soporte = abs(precio_actual - soporte) / precio_actual * 100
    if distancia_soporte < 0.3:
        score += 20
        detalles["SOPORTE"] = f"Precio en soporte ${soporte} +20"
    elif distancia_soporte < 1.0:
        score += 10
        detalles["SOPORTE"] = f"Cerca del soporte +10"
    else:
        detalles["SOPORTE"] = f"Lejos del soporte +0"

    return score, detalles, {
        "rsi": rsi,
        "macd": macd,
        "señal_macd": señal,
        "histograma": histograma,
        "banda_sup": banda_sup,
        "banda_inf": banda_inf,
        "media_bb": media,
        "volumen_relativo": vol_rel,
        "soporte": soporte,
        "resistencia": resistencia,
        "atr": calcular_atr(velas_high, velas_low, precios),
    }
