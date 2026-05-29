# ============================================================
#   BOT DE TRADING — CONFIGURACIÓN CENTRAL
#   Archivo: config.py
#   ⚠️  EDITA ESTE ARCHIVO CON TUS DATOS ANTES DE INICIAR
# ============================================================

# ════════════════════════════════════════════
# 🔑 APIs — DEBES RELLENAR ESTOS VALORES
# ════════════════════════════════════════════

# ── Binance (para operar) ──
BINANCE_API_KEY    = "quh4HQdviitFPhL2EYDF4zQdLpf2J8G8tEpjz4NxxI4Se95bR27jsIoi13lQ0KbH"
BINANCE_API_SECRET = "P9c3z4sYuWCXpcXj1TiwFe0lfoaOOM6snmIUOh1kJgK0lcA6LnpC0tUpjI2jPGTF"

# ── OpenAI (para el análisis con IA) ──
GROQ_API_KEY       = "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"

# ── Email (para recibir reportes) ──
EMAIL_REMITENTE    = "ariasbrandon442@gmail.com"
EMAIL_CONTRASENA   = "vvecdyqkypjagols"
EMAIL_DESTINATARIO = "ariasbrandon442@gmail.com"

# ════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN DEL BOT
# ════════════════════════════════════════════

# -- Modo de operacion --
# "SIMULACION" = solo en tu PC, no envia ordenes a Binance
# "DEMO"       = envia ordenes a la Testnet de Binance (dinero ficticio, visible en la app)
# "REAL"       = opera con dinero real en Binance
MODO = "SIMULACION"

# -- Binance Testnet (cuenta demo) --
# Para obtener tus claves de Testnet, ve a: https://testnet.binance.vision/
# Crea una cuenta y genera tus API Keys alli
BINANCE_TESTNET_API_KEY    = ""   # <-- Pega aqui tu API Key de Testnet
BINANCE_TESTNET_API_SECRET = ""   # <-- Pega aqui tu API Secret de Testnet

# ── Par y mercado ──
PAR          = "BTCUSDT"          # Par a operar
INTERVALO    = "15m"              # Velas de 15 minutos
CAPITAL_USDT = 1000.0             # Capital total disponible en USDT (demo: $1000 para lograr meta de $30/día)

# ── Gestión de riesgo ──
STOP_LOSS_PCT    = 0.8            # Stop loss en % — MUY AJUSTADO para minimizar pérdidas
TAKE_PROFIT_PCT  = 2.0            # Take profit en % — Objetivo realista y alcanzable
MAX_TRADES_DIA   = 15             # Máximo de trades por día — Más operaciones = más oportunidades
META_GANANCIA_DIA = 30.0         # Meta diaria en USDT ($30/día con capital de $1000)
TIMEOUT_TRADE_MINUTOS = 90       # Tiempo máximo de trade en minutos (1.5 horas — más ágil)

# ── Indicadores técnicos (los ajusta la estrategia activa automáticamente) ──
EMA_RAPIDA   = 9
EMA_LENTA    = 21
RSI_COMPRA   = 45
RSI_VENTA    = 65

# ── Ciclo del bot ──
SEGUNDOS_CICLO = 30              # Cada cuántos segundos revisa el mercado

# ════════════════════════════════════════════
# 📊 UMBRALES DE DECISIÓN
# ════════════════════════════════════════════

SCORE_MINIMO_ENTRADA = 50        # Score mínimo de gráfico para entrar — Permite más entradas de calidad
CONFIANZA_SENTIMIENTO_MINIMA = 40  # Confianza mínima del análisis de noticias

# ════════════════════════════════════════════
# 🧠 CONFIGURACIÓN DE IA HÍBRIDA
# ════════════════════════════════════════════
TRADES_MINIMOS_PARA_IA   = 50      # Trades reales antes de activar LSTM y XGBoost
USAR_IA_HIBRIDA          = True    # Activar IA híbrida después del bootstrap
UMBRAL_PROBABILIDAD_XGB  = 0.60    # XGBoost debe superar este umbral
UMBRAL_LSTM              = 0.52    # LSTM debe superar este umbral
PESOS_DECISION = {                 # Pesos de cada capa en la decisión final
    "score_tecnico" : 0.40,
    "xgboost"       : 0.35,
    "lstm"          : 0.25,
}

