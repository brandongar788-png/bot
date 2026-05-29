# ============================================================
#   BOT DE TRADING — DETECTOR DE RÉGIMEN DE MERCADO
#   regimen.py
#   Identifica si el mercado está en tendencia o lateral
#   y ajusta la estrategia automáticamente
# ============================================================

from indicadores import calcular_ema, calcular_atr

REGIMENES = {
    "ALCISTA_FUERTE": {
        "descripcion"    : "Tendencia alcista confirmada en todos los timeframes",
        "rsi_compra"     : 62,    # Más permisivo — captura tendencias fuertes
        "score_minimo"   : 40,    # Bajo para entrar en tendencias claras
        "capital_pct"    : 0.25,  # 25% del capital = $250 por operación
        "emoji"          : "🚀",
    },
    "ALCISTA": {
        "descripcion"    : "Tendencia alcista moderada",
        "rsi_compra"     : 55,    # Permisivo en tendencia moderada
        "score_minimo"   : 45,
        "capital_pct"    : 0.20,  # 20% del capital = $200 por operación
        "emoji"          : "📈",
    },
    "LATERAL": {
        "descripcion"    : "Mercado sin dirección clara— modo scalping activo",
        "rsi_compra"     : 45,    # Solo entrar en rebotes bajos
        "score_minimo"   : 50,    # Umbral moderado
        "capital_pct"    : 0.12,  # 12% del capital = $120 por operación (conservador)
        "emoji"          : "➡️",
    },
    "BAJISTA": {
        "descripcion"    : "Tendencia bajista — operar con cautela",
        "rsi_compra"     : 45,
        "score_minimo"   : 55,
        "capital_pct"    : 0.08,
        "emoji"          : "📉",
    },
    "BAJISTA_FUERTE": {
        "descripcion"    : "Caída fuerte — operar mínimo",
        "rsi_compra"     : 35,
        "score_minimo"   : 50,
        "capital_pct"    : 0.05,
        "emoji"          : "🛑",
    },
}


class DetectorRegimen:

    def __init__(self):
        self.regimen_actual = "LATERAL"
        self.ultimo_cambio  = None

    def analizar(self, precios_5m, precios_15m, precios_1h) -> dict:
        """
        Analiza 3 timeframes y determina el régimen actual.
        Cuantos más timeframes estén alineados, más fuerte la señal.
        """
        puntos = 0

        # ── Timeframe 1h (tendencia principal) ──
        if len(precios_1h) >= 21:
            ema9  = calcular_ema(precios_1h, 9)
            ema21 = calcular_ema(precios_1h, 21)
            if ema9 > ema21:
                puntos += 3   # Más peso al timeframe mayor
            else:
                puntos -= 3

        # ── Timeframe 15m (tendencia intermedia) ──
        if len(precios_15m) >= 21:
            ema9  = calcular_ema(precios_15m, 9)
            ema21 = calcular_ema(precios_15m, 21)
            if ema9 > ema21:
                puntos += 2
            else:
                puntos -= 2

        # ── Timeframe 5m (timing) ──
        if len(precios_5m) >= 21:
            ema9  = calcular_ema(precios_5m, 9)
            ema21 = calcular_ema(precios_5m, 21)
            if ema9 > ema21:
                puntos += 1
            else:
                puntos -= 1

        # ── Determinar régimen según puntos ──
        if puntos >= 5:
            regimen = "ALCISTA_FUERTE"
        elif puntos >= 2:
            regimen = "ALCISTA"
        elif puntos >= -1:
            regimen = "LATERAL"
        elif puntos >= -4:
            regimen = "BAJISTA"
        else:
            regimen = "BAJISTA_FUERTE"

        self.regimen_actual = regimen
        info = REGIMENES[regimen]

        print(f"[Régimen] {info['emoji']} {regimen} (puntos: {puntos}) — {info['descripcion']}")
        return {
            "regimen"      : regimen,
            "puntos"       : puntos,
            "rsi_compra"   : info["rsi_compra"],
            "score_minimo" : info["score_minimo"],
            "capital_pct"  : info["capital_pct"],
            "operar"       : info["capital_pct"] > 0,
            "emoji"        : info["emoji"],
        }
