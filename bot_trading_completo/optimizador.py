# ============================================================
#   BOT DE TRADING — MOTOR DE EVOLUCIÓN Y BACKTESTING GENÉTICO
#   Archivo: optimizador.py
#   Descripción: Motor evolutivo CPU-friendly que muta parámetros
#                técnicos y los simula vectorialmente sobre
#                las velas de los últimos 7 días.
# ============================================================

import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import config

class Backtester:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def simular(self, params: dict) -> dict:
        """
        Simula una estrategia clásica EMA + RSI de forma vectorial y súper veloz.
        """
        if len(self.df) < 30:
            return {"total_trades": 0, "winrate": 0.0, "ganancia_total": 0.0, "trades": []}

        # Calcular EMAs y RSI usando pandas
        close = self.df['cierre']
        
        # EMA rápida y lenta
        ema_fast = close.ewm(span=int(params['EMA_RAPIDA']), adjust=False).mean()
        ema_slow = close.ewm(span=int(params['EMA_LENTA']), adjust=False).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        
        # Evitar división por cero
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            rsi = rsi.fillna(50.0)
        
        self.df['ema_fast'] = ema_fast
        self.df['ema_slow'] = ema_slow
        self.df['rsi'] = rsi
        
        # Señal de compra: EMA rápida por encima de EMA lenta y RSI en zona de compra
        self.df['signal'] = (ema_fast > ema_slow) & (rsi <= params['RSI_COMPRA'])
        
        # Simulación de trades
        close_arr = self.df['cierre'].values
        high_arr = self.df['alto'].values
        low_arr = self.df['bajo'].values
        sig_arr = self.df['signal'].values
        
        trades = []
        in_trade = False
        entry_price = 0.0
        
        sl_pct = params['STOP_LOSS_PCT'] / 100.0
        tp_pct = params['TAKE_PROFIT_PCT'] / 100.0
        
        for i in range(15, len(self.df)):
            if not in_trade:
                if sig_arr[i]:
                    in_trade = True
                    entry_price = close_arr[i]
            else:
                sl_price = entry_price * (1.0 - sl_pct)
                tp_price = entry_price * (1.0 + tp_pct)
                
                # Revisar límites
                hit_sl = low_arr[i] <= sl_price
                hit_tp = high_arr[i] >= tp_price
                
                if hit_sl and hit_tp:
                    # En la misma vela, asumimos conservadoramente que tocó SL primero
                    trades.append(-params['STOP_LOSS_PCT'])
                    in_trade = False
                elif hit_sl:
                    trades.append(-params['STOP_LOSS_PCT'])
                    in_trade = False
                elif hit_tp:
                    trades.append(params['TAKE_PROFIT_PCT'])
                    in_trade = False
                elif i == len(self.df) - 1:
                    # Forzar cierre al final de los datos históricos
                    pct = (close_arr[i] - entry_price) / entry_price * 100.0
                    trades.append(round(pct, 2))
                    in_trade = False
                    
        total_trades = len(trades)
        winrate = 0.0
        ganancia_total = 0.0
        
        if total_trades > 0:
            trades_ganados = sum(1 for t in trades if t > 0)
            winrate = round((trades_ganados / total_trades) * 100, 1)
            ganancia_total = round(sum(trades), 2)
            
        return {
            "total_trades": total_trades,
            "winrate": winrate,
            "ganancia_total": ganancia_total,
            "trades": trades
        }


def descargar_velas_completas(dias=7) -> pd.DataFrame:
    """
    Descarga velas de 15m con OHLCV de Binance de los últimos N días.
    Si falla, devuelve un DataFrame sintético idéntico en formato.
    """
    try:
        from binance.client import Client
        
        key = config.BINANCE_API_KEY if config.BINANCE_API_KEY else config.BINANCE_TESTNET_API_KEY
        secret = config.BINANCE_API_SECRET if config.BINANCE_API_SECRET else config.BINANCE_TESTNET_API_SECRET
        
        if not key or not secret:
            raise ValueError("No hay credenciales en config.py")
            
        print(f"[Optimizador] Descargando velas de Binance de los ultimos {dias} dias...")
        cliente = Client(key, secret, testnet=(config.MODO == "DEMO"))
        
        inicio_str = (datetime.now() - timedelta(days=dias)).strftime("%d %b, %Y")
        velas = cliente.get_historical_klines(
            symbol=config.PAR,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            start_str=inicio_str
        )
        
        datos = []
        for v in velas:
            datos.append({
                "tiempo": datetime.fromtimestamp(v[0] / 1000.0),
                "abierto": float(v[1]),
                "alto": float(v[2]),
                "bajo": float(v[3]),
                "cierre": float(v[4]),
                "volumen": float(v[5])
            })
        df = pd.DataFrame(datos)
        if df.empty:
            raise ValueError("API de Binance no retorno datos")
        print(f"[Optimizador] OK: Descargadas {len(df)} velas reales con exito.")
        return df
        
    except Exception as e:
        print(f"[Optimizador] AVISO: Error en descarga historica ({e}). Creando velas sinteticas...")
        
        # Generar velas sintéticas para simulación CPU/RAM segura
        n_velas = dias * 96
        cierre_base = 65000.0
        datos_sint = []
        fecha_base = datetime.now() - timedelta(days=dias)
        
        for i in range(n_velas):
            cambio = random.uniform(-0.002, 0.0021)  # Ligero sesgo alcista
            abierto = cierre_base
            cierre = abierto * (1 + cambio)
            alto = max(abierto, cierre) * (1 + random.uniform(0.0005, 0.003))
            bajo = min(abierto, cierre) * (1 - random.uniform(0.0005, 0.003))
            vol = random.uniform(10.0, 150.0)
            
            datos_sint.append({
                "tiempo": fecha_base + timedelta(minutes=15 * i),
                "abierto": round(abierto, 2),
                "alto": round(alto, 2),
                "bajo": round(bajo, 2),
                "cierre": round(cierre, 2),
                "volumen": round(vol, 2)
            })
            cierre_base = cierre
            
        df = pd.DataFrame(datos_sint)
        print(f"[Optimizador] OK: Creadas {len(df)} velas sinteticas de contingencia.")
        return df


class EvolucionadorGenetico:
    @staticmethod
    def evolucionar_poblacion() -> str:
        """
        Carga las estrategias actuales, muta la mejor estrategia,
        hace backtesting y guarda el mejor mutant calificado.
        """
        print("[Optimizador] Iniciando ciclo de evolucion genetica...")
        
        # 1. Obtener velas de simulación
        df_velas = descargar_velas_completas(dias=7)
        if df_velas.empty:
            print("[Optimizador] ERROR: No se cargaron velas para backtesting. Abortando.")
            return None
            
        # 2. Cargar estrategias actuales
        from estrategias_db import BibliotecaEstrategias
        db = BibliotecaEstrategias()
        estrategias = db._leer()
        
        if not estrategias:
            print("[Optimizador] ERROR: Biblioteca de estrategias vacia. Abortando.")
            return None
            
        # 3. Elegir la mejor estrategia como padre
        mejor_actual = max(estrategias.values(), key=lambda x: x.get("score_global", 0.0))
        padre_params = mejor_actual["params"]
        padre_id = mejor_actual["id"]
        
        print(f"[Optimizador] Padre seleccionado: {padre_id} | Score actual: {mejor_actual.get('score_global')}")
        
        # 4. Generar candidatos mutados
        candidatos = []
        n_mutaciones = 20
        
        for i in range(n_mutaciones):
            # Aplicar mutaciones dentro de rangos seguros y realistas
            ema_rapida = max(5, min(15, int(padre_params.get("EMA_RAPIDA", 9) + random.choice([-3, -2, -1, 1, 2, 3]))))
            ema_lenta = max(18, min(35, int(padre_params.get("EMA_LENTA", 21) + random.choice([-4, -3, -2, -1, 1, 2, 3, 4]))))
            
            # Evitar EMAs incorrectas (lenta debe ser mayor que rapida)
            if ema_lenta <= ema_rapida + 4:
                ema_lenta = ema_rapida + 5
                
            rsi_compra = max(25, min(45, int(padre_params.get("RSI_COMPRA", 35) + random.choice([-3, -2, -1, 1, 2, 3]))))
            rsi_venta = max(55, min(75, int(padre_params.get("RSI_VENTA", 65) + random.choice([-3, -2, -1, 1, 2, 3]))))
            
            stop_loss = max(0.5, min(2.5, round(padre_params.get("STOP_LOSS_PCT", 1.5) + random.uniform(-0.4, 0.4), 1)))
            take_profit = max(1.0, min(5.0, round(padre_params.get("TAKE_PROFIT_PCT", 2.5) + random.uniform(-0.5, 0.5), 1)))
            
            candidato_params = {
                "EMA_RAPIDA": ema_rapida,
                "EMA_LENTA": ema_lenta,
                "RSI_COMPRA": rsi_compra,
                "RSI_VENTA": rsi_venta,
                "STOP_LOSS_PCT": stop_loss,
                "TAKE_PROFIT_PCT": take_profit,
                "descripcion": f"Mutante derivado de {padre_id}"
            }
            candidatos.append(candidato_params)
            
        # 5. Backtesting de candidatos
        backtester = Backtester(df_velas)
        mejores_mutantes = []
        
        for idx, c_params in enumerate(candidatos):
            res = backtester.simular(c_params)
            # Guardamos si es rentable y tiene winrate aceptable y al menos 2 trades
            if res["ganancia_total"] > 0 and res["winrate"] > 50.0 and res["total_trades"] >= 2:
                mejores_mutantes.append({
                    "params": c_params,
                    "resultado": res
                })
                
        # 6. Guardar la mejor si califica
        if mejores_mutantes:
            # Ordenar por ganancia total descendente
            mejores_mutantes = sorted(mejores_mutantes, key=lambda x: x["resultado"]["ganancia_total"], reverse=True)
            ganador = mejores_mutantes[0]
            ganador_params = ganador["params"]
            ganador_res = ganador["resultado"]
            
            # Generar identificador correlativo para el nuevo mutante
            max_n = 0
            for name in estrategias.keys():
                if name.startswith("EXP_EMA_RSI_V"):
                    try:
                        num = int(name.replace("EXP_EMA_RSI_V", ""))
                        max_n = max(max_n, num)
                    except ValueError:
                        pass
            nuevo_n = max_n + 1
            nuevo_nombre = f"EXP_EMA_RSI_V{nuevo_n}"
            
            # Guardar en base de datos
            db.agregar_estrategia(nuevo_nombre, ganador_params)
            print(f"[Optimizador] NUEVO MUTANTE PATENTADO: {nuevo_nombre}")
            print(f"    Parametros: {ganador_params}")
            print(f"    Simulacion 7d: Ganancia: {ganador_res['ganancia_total']}% | Winrate: {ganador_res['winrate']}% | Trades: {ganador_res['total_trades']}")
            
            # Re-evaluar de inmediato para re-ordenar el ranking
            db.evaluar_todas()
            return nuevo_nombre
        else:
            print("[Optimizador] No se encontraron candidatos rentables con winrate > 50% en esta generacion.")
            return None


if __name__ == "__main__":
    print("=" * 50)
    print(" TESTSTAND DE OPTIMIZADOR GENETICO")
    print("=" * 50)
    
    # Crear archivo si no existe
    from estrategias_db import BibliotecaEstrategias
    db = BibliotecaEstrategias()
    
    # Ejecutar evolución manual
    nuevo = EvolucionadorGenetico.evolucionar_poblacion()
    if nuevo:
        print(f"\n[Test] Evolucion completada con exito! Nueva estrategia: {nuevo}")
    else:
        print("\n[Test] Evolucion completada. No hubo nuevas estrategias aprobadas.")
    print("=" * 50)
