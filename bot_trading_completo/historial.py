# ============================================================
#   BOT DE TRADING — HISTORIAL DE TRADES
#   Archivo: historial.py
#   Descripción: Guarda cada trade en un archivo JSON.
#                Permite leer estadísticas y rendimiento.
# ============================================================

import json
import os
from datetime import datetime, timedelta

ARCHIVO_HISTORIAL = "data/historial.json"


def _leer_archivo() -> list:
    """Lee el archivo de historial. Devuelve lista vacía si no existe."""
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar_archivo(trades: list):
    """Guarda la lista de trades en el archivo."""
    os.makedirs("data", exist_ok=True)
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)


# ════════════════════════════════════════════
# ESCRITURA
# ════════════════════════════════════════════

def guardar_trade(trade: dict):
    """
    Guarda un trade cerrado en el historial.

    trade debe tener al menos:
      precio_entrada, precio_salida, ganancia, motivo_cierre,
      ema_rapida, ema_lenta
    """
    trades = _leer_archivo()

    trade["fecha_entrada"] = trade.get(
        "fecha_entrada", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    trade["fecha_salida"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade["id"] = len(trades) + 1

    trades.append(trade)
    _guardar_archivo(trades)
    print(f"[Historial] Trade #{trade['id']} guardado — Ganancia: ${trade.get('ganancia', 0):.2f}")


# ════════════════════════════════════════════
# LECTURA
# ════════════════════════════════════════════

def leer_todos() -> list:
    """Devuelve todos los trades del historial."""
    return _leer_archivo()


def leer_del_dia(fecha: str = None) -> list:
    """
    Devuelve los trades de un día específico.
    Si fecha es None, devuelve los de hoy.
    """
    if fecha is None:
        fecha = datetime.now().strftime("%Y-%m-%d")

    todos = _leer_archivo()
    return [
        t for t in todos
        if t.get("fecha_entrada", "").startswith(fecha)
    ]


def leer_estadisticas() -> dict:
    """
    Calcula estadísticas globales de todos los trades.
    """
    todos = _leer_archivo()

    if not todos:
        return {
            "total_trades"       : 0,
            "trades_ganados"     : 0,
            "trades_perdidos"    : 0,
            "winrate"            : 0.0,
            "ganancia_acumulada" : 0.0,
            "mejor_trade"        : 0.0,
            "peor_trade"         : 0.0,
            "dias_operando"      : 0,
        }

    ganados  = [t for t in todos if float(t.get("ganancia", 0)) > 0]
    perdidos = [t for t in todos if float(t.get("ganancia", 0)) <= 0]
    ganancias = [float(t.get("ganancia", 0)) for t in todos]

    # Días únicos operando
    fechas = set()
    for t in todos:
        fecha_str = t.get("fecha_entrada", "")[:10]
        if fecha_str:
            fechas.add(fecha_str)

    return {
        "total_trades"       : len(todos),
        "trades_ganados"     : len(ganados),
        "trades_perdidos"    : len(perdidos),
        "winrate"            : round(len(ganados) / len(todos) * 100, 1) if todos else 0,
        "ganancia_acumulada" : round(sum(ganancias), 2),
        "mejor_trade"        : round(max(ganancias), 2) if ganancias else 0,
        "peor_trade"         : round(min(ganancias), 2) if ganancias else 0,
        "dias_operando"      : len(fechas),
    }


def leer_racha_actual() -> dict:
    """Calcula la racha actual de wins o losses consecutivos."""
    todos = _leer_archivo()
    if not todos:
        return {"tipo": "ninguna", "cantidad": 0}

    racha = 1
    ultimo = float(todos[-1].get("ganancia", 0))
    es_ganador = ultimo > 0

    for t in reversed(todos[:-1]):
        ganancia = float(t.get("ganancia", 0))
        if (ganancia > 0) == es_ganador:
            racha += 1
        else:
            break

    return {
        "tipo"     : "ganadora" if es_ganador else "perdedora",
        "cantidad" : racha,
    }


# ════════════════════════════════════════════
# TEST RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    # Simular algunos trades
    trades_prueba = [
        {"precio_entrada": 65000, "precio_salida": 66000, "ganancia": 2.5,
         "motivo_cierre": "TAKE_PROFIT", "ema_rapida": "9", "ema_lenta": "21"},
        {"precio_entrada": 66000, "precio_salida": 65500, "ganancia": -1.2,
         "motivo_cierre": "STOP_LOSS",   "ema_rapida": "9", "ema_lenta": "21"},
        {"precio_entrada": 65500, "precio_salida": 67000, "ganancia": 3.1,
         "motivo_cierre": "TRAILING_STOP", "ema_rapida": "9", "ema_lenta": "21"},
    ]

    for t in trades_prueba:
        guardar_trade(t)

    stats = leer_estadisticas()
    print(f"\n[Historial] Stats: {stats}")
    print(f"[Historial] Hoy: {len(leer_del_dia())} trades")
    print(f"[Historial] Racha: {leer_racha_actual()}")
