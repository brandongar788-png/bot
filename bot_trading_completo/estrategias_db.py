# ============================================================
#   BOT DE TRADING — BIBLIOTECA DE ESTRATEGIAS
#   Archivo: estrategias_db.py
#   Descripción: Guarda, rankea y evoluciona las estrategias
#                del bot de peor a mejor según rendimiento real.
# ============================================================

import json
import os
from datetime import datetime, timedelta
from historial import leer_todos
import config


ARCHIVO_ESTRATEGIAS = "data/estrategias.json"


# ════════════════════════════════════════════
# ESTRUCTURA DE UNA ESTRATEGIA
# ════════════════════════════════════════════

def _nueva_estrategia(nombre: str, params: dict) -> dict:
    return {
        "id"               : nombre,
        "nombre"           : nombre,
        "params"           : params,          # EMA, RSI, SL, TP, etc.
        "creada"           : datetime.now().strftime("%Y-%m-%d"),
        "activa"           : False,

        # Rendimiento
        "total_trades"     : 0,
        "trades_ganados"   : 0,
        "trades_perdidos"  : 0,
        "winrate"          : 0.0,
        "ganancia_total"   : 0.0,
        "ganancia_dia"     : 0.0,
        "ganancia_semana"  : 0.0,
        "ganancia_mes"     : 0.0,
        "mejor_trade"      : 0.0,
        "peor_trade"       : 0.0,
        "racha_ganadora"   : 0,
        "racha_perdedora"  : 0,
        "score_global"     : 0.0,             # Score calculado para el ranking
        "rank"             : 99,              # Posición en el ranking (1 = mejor)

        # Metadata
        "dias_activa"      : 0,
        "ultima_evaluacion": "",
        "estado"           : "🟡 NUEVA",      # 🟢 BUENA / 🟡 NUEVA / 🔴 MALA
    }


# ════════════════════════════════════════════
# BASE DE ESTRATEGIAS
# ════════════════════════════════════════════

class BibliotecaEstrategias:

    def __init__(self):
        self._inicializar()

    def _inicializar(self):
        """Crea el archivo y las estrategias iniciales si no existen."""
        os.makedirs("data", exist_ok=True)

        if not os.path.exists(ARCHIVO_ESTRATEGIAS):
            estrategias_iniciales = self._crear_estrategias_iniciales()
            self._guardar(estrategias_iniciales)
            print(f"[Estrategias] Biblioteca creada con {len(estrategias_iniciales)} estrategias.")

    def _crear_estrategias_iniciales(self) -> dict:
        """Estrategias predefinidas para empezar."""
        return {
            "EMA9_RSI35_Clasica": _nueva_estrategia("EMA9_RSI35_Clasica", {
                "EMA_RAPIDA"      : 9,
                "EMA_LENTA"       : 21,
                "RSI_COMPRA"      : 35,
                "RSI_VENTA"       : 65,
                "STOP_LOSS_PCT"   : 1.5,
                "TAKE_PROFIT_PCT" : 2.5,
                "descripcion"     : "Estrategia clásica EMA + RSI"
            }),
            "EMA12_RSI30_Conservadora": _nueva_estrategia("EMA12_RSI30_Conservadora", {
                "EMA_RAPIDA"      : 12,
                "EMA_LENTA"       : 26,
                "RSI_COMPRA"      : 30,
                "RSI_VENTA"       : 70,
                "STOP_LOSS_PCT"   : 1.0,
                "TAKE_PROFIT_PCT" : 2.0,
                "descripcion"     : "Conservadora: entra menos pero más segura"
            }),
            "EMA7_RSI40_Agresiva": _nueva_estrategia("EMA7_RSI40_Agresiva", {
                "EMA_RAPIDA"      : 7,
                "EMA_LENTA"       : 18,
                "RSI_COMPRA"      : 40,
                "RSI_VENTA"       : 60,
                "STOP_LOSS_PCT"   : 2.0,
                "TAKE_PROFIT_PCT" : 3.5,
                "descripcion"     : "Agresiva: más trades, mayor riesgo/recompensa"
            }),
            "EMA10_RSI33_Balanceada": _nueva_estrategia("EMA10_RSI33_Balanceada", {
                "EMA_RAPIDA"      : 10,
                "EMA_LENTA"       : 22,
                "RSI_COMPRA"      : 33,
                "RSI_VENTA"       : 67,
                "STOP_LOSS_PCT"   : 1.5,
                "TAKE_PROFIT_PCT" : 3.0,
                "descripcion"     : "Balanceada entre frecuencia y seguridad"
            }),
        }

    # ────────────────────────────────────────
    # REGISTRAR RESULTADO DE UN TRADE
    # ────────────────────────────────────────

    def registrar_trade(self, ganancia: float):
        """
        Registra el resultado de un trade en la estrategia activa.
        Se llama desde main.py cada vez que se cierra un trade.
        """
        estrategias = self._leer()
        activa_id   = self._obtener_activa_id(estrategias)

        if not activa_id:
            return

        e = estrategias[activa_id]
        e["total_trades"]   += 1
        e["ganancia_total"]  = round(e["ganancia_total"] + ganancia, 2)

        if ganancia > 0:
            e["trades_ganados"]  += 1
            e["mejor_trade"]      = max(e["mejor_trade"], ganancia)
        else:
            e["trades_perdidos"] += 1
            e["peor_trade"]       = min(e["peor_trade"], ganancia)

        total = e["total_trades"]
        e["winrate"] = round(e["trades_ganados"] / total * 100, 1) if total > 0 else 0

        self._guardar(estrategias)

    # ────────────────────────────────────────
    # EVALUAR Y RANKEAR
    # ────────────────────────────────────────

    def evaluar_todas(self):
        """
        Calcula el rendimiento diario/semanal/mensual de cada estrategia
        y actualiza el ranking. Se llama una vez al día.
        """
        print("[Estrategias] 📊 Evaluando todas las estrategias...")
        estrategias = self._leer()
        todos_trades = leer_todos()

        for nombre, e in estrategias.items():
            trades_estrategia = [
                t for t in todos_trades
                if t.get("ema_rapida") == str(e["params"].get("EMA_RAPIDA")) and
                   t.get("ema_lenta")  == str(e["params"].get("EMA_LENTA"))
            ]

            if not trades_estrategia:
                continue

            # Ganancias por período
            e["ganancia_dia"]    = self._ganancia_periodo(trades_estrategia, dias=1)
            e["ganancia_semana"] = self._ganancia_periodo(trades_estrategia, dias=7)
            e["ganancia_mes"]    = self._ganancia_periodo(trades_estrategia, dias=30)
            e["dias_activa"]     = self._contar_dias_activa(trades_estrategia)

            # Score global (combina winrate + ganancia + consistencia)
            e["score_global"] = self._calcular_score(e)

            # Estado visual
            if e["winrate"] >= 60 and e["ganancia_semana"] > 0:
                e["estado"] = "🟢 BUENA"
            elif e["winrate"] < 45 or e["ganancia_semana"] < -10:
                e["estado"] = "🔴 MALA"
            else:
                e["estado"] = "🟡 REGULAR"

            e["ultima_evaluacion"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Asignar ranking
        ordenadas = sorted(
            estrategias.items(),
            key=lambda x: x[1]["score_global"],
            reverse=True
        )
        for rank, (nombre, e) in enumerate(ordenadas, 1):
            estrategias[nombre]["rank"] = rank

        self._guardar(estrategias)
        print(f"[Estrategias] Ranking actualizado. #1: {ordenadas[0][0]}")

    def activar_mejor(self) -> dict:
        """
        Activa la estrategia con mejor score y aplica sus parámetros a config.
        """
        estrategias = self._leer()
        mejor       = self._obtener_mejor(estrategias)

        if not mejor:
            return {}

        # Desactivar todas
        for e in estrategias.values():
            e["activa"] = False

        # Activar la mejor
        estrategias[mejor["id"]]["activa"] = True
        self._guardar(estrategias)

        # Aplicar parámetros al config
        params = mejor["params"]
        config.EMA_RAPIDA       = params.get("EMA_RAPIDA",       config.EMA_RAPIDA)
        config.EMA_LENTA        = params.get("EMA_LENTA",        config.EMA_LENTA)
        config.RSI_COMPRA       = params.get("RSI_COMPRA",       config.RSI_COMPRA)
        config.RSI_VENTA        = params.get("RSI_VENTA",        config.RSI_VENTA)
        config.STOP_LOSS_PCT    = params.get("STOP_LOSS_PCT",    config.STOP_LOSS_PCT)
        config.TAKE_PROFIT_PCT  = params.get("TAKE_PROFIT_PCT",  config.TAKE_PROFIT_PCT)

        print(f"[Estrategias] ✅ Activada: #{mejor['rank']} {mejor['id']} (score: {mejor['score_global']:.1f})")
        return mejor

    def agregar_estrategia(self, nombre: str, params: dict):
        """Agrega una nueva estrategia (generada por el optimizador)."""
        estrategias = self._leer()
        if nombre not in estrategias:
            estrategias[nombre] = _nueva_estrategia(nombre, params)
            self._guardar(estrategias)
            print(f"[Estrategias] Nueva estrategia agregada: {nombre}")

    # ────────────────────────────────────────
    # REPORTE DE RANKING
    # ────────────────────────────────────────

    def generar_ranking_texto(self) -> str:
        """Genera el texto del ranking para el email."""
        estrategias = self._leer()
        ordenadas   = sorted(
            estrategias.values(),
            key=lambda x: x["rank"]
        )

        lineas = ["RANKING DE ESTRATEGIAS\n" + "─" * 45]
        for e in ordenadas:
            lineas.append(
                f"#{e['rank']} {e['estado']} {e['id']}\n"
                f"    Winrate: {e['winrate']}% | Score: {e['score_global']:.1f}\n"
                f"    Hoy: ${e['ganancia_dia']:.2f} | "
                f"Semana: ${e['ganancia_semana']:.2f} | "
                f"Mes: ${e['ganancia_mes']:.2f}\n"
                f"    {e['params'].get('descripcion','')}\n"
            )

        lineas.append(f"\n✅ Estrategia activa: #{self._obtener_activa_rank(estrategias)}")
        return "\n".join(lineas)

    def generar_ranking_html(self) -> str:
        """Genera HTML del ranking para los emails."""
        estrategias = self._leer()
        ordenadas   = sorted(estrategias.values(), key=lambda x: x["rank"])

        filas = ""
        for e in ordenadas:
            color = "#e8f5e9" if "BUENA" in e["estado"] else (
                    "#ffebee" if "MALA"  in e["estado"] else "#fffde7")
            filas += f"""
            <tr style="background:{color}">
                <td>#{e['rank']}</td>
                <td>{e['estado']} {e['id']}</td>
                <td>{e['winrate']}%</td>
                <td>${e['ganancia_dia']:.2f}</td>
                <td>${e['ganancia_semana']:.2f}</td>
                <td>${e['ganancia_mes']:.2f}</td>
            </tr>
            """

        return f"""
        <table style="width:100%;border-collapse:collapse;font-size:12px">
            <tr style="background:#1565c0;color:white">
                <th>Rank</th><th>Estrategia</th><th>Winrate</th>
                <th>Hoy</th><th>Semana</th><th>Mes</th>
            </tr>
            {filas}
        </table>
        """

    # ────────────────────────────────────────
    # UTILIDADES INTERNAS
    # ────────────────────────────────────────

    def _ganancia_periodo(self, trades: list, dias: int) -> float:
        desde = datetime.now() - timedelta(days=dias)
        total = 0.0
        for t in trades:
            try:
                fecha = datetime.strptime(t["fecha_entrada"][:19], "%Y-%m-%d %H:%M:%S")
                if fecha >= desde:
                    total += float(t.get("ganancia", 0))
            except Exception:
                continue
        return round(total, 2)

    def _contar_dias_activa(self, trades: list) -> int:
        if not trades:
            return 0
        try:
            primera = datetime.strptime(trades[0]["fecha_entrada"][:10], "%Y-%m-%d")
            return (datetime.now() - primera).days
        except Exception:
            return 0

    def _calcular_score(self, e: dict) -> float:
        """Score combinado: winrate 40% + ganancia 40% + consistencia 20%"""
        score_wr   = e["winrate"]                          # 0-100
        score_gan  = min(100, max(0, e["ganancia_semana"] * 5 + 50))  # normalizado
        consistencia = 100 if e["racha_perdedora"] < 3 else max(0, 100 - e["racha_perdedora"] * 10)
        return round(score_wr * 0.4 + score_gan * 0.4 + consistencia * 0.2, 1)

    def _obtener_mejor(self, estrategias: dict) -> dict | None:
        if not estrategias:
            return None
        return max(estrategias.values(), key=lambda x: x["score_global"])

    def _obtener_activa_id(self, estrategias: dict) -> str | None:
        for nombre, e in estrategias.items():
            if e.get("activa"):
                return nombre
        # Si ninguna está activa, activar la primera
        if estrategias:
            primera = list(estrategias.keys())[0]
            estrategias[primera]["activa"] = True
            return primera
        return None

    def _obtener_activa_rank(self, estrategias: dict) -> int:
        for e in estrategias.values():
            if e.get("activa"):
                return e["rank"]
        return 0

    def _leer(self) -> dict:
        try:
            with open(ARCHIVO_ESTRATEGIAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._crear_estrategias_iniciales()

    def _guardar(self, estrategias: dict):
        os.makedirs("data", exist_ok=True)
        with open(ARCHIVO_ESTRATEGIAS, "w", encoding="utf-8") as f:
            json.dump(estrategias, f, indent=2, ensure_ascii=False)


# ════════════════════════════════════════════
# TEST RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 55)
    print("  TEST — BIBLIOTECA DE ESTRATEGIAS")
    print("═" * 55)

    db = BibliotecaEstrategias()

    # Simular algunos trades
    for ganancia in [2.5, -1.5, 3.0, 2.0, -1.0, 2.8, 1.9, -1.5, 3.5, 2.1]:
        db.registrar_trade(ganancia)

    db.evaluar_todas()
    mejor = db.activar_mejor()

    print("\n" + db.generar_ranking_texto())
    print("═" * 55)
