# ============================================================
#   BOT DE TRADING — ARCHIVO PRINCIPAL V2
#   main.py — Versión reestructurada y autónoma
# ============================================================

import time
import sys
import json
import os
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

import config
from historial        import guardar_trade, leer_del_dia, leer_estadisticas
from trailing_stop    import TrailingStop
from estrategias_db   import BibliotecaEstrategias
from email_bot        import enviar_email, enviar_alerta
from indicadores      import calcular_ema, calcular_rsi, calcular_score_entrada, detectar_patron_velas
from market_data      import obtener_contexto_completo
from regimen          import DetectorRegimen
from gestor_riesgo    import GestorRiesgo
from ia_manager        import GestorIA
from ml_dl_hybrid     import HybridBrain
from preparar_datos   import preparar_y_entrenar_todo
from optimizador     import EvolucionadorGenetico


# ════════════════════════════════════════════
# INICIALIZACIÓN
# ════════════════════════════════════════════

print("=" * 60)
print("  BOT DE TRADING BTC/USDT — V2 AUTÓNOMO")
print(f"  Modo: {config.MODO}")
print(f"  Par: {config.PAR} | Capital: ${config.CAPITAL_USDT} USDT")
print("=" * 60)

try:
    if config.MODO == "DEMO":
        # Conectar a la Testnet de Binance (cuenta demo)
        cliente = Client(
            config.BINANCE_TESTNET_API_KEY,
            config.BINANCE_TESTNET_API_SECRET,
            testnet=True
        )
        print(f"[Main] OK - Conectado a Binance TESTNET (Demo)")
        # Para precios reales, usamos un segundo cliente sin testnet
        cliente_precios = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
        cliente_precios.timestamp_offset = cliente_precios.get_server_time()['serverTime'] - int(time.time() * 1000)
        precio_test = cliente_precios.get_symbol_ticker(symbol=config.PAR)
        print(f"[Main] OK - Precios en vivo de Binance | BTC: ${float(precio_test['price']):,.2f}")
    else:
        cliente = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
        cliente.timestamp_offset = cliente.get_server_time()['serverTime'] - int(time.time() * 1000)
        cliente_precios = cliente  # En modo REAL o SIMULACION, es el mismo cliente
        precio_test = cliente.get_symbol_ticker(symbol=config.PAR)
        print(f"[Main] OK - Binance conectado | BTC: ${float(precio_test['price']):,.2f}")
except Exception as e:
    print(f"[Main] ERROR - Error Binance: {e}")
    sys.exit(1)

# Módulos
estrategias  = BibliotecaEstrategias()
detector     = DetectorRegimen()
riesgo       = GestorRiesgo()
ia_filtro    = GestorIA()
hora_inicio  = datetime.now()

# Cerebro de IA Híbrido local (ML + DL)
cerebro_ia = None

# ── Modo Bootstrap — desactiva IA hasta tener datos reales ──
stats_actuales = leer_estadisticas()
total_trades   = stats_actuales.get("total_trades", 0)

if total_trades < config.TRADES_MINIMOS_PARA_IA:
    usar_ia = False
    print(f"[Main] 🔄 Bootstrap {total_trades}/{config.TRADES_MINIMOS_PARA_IA} — acumulando datos reales, IA desactivada")
else:
    usar_ia = config.USAR_IA_HIBRIDA
    if total_trades == config.TRADES_MINIMOS_PARA_IA:
        print(f"[Main] 🧠 ¡IA activada! Ya tienes {total_trades} trades reales de entrenamiento")

if usar_ia:
    print("[Main] IA Hibrida - Inicializando Cerebro de IA Hibrido (XGBoost + LSTM PyTorch CPU)...")
    cerebro_ia = HybridBrain()
    try:
        # Pre-entrenar de manera autónoma con datos históricos reales/sintéticos
        preparar_y_entrenar_todo(cerebro_ia)
    except Exception as ex:
        print(f"[Main] AVISO: No se pudo realizar el pre-entrenamiento inicial de la IA: {ex}")



# Estado del trade
trade_abierto  = False
trailing_stop  = None
precio_entrada = 0.0
capital_en_uso = 0.0
fecha_entrada  = ""
trades_hoy     = 0
trades_cerrados_total = 0   # Contador global para disparar evolucion genetica
contexto       = {}
regimen_info   = {}
trade_info     = {}         # Variables extra de entrada (para guardar luego)

# Contexto de mercado — se actualiza cada 2 horas
ultima_actualizacion_contexto = None


# ════════════════════════════════════════════
# FUNCIONES DE MERCADO
# ════════════════════════════════════════════

def obtener_velas_timeframe(intervalo: str, limite: int = 100):
    """Obtiene velas de cualquier timeframe."""
    try:
        velas = cliente.get_klines(symbol=config.PAR, interval=intervalo, limit=limite)
        cierres = [float(v[4]) for v in velas]
        altos   = [float(v[2]) for v in velas]
        bajos   = [float(v[3]) for v in velas]
        volumes = [float(v[5]) for v in velas]
        abre    = [float(v[1]) for v in velas]
        return cierres, altos, bajos, volumes, abre
    except Exception as e:
        print(f"[Main] ⚠️ Error velas {intervalo}: {e}")
        return [], [], [], [], []

def obtener_precio() -> float:
    try:
        return float(cliente.get_symbol_ticker(symbol=config.PAR)["price"])
    except:
        return 0.0

def obtener_imbalance_libro(cliente, par: str) -> float:
    """
    Calcula el ratio entre el volumen de órdenes de compra (bids)
    y órdenes de venta (asks) activas en Binance.
    > 1.5 = fuerte presión de compra
    < 0.6 = fuerte presión de venta
    """
    try:
        book = cliente.get_order_book(symbol=par, limit=20)
        bids_vol = sum(float(b[1]) for b in book["bids"])
        asks_vol = sum(float(a[1]) for a in book["asks"])
        if asks_vol == 0:
            return 1.0
        return round(bids_vol / asks_vol, 2)
    except Exception as e:
        print(f"[Main] ⚠️ Error al obtener libro de órdenes: {e}")
        return 1.0

def detectar_ballenas(cliente, par: str) -> dict:
    """
    Escanea las transacciones de mercado recientes (últimos 100 trades).
    Filtra trades de gran tamaño (> $35,000 USD) para ver si las ballenas
    están acumulando (compras taker) o distribuyendo (ventas taker).
    """
    try:
        trades = cliente.get_recent_trades(symbol=par, limit=100)
        compras_grandes = 0.0
        ventas_grandes = 0.0
        umbral_usdt = 35000.0  # ~0.5 BTC. Detecta actividad institucional rápida
        
        for t in trades:
            qty = float(t["qty"])
            price = float(t["price"])
            valor_usdt = qty * price
            
            if valor_usdt >= umbral_usdt:
                # isBuyerMaker: False significa que el tomador (taker) es el comprador -> COMPRA de mercado
                if t.get("isBuyerMaker") == False:
                    compras_grandes += valor_usdt
                else:
                    ventas_grandes += valor_usdt
        
        neto = compras_grandes - ventas_grandes
        return {
            "compras": round(compras_grandes, 2),
            "ventas": round(ventas_grandes, 2),
            "neto": round(neto, 2)
        }
    except Exception as e:
        print(f"[Main] ⚠️ Error en detector de ballenas: {e}")
        return {"compras": 0.0, "ventas": 0.0, "neto": 0.0}

def guardar_estado(precio_actual, ema9, ema21, rsi, score, regimen):
    """Guarda estado para el panel web."""
    try:
        stats = leer_estadisticas()
        estado = {
            "hora"           : datetime.now().strftime("%H:%M:%S"),
            "fecha"          : datetime.now().strftime("%d/%m/%Y"),
            "precio"         : precio_actual,
            "ema_rapida"     : round(ema9, 0),
            "ema_lenta"      : round(ema21, 0),
            "rsi"            : rsi,
            "score"          : score,
            "regimen"        : regimen,
            "trade_abierto"  : trade_abierto,
            "trades_hoy"     : trades_hoy,
            "modo"           : config.MODO,
            "precio_entrada" : precio_entrada if trade_abierto else 0,
            "sl_actual"      : round(trailing_stop.sl_actual, 2) if trailing_stop else 0,
            "tp_actual"      : round(trailing_stop.tp_actual, 2) if trailing_stop else 0,
            "ganancia_actual": round(capital_en_uso * (precio_actual - precio_entrada) / precio_entrada, 2) if trade_abierto and precio_entrada > 0 else 0,
            "fear_greed"     : contexto.get("fear_greed_valor", 50),
            "fear_texto"     : contexto.get("fear_greed_texto", ""),
            "cambio_24h"     : contexto.get("cambio_24h", 0),
            "stats"          : stats,
        }
        os.makedirs("data", exist_ok=True)
        with open("data/estado.json", "w") as f:
            json.dump(estado, f)
    except Exception:
        pass


def filtrar_con_ia(precios_cierre: list, volumenes: list, regimen: str, score: int, imbalance: float, ballenas_neto: float, fear_greed: int) -> bool:
    """
    Usa Llama 3.3 en Groq para validar una señal de entrada.
    Retorna True si la IA aprueba comprar, o si falla/da timeout para no bloquear la operación.
    """
    try:
        # Formatear últimos 10 precios y volúmenes
        ultimos_precios = [f"${p:,.2f}" for p in precios_cierre[-10:]]
        ultimos_vols = [f"{v:.2f}" for v in volumenes[-10:]]
        
        prompt = f"""
        Analiza las condiciones de BTC/USDT (15m) y determina si es una entrada LONG de alta probabilidad.
        
        DATOS ACTUALES:
        - Últimos 10 precios de cierre: {', '.join(ultimos_precios)}
        - Últimos 10 volúmenes: {', '.join(ultimos_vols)}
        - Régimen de Mercado: {regimen}
        - Score Técnico General: {score}/100
        - Imbalance del Libro (Bids/Asks): {imbalance:.2f}x
        - Volumen Neto de Ballenas (100 trades): {ballenas_neto:+.2f} USD
        - Fear & Greed Index: {fear_greed}
        
        Reglas de decisión:
        - Si el régimen es LATERAL y estamos en rebote de soporte, es aceptable si la estructura no es bajista.
        - Si la tendencia es alcista, busca continuación.
        - Si detectas sobrecompra extrema o debilidad en el volumen/imbalance, descarta.
        
        Responde estrictamente en formato JSON válido, sin explicaciones externas ni markdown de código, solo el objeto JSON:
        {{
          "decision": "COMPRAR" o "ESPERAR",
          "motivo": "Explicación breve del motivo de tu decisión en español"
        }}
        """
        
        sistema = "Eres un agente de trading cuantitativo de élite que solo aprueba operaciones con alta probabilidad de acierto y riesgo mínimo."
        
        print(f"[Main] 🤖 Consultando filtro de IA...")
        inicio_ia = time.time()
        respuesta_texto = ia_filtro.preguntar(prompt, sistema)
        print(f"[Main] 🤖 Respuesta de IA ({time.time() - inicio_ia:.1f}s): {respuesta_texto}")
        
        if not respuesta_texto:
            print("[Main] ⚠️ Respuesta de IA vacía o error de API. Procediendo con señal técnica (Fallback).")
            return True
            
        import re
        respuesta_limpia = respuesta_texto.strip()
        if "```json" in respuesta_limpia:
            respuesta_limpia = re.search(r"```json\s*(.*?)\s*```", respuesta_limpia, re.DOTALL).group(1)
        elif "```" in respuesta_limpia:
            respuesta_limpia = re.search(r"```\s*(.*?)\s*```", respuesta_limpia, re.DOTALL).group(1)
            
        data = json.loads(respuesta_limpia)
        decision = data.get("decision", "ESPERAR").upper()
        motivo = data.get("motivo", "Sin motivo especificado")
        
        print(f"[Main] 🤖 Decisión IA: {decision} | Motivo: {motivo}")
        return decision == "COMPRAR"
        
    except Exception as e:
        print(f"[Main] ⚠️ Error en filtro de IA: {e}. Procediendo con señal técnica (Fallback).")
        return True


def abrir_trade(precio: float, capital: float, sl_dinamico: float, tp_din_pct: float = None):
    global trade_abierto, trailing_stop, precio_entrada, capital_en_uso, fecha_entrada

    if config.MODO == "REAL":
        try:
            cantidad_btc = capital / precio
            cliente.order_market_buy(symbol=config.PAR, quantity=round(cantidad_btc, 5))
        except BinanceAPIException as e:
            print(f"[Main] ERROR - Error orden real: {e}")
            return
    elif config.MODO == "DEMO":
        try:
            cantidad_btc = capital / precio
            cliente.order_market_buy(symbol=config.PAR, quantity=round(cantidad_btc, 5))
            print(f"[Main] [DEMO] Orden de compra enviada a Testnet: {round(cantidad_btc, 5)} BTC a ${precio:,.2f}")
        except Exception as e:
            print(f"[Main] AVISO - Error Testnet (operacion registrada localmente): {e}")
    else:
        print(f"[Main] [SIMULACION] Comprando ${capital:.2f} a ${precio:,.2f}")

    precio_entrada = precio
    capital_en_uso = capital
    fecha_entrada  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trailing_stop  = TrailingStop(precio, capital, tp_pct=tp_din_pct)

    # Aplicar SL dinámico
    trailing_stop.sl_actual  = sl_dinamico
    trailing_stop.sl_inicial = sl_dinamico

    trade_abierto = True
    enviar_alerta("Trade abierto",
        f"Compra {'REAL' if config.MODO=='REAL' else 'SIMULADA'}: "
        f"${capital:.2f} a ${precio:,.2f} | SL: ${sl_dinamico:,.2f} | TP: {tp_din_pct if tp_din_pct else config.TAKE_PROFIT_PCT}%"
    )


def cerrar_trade(precio: float, motivo: str, ganancia_usd: float):
    global trade_abierto, trailing_stop, precio_entrada, capital_en_uso, trades_hoy, trades_cerrados_total

    if config.MODO == "REAL":
        try:
            cantidad_btc = capital_en_uso / precio_entrada
            cliente.order_market_sell(symbol=config.PAR, quantity=round(cantidad_btc, 5))
        except BinanceAPIException as e:
            print(f"[Main] ERROR - Error cierre real: {e}")
    elif config.MODO == "DEMO":
        try:
            cantidad_btc = capital_en_uso / precio_entrada
            cliente.order_market_sell(symbol=config.PAR, quantity=round(cantidad_btc, 5))
            print(f"[Main] [DEMO] Orden de venta enviada a Testnet: {round(cantidad_btc, 5)} BTC a ${precio:,.2f}")
        except Exception as e:
            print(f"[Main] AVISO - Error Testnet (operacion registrada localmente): {e}")

    signo = "+" if ganancia_usd >= 0 else ""
    print(f"[Main] [CERRADO] {motivo} | {signo}${ganancia_usd:.2f}")

    guardar_trade({
        "precio_entrada"  : precio_entrada,
        "precio_salida"   : precio,
        "ganancia"        : round(ganancia_usd, 2),
        "motivo_cierre"   : motivo,
        "capital_usado"   : capital_en_uso,
        "ema_rapida"      : str(config.EMA_RAPIDA),
        "ema_lenta"       : str(config.EMA_LENTA),
        "fecha_entrada"   : fecha_entrada,
        "hora_entrada"    : fecha_entrada[11:16] if len(fecha_entrada) >= 16 else "",
        "regimen"         : regimen_info.get("regimen", ""),
        "fear_greed"      : contexto.get("fear_greed_valor", 50),
        "rsi_entrada"     : trade_info.get("rsi", 0),
        "score_entrada"   : trade_info.get("score", 0),
        "prob_xgboost"    : trade_info.get("prob_xgb", 0),
        "prob_lstm"       : trade_info.get("prob_lstm", 0),
        "decision_final"  : trade_info.get("decision_final", 0),
        "patron_vela"     : trade_info.get("patron", ""),
        "volumen_relativo": trade_info.get("volumen_relativo", 1.0),
    })

    estrategias.registrar_trade(ganancia_usd)
    trade_abierto = False
    trailing_stop = None
    trades_hoy   += 1
    trades_cerrados_total += 1

    # Re-entrenamiento automatico despues de cerrar un trade para auto-aprendizaje continuo
    if usar_ia and cerebro_ia:
        try:
            print("[Main] IA Hibrida - Re-entrenando IA de manera continua con el nuevo trade cerrado...")
            preparar_y_entrenar_todo(cerebro_ia)
        except Exception as ex:
            print(f"[Main] AVISO: No se pudo re-entrenar la IA: {ex}")

    # Evolucion genetica cada 20 trades cerrados
    if trades_cerrados_total % 20 == 0 and trades_cerrados_total > 0:
        try:
            print(f"[Main] EVOLUCION GENETICA - Se alcanzaron {trades_cerrados_total} trades cerrados. Iniciando ciclo de mutacion...")
            nuevo_mutante = EvolucionadorGenetico.evolucionar_poblacion()
            if nuevo_mutante:
                print(f"[Main] EVOLUCION GENETICA - Nueva estrategia experimental patentada: {nuevo_mutante}")
            else:
                print(f"[Main] EVOLUCION GENETICA - Ciclo completado. Ningun mutante supero los filtros en esta generacion.")
        except Exception as ex:
            print(f"[Main] AVISO: Error en el ciclo de evolucion genetica: {ex}")



# ════════════════════════════════════════════
# LOOP PRINCIPAL
# ════════════════════════════════════════════

print(f"\n[Main] Bot V2 iniciado. Ciclo cada {config.SEGUNDOS_CICLO}s.\n")

while True:
    try:
        ahora  = datetime.now()
        hora   = ahora.hour
        minuto = ahora.minute

        # ── Actualizar contexto de mercado cada 2 horas ──
        if ultima_actualizacion_contexto is None or \
           (ahora - ultima_actualizacion_contexto).total_seconds() > 7200:
            print("[Main] Actualizando contexto de mercado...")
            contexto = obtener_contexto_completo()
            ultima_actualizacion_contexto = ahora

        # ── Obtener velas de 3 timeframes ──
        c15m, h15m, l15m, v15m, o15m = obtener_velas_timeframe("15m", 100)
        c5m,  h5m,  l5m,  v5m,  o5m  = obtener_velas_timeframe("5m",  100)
        c1h,  h1h,  l1h,  v1h,  o1h  = obtener_velas_timeframe("1h",  100)

        if not c15m:
            time.sleep(config.SEGUNDOS_CICLO)
            continue

        precio_actual = c15m[-1]

        # ── Calcular indicadores principales ──
        ema9  = calcular_ema(c15m, 9)
        ema21 = calcular_ema(c15m, 21)
        rsi   = calcular_rsi(c15m)

        # ── Detectar régimen de mercado (3 timeframes) ──
        regimen_info = detector.analizar(c5m, c15m, c1h)

        # ── Score de entrada (sistema propio sin IA) ──
        score, detalles, indicadores = calcular_score_entrada(c15m, v15m, h15m, l15m)

        # ── Libro de Órdenes y Ballenas (Factores en tiempo real) ──
        imbalance = obtener_imbalance_libro(cliente, config.PAR)
        indicadores["imbalance_libro"] = imbalance
        if imbalance >= 1.5:
            score += 15
            detalles["LIBRO_ORDENES"] = f"Presión de compra ({imbalance:.2f}x) +15"
        elif imbalance <= 0.6:
            score -= 15
            detalles["LIBRO_ORDENES"] = f"Presión de venta ({imbalance:.2f}x) -15"
        else:
            detalles["LIBRO_ORDENES"] = f"Libro balanceado ({imbalance:.2f}x) +0"

        ballenas = detectar_ballenas(cliente, config.PAR)
        indicadores["ballenas_neto"] = ballenas["neto"]
        if ballenas["neto"] > 0:
            score += 10
            detalles["BALLENAS"] = f"Compras ballena neto (+${ballenas['neto']:,.0f}) +10"
        elif ballenas["neto"] < 0:
            score -= 10
            detalles["BALLENAS"] = f"Ventas ballena neto (-${abs(ballenas['neto']):,.0f}) -10"
        else:
            detalles["BALLENAS"] = f"Sin movimientos de ballenas +0"

        # Asegurar límites del score entre 0 y 100
        score = max(0, min(100, score))

        # ── Patrón de vela actual ──
        patron = detectar_patron_velas(o15m[-1], h15m[-1], l15m[-1], c15m[-1])

        estado_trade_str = "TRADE ABIERTO" if trade_abierto else "Esperando"
        print(
            f"[{ahora.strftime('%H:%M:%S')}] "
            f"BTC: ${precio_actual:,.2f} | "
            f"RSI: {rsi:.1f} | "
            f"Score: {score}/100 | "
            f"Regimen: {regimen_info['regimen']} | "
            f"F&G: {contexto.get('fear_greed_valor', '?')} | "
            f"Estado: {estado_trade_str}"
        )

        # Guardar estado para panel web
        guardar_estado(precio_actual, ema9, ema21, rsi, score, regimen_info["regimen"])

        # ── Verificar pérdida máxima del día ──
        if riesgo.verificar_perdida_maxima_dia(config.CAPITAL_USDT):
            time.sleep(config.SEGUNDOS_CICLO)
            continue

        # ── Verificar meta de ganancia del día ──
        trades_dia = leer_del_dia()
        ganancia_hoy = sum(float(t.get("ganancia", 0)) for t in trades_dia)
        if ganancia_hoy >= config.META_GANANCIA_DIA:
            if not trade_abierto:
                print(f"[Main] 🏆 Meta diaria de ganancia alcanzada (${ganancia_hoy:.2f} >= ${config.META_GANANCIA_DIA:.2f}). Esperando al siguiente día...")
                time.sleep(config.SEGUNDOS_CICLO)
                continue

        # ── Gestión del trade abierto ──
        if trade_abierto and trailing_stop:

            # Verificar Timeout de Tiempo para evitar bloqueos de capital
            minutos_transcurridos = int((datetime.now() - trailing_stop.hora_inicio).total_seconds() / 60)
            if minutos_transcurridos >= config.TIMEOUT_TRADE_MINUTOS:
                ganancia_pct = (precio_actual - precio_entrada) / precio_entrada * 100
                ganancia_usd = capital_en_uso * (ganancia_pct / 100)
                print(f"[Main] TIMEOUT DETECTADO - Trade abierto por {minutos_transcurridos} min (limite {config.TIMEOUT_TRADE_MINUTOS} min). Cerrando.")
                cerrar_trade(precio_actual, f"TIMEOUT_{config.TIMEOUT_TRADE_MINUTOS}MIN", ganancia_usd)
                time.sleep(config.SEGUNDOS_CICLO)
                continue

            resultado = trailing_stop.actualizar(precio_actual)
            if resultado["cerrar"]:
                cerrar_trade(precio_actual, resultado["estado"], resultado["ganancia_usd"])

        # ── Búsqueda de señal de entrada ──
        elif not trade_abierto:

            if trades_hoy >= config.MAX_TRADES_DIA:
                time.sleep(config.SEGUNDOS_CICLO)
                continue

            # No operar si Fear & Greed dice vender o régimen es bajista fuerte
            if contexto.get("señal_mercado") == "VENDER":
                time.sleep(config.SEGUNDOS_CICLO)
                continue

            if not regimen_info.get("operar", True):
                time.sleep(config.SEGUNDOS_CICLO)
                continue

            # Score mínimo según régimen actual
            score_minimo = regimen_info.get("score_minimo", config.SCORE_MINIMO_ENTRADA)
            rsi_compra   = regimen_info.get("rsi_compra",   config.RSI_COMPRA)

            # --- Condición especial para Régimen Lateral (Rebote) ---
            es_rebote_lateral = False
            if regimen_info["regimen"] == "LATERAL":
                soporte = indicadores.get("soporte", 0)
                banda_inf = indicadores.get("banda_inf", 0)
                distancia_soporte = abs(precio_actual - soporte) / precio_actual * 100 if soporte > 0 else 99.0
                toca_bollinger = precio_actual <= banda_inf * 1.002
                
                # Cerca de soporte (< 0.5%) o tocando la banda inferior de Bollinger y con RSI bajo (< 45)
                if (distancia_soporte <= 0.5 or toca_bollinger) and rsi <= 45:
                    es_rebote_lateral = True
                    print(f"[Main] REBOTE LATERAL DETECTADO - Precio: ${precio_actual:,.2f} | Soporte: ${soporte:,.2f} | Banda Inf: ${banda_inf:,.2f} | RSI: {rsi:.1f}")

            # Condición de entrada: Score suficiente + RSI en zona (o Rebote Lateral)
            if (score >= score_minimo and rsi <= rsi_compra) or es_rebote_lateral:

                print(f"[Main] Senal tecnica detectada (Score: {score} | RSI: {rsi}). Validando con Filtros de IA...")
                
                # ── Sistema de pesos adaptativos ──
                prob_xgb = 0.5
                prob_lstm = 0.5
                decision_final = 0.0
                
                if usar_ia and cerebro_ia:
                    velas_ia = []
                    for i in range(len(c15m)):
                        velas_ia.append([c15m[i], v15m[i]])
                    
                    cambio_1 = (c15m[-1] - c15m[-2]) / c15m[-2] * 100 if len(c15m)>1 else 0
                    cambio_2 = (c15m[-2] - c15m[-3]) / c15m[-3] * 100 if len(c15m)>2 else 0
                    cambio_3 = (c15m[-3] - c15m[-4]) / c15m[-4] * 100 if len(c15m)>3 else 0
                    dist_soporte = (c15m[-1] - min(c15m[-20:])) / c15m[-1] * 100 if len(c15m)>20 else 0
                    from indicadores import calcular_atr
                    atr_val = calcular_atr(h15m, l15m, c15m)
                    atr_rel = (atr_val / c15m[-1] * 100) if c15m[-1] > 0 else 0
                    
                    indicadores_actuales = {
                        'rsi': rsi,
                        'score_tecnico': score,
                        'fear_greed': contexto.get("fear_greed_valor", 50),
                        'imbalance_libro': imbalance,
                        'ballenas_neto': ballenas["neto"],
                        'cambio_vela_1': cambio_1,
                        'cambio_vela_2': cambio_2,
                        'cambio_vela_3': cambio_3,
                        'distancia_soporte': dist_soporte,
                        'atr_relativo': atr_rel
                    }
                    
                    evaluacion = cerebro_ia.evaluar_entrada(velas_ia, indicadores_actuales)
                    prob_xgb  = evaluacion.get("prob_exito", 50.0) / 100.0
                    prob_lstm = evaluacion.get("prob_tendencia", 0.5)

                    # Normalizar score técnico a 0-1
                    score_norm = score / 100

                    # Decisión por pesos
                    decision_final = (
                        score_norm * config.PESOS_DECISION["score_tecnico"] +
                        prob_xgb   * config.PESOS_DECISION["xgboost"] +
                        prob_lstm  * config.PESOS_DECISION["lstm"]
                    )

                    print(f"[IA] Score: {score_norm:.2f} | XGB: {prob_xgb:.2f} | LSTM: {prob_lstm:.2f} | Final: {decision_final:.2f}")

                    aprobado = decision_final >= 0.60
                else:
                    # Sin IA — solo score técnico
                    aprobado = (score >= score_minimo and rsi <= rsi_compra) or es_rebote_lateral
                    decision_final = score / 100

                trade_info = {
                    "rsi": rsi,
                    "score": score,
                    "prob_xgb": prob_xgb,
                    "prob_lstm": prob_lstm,
                    "decision_final": decision_final,
                    "patron": patron,
                    "volumen_relativo": indicadores.get("volumen_relativo", 1.0)
                }

                if not aprobado:
                    print(f"[Main] Rechazado por sistema hibrido / tecnico (Decision Final: {decision_final:.2f})")
                    time.sleep(config.SEGUNDOS_CICLO)
                    continue


                # 2. Consultar filtro de IA Generativa macro (Groq / Llama)
                aprobado_por_ia = filtrar_con_ia(
                    c15m, v15m, regimen_info["regimen"], score, imbalance, ballenas["neto"], contexto.get("fear_greed_valor", 50)
                )

                
                if aprobado_por_ia:
                    # Calcular capital y SL dinámico
                    capital = riesgo.calcular_capital_trade(config.CAPITAL_USDT)
                    
                    if es_rebote_lateral:
                        # En rebote lateral, ponemos un TP y SL más cortos (Scalping)
                        sl_din = precio_actual * 0.992  # SL corto del 0.8%
                        tp_din_pct = 1.0                # TP de scalping del 1.0%
                        print(f"[Main] Entrando en modo Rebote Lateral (Scalping). TP: 1.0% | SL: 0.8%")
                    else:
                        sl_din  = riesgo.calcular_sl_dinamico(precio_actual, h15m, l15m, c15m)
                        tp_din_pct = riesgo.calcular_tp_dinamico(precio_actual, h15m, l15m, c15m)

                    print(f"[Main] SEÑAL APROBADA POR IA - Score: {score}/100 | RSI: {rsi} | Patron: {patron}")
                    for k, v in detalles.items():
                        print(f"[Main]    {k}: {v}")

                    abrir_trade(precio_actual, capital, sl_din, tp_din_pct=tp_din_pct)
                else:
                    print(f"[Main] Filtro de IA rechazo la operacion. Se descarta la entrada.")

            else:
                if score > 30:  # Solo mostrar si hay algo interesante
                    print(f"[Main] Score insuficiente: {score}/{score_minimo} | RSI: {rsi}/{rsi_compra}")

        time.sleep(config.SEGUNDOS_CICLO)

    except KeyboardInterrupt:
        print("\n[Main] Bot detenido.")

        tiempo = datetime.now() - hora_inicio
        horas  = int(tiempo.total_seconds() // 3600)
        mins   = int((tiempo.total_seconds() % 3600) // 60)
        stats  = leer_estadisticas()
        trades_dia = leer_del_dia()
        ganancia_sesion = sum(float(t.get("ganancia", 0)) for t in trades_dia)
        signo = "+" if ganancia_sesion >= 0 else ""

        print(f"[Main] Tiempo: {horas}h {mins}m | Trades: {trades_hoy} | Ganancia: {signo}${ganancia_sesion:.2f}")

        enviar_email("📊 Resumen de sesión — Bot detenido", f"""
        <html><body style="font-family:Arial;padding:20px">
        <h2>🤖 Resumen de sesión</h2>
        <p>⏱️ Tiempo encendido: {horas}h {mins}m</p>
        <p>📊 Trades realizados: {trades_hoy}</p>
        <p>💰 Ganancia sesión: {signo}${ganancia_sesion:.2f}</p>
        <p>📈 Winrate total: {stats['winrate']}%</p>
        <p>💵 Ganancia acumulada: ${stats['ganancia_acumulada']:.2f}</p>
        </body></html>
        """)
        print(f"[Main] 📧 Resumen enviado a {config.EMAIL_DESTINATARIO}")
        break

    except Exception as e:
        print(f"[Main] ERROR: {e}")
        time.sleep(30)
