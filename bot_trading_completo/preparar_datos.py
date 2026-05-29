# ============================================================
#   BOT DE TRADING — GENERADOR Y PREPARADOR DE DATOS DE IA
#   Archivo: preparar_datos.py
#   Descripción: Estructura los datos reales o sintéticos para
#                poder entrenar los modelos LSTM y XGBoost.
# ============================================================

import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import config

try:
    from binance.client import Client
    IA_DISPONIBLE = True
except ImportError:
    IA_DISPONIBLE = False

ARCHIVO_HISTORIAL = "data/historial.json"


def generar_datos_sinteticos_trades(cantidad=200) -> pd.DataFrame:
    """
    Genera un histórico de trades simulados realistas para pre-entrenar XGBoost.
    Esto permite que el bot empiece con un cerebro ya entrenado.
    """
    print(f"[Datos] Generando {cantidad} trades sinteticos basados en reglas del mercado...")
    
    datos = []
    fecha_base = datetime.now() - timedelta(days=30)

    for i in range(cantidad):
        # Simular indicadores realistas
        rsi = random.uniform(15.0, 85.0)
        score_tecnico = random.uniform(20.0, 95.0)
        fear_greed = random.randint(10, 90)
        imbalance_libro = random.uniform(0.3, 2.5)
        ballenas_neto = random.uniform(-100000.0, 100000.0)
        
        # Lógica heurística para determinar si el trade ganará dinero (etiqueta real)
        # Una buena configuración de compra tiene alta probabilidad de éxito
        probabilidad_ganar = 0.35  # Probabilidad base
        
        if rsi <= 35:
            probabilidad_ganar += 0.20  # Sobrevendido es bueno
        elif rsi >= 70:
            probabilidad_ganar -= 0.25  # Sobrecomprado es malo
            
        if score_tecnico >= 70:
            probabilidad_ganar += 0.20  # Fuertes señales técnicas
            
        if fear_greed <= 25:
            probabilidad_ganar += 0.15  # Miedo extremo, buen momento de compra
        elif fear_greed >= 75:
            probabilidad_ganar -= 0.20  # Codicia extrema, riesgo alto
            
        if imbalance_libro >= 1.5:
            probabilidad_ganar += 0.15  # Presión de compra en el libro
        elif imbalance_libro <= 0.6:
            probabilidad_ganar -= 0.15
            
        if ballenas_neto > 30000:
            probabilidad_ganar += 0.10  # Ballenas acumulando

        # Decidir resultado final
        ganador = random.random() < probabilidad_ganar
        
        # Simular ganancia en dólares (ej. con capital de $100)
        if ganador:
            ganancia = random.uniform(0.5, 4.5)  # Ganó entre 0.5% y 4.5%
        else:
            ganancia = random.uniform(-0.5, -2.5) # Perdió entre 0.5% y 2.5%

        fecha = (fecha_base + timedelta(hours=i * 3)).strftime("%Y-%m-%d %H:%M:%S")

        datos.append({
            "id": i + 1,
            "rsi": round(rsi, 1),
            "score_tecnico": round(score_tecnico, 0),
            "fear_greed": fear_greed,
            "imbalance_libro": round(imbalance_libro, 2),
            "ballenas_neto": round(ballenas_neto, 2),
            "ganancia": round(ganancia, 2),
            "fecha_entrada": fecha
        })

    return pd.DataFrame(datos)


def obtener_datos_reales_trades() -> pd.DataFrame:
    """
    Lee los trades reales de tu historial.json y los formatea.
    Si no hay suficientes, los combina con sintéticos para no fallar.
    """
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return generar_datos_sinteticos_trades(150)

    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            trades = json.load(f)
            
        if len(trades) < 15:
            print(f"[Datos] AVISO: Solo hay {len(trades)} trades reales. Mezclando con sinteticos...")
            df_reales = pd.DataFrame(trades)
            # Normalizar nombres de columnas si cambian en el JSON
            if not df_reales.empty:
                df_reales = df_reales.rename(columns={"score": "score_tecnico"})
            
            df_sinteticos = generar_datos_sinteticos_trades(120)
            return pd.concat([df_reales, df_sinteticos], ignore_index=True)

        df = pd.DataFrame(trades)
        if "score" in df.columns:
            df = df.rename(columns={"score": "score_tecnico"})
        return df

    except Exception as e:
        print(f"[Datos] Error leyendo historial real: {e}. Usando sinteticos.")
        return generar_datos_sinteticos_trades(150)


def descargar_velas_historicas(dias=10) -> pd.DataFrame:
    """
    Descarga velas históricas reales de BTC/USDT de Binance (15m)
    para el entrenamiento del LSTM.
    """
    if not IA_DISPONIBLE:
        print("[Datos] API de Binance no disponible para descargar velas.")
        return pd.DataFrame()

    print(f"[Datos] Descargando velas de 15m de Binance de los ultimos {dias} dias para Deep Learning...")
    
    try:
        # Usar credenciales demo o reales del config
        key = config.BINANCE_API_KEY if config.BINANCE_API_KEY else config.BINANCE_TESTNET_API_KEY
        secret = config.BINANCE_API_SECRET if config.BINANCE_API_SECRET else config.BINANCE_TESTNET_API_SECRET
        
        # Conectar a la API
        cliente = Client(key, secret, testnet=(config.MODO == "DEMO"))
        
        # Calcular fecha de inicio
        inicio_str = (datetime.now() - timedelta(days=dias)).strftime("%d %b, %Y")
        
        velas = cliente.get_historical_klines(
            symbol=config.PAR,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            start_str=inicio_str
        )
        
        # Formatear a DataFrame
        datos = []
        for v in velas:
            datos.append({
                "cierre": float(v[4]),
                "volumen": float(v[5]),
                "tiempo": datetime.fromtimestamp(v[0] / 1000.0)
            })
            
        df = pd.DataFrame(datos)
        print(f"[Datos] OK: Descargadas {len(df)} velas con exito.")
        return df
        
    except Exception as e:
        print(f"[Datos] AVISO: Error al conectar con Binance API para descarga historica: {e}")
        # Crear velas sintéticas como plan de contingencia
        print("[Datos] Creando velas sinteticas para no detener la instalacion...")
        cierre_base = 65000.0
        datos_sint = []
        for i in range(1000):
            cierre_base += random.uniform(-150, 153) # Ligera deriva alcista
            vol = random.uniform(10.0, 150.0)
            datos_sint.append({
                "cierre": cierre_base,
                "volumen": vol,
                "tiempo": datetime.now() - timedelta(minutes=15 * (1000 - i))
            })
        return pd.DataFrame(datos_sint)


def preparar_y_entrenar_todo(cerebro_ia):
    """
    Función helper que descarga/extrae todo y entrena los modelos en un paso.
    """
    # 1. Obtener datos para XGBoost
    df_trades = obtener_datos_reales_trades()
    
    # 2. Obtener datos para LSTM
    df_velas = descargar_velas_historicas(dias=8)
    
    # 3. Entrenar en el cerebro
    if not df_velas.empty and not df_trades.empty:
        exito = cerebro_ia.entrenar_con_datos(df_velas, df_trades)
        if exito:
            print("[Datos] OK: El Cerebro de IA Hibrido se ha entrenado y esta listo!")
            return True
    print("[Datos] ERROR: No se pudo completar el entrenamiento inicial.")
    return False


if __name__ == "__main__":
    print("Test de preparacion de datos...")
    df = obtener_datos_reales_trades()
    print(f"Dataset de trades listo: {df.shape} filas.")
    print(df.head(3))

