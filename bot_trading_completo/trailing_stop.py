# ============================================================
#   BOT DE TRADING — TRAILING STOP DINÁMICO
#   Archivo: trailing_stop.py
#   Descripción: El Stop Loss sigue al precio como una sombra.
#                Protege ganancias sin limitar el potencial.
# ============================================================

import config
from datetime import datetime


class TrailingStop:
    """
    Stop Loss dinámico que sube automáticamente con el precio.

    Fases:
    ─────
    FASE 1 — Precio sube +0.7% → SL se mueve a precio de entrada (breakeven)
             Ya no puedes perder dinero en este trade ✅

    FASE 2 — Precio sube +1.3% → SL se mueve a +0.6% (ganancia asegurada)
             Mínimo ganarás algo aunque el precio caiga ✅

    FASE 3 — Precio sube +2.0% → SL sigue al precio a 0.8% de distancia
             Maximiza la ganancia sin riesgo ✅
    """

    def __init__(self, precio_entrada: float, capital_usado: float, tp_pct: float = None, sl_pct: float = None):
        self.precio_entrada  = precio_entrada
        self.capital_usado   = capital_usado
        
        # SL y TP personalizados o estáticos según configuración
        pct_sl = sl_pct if sl_pct is not None else config.STOP_LOSS_PCT
        pct_tp = tp_pct if tp_pct is not None else config.TAKE_PROFIT_PCT
        
        self.sl_actual       = precio_entrada * (1 - pct_sl / 100)
        self.sl_inicial      = self.sl_actual
        self.tp_actual       = precio_entrada * (1 + pct_tp / 100)
        self.fase            = 1
        self.precio_maximo   = precio_entrada
        self.historial_sl    = []
        self.hora_inicio     = datetime.now()

        self._registrar(precio_entrada, "INICIO")
        print(f"[TrailingStop] Iniciado | Entrada: ${precio_entrada:,.2f} | SL: ${self.sl_actual:,.2f}")

    def actualizar(self, precio_actual: float) -> dict:
        """
        Actualiza el trailing stop según el precio actual.

        Devuelve:
            "estado"    → ABIERTO / STOP_LOSS / TAKE_PROFIT / TRAILING_STOP
            "sl_actual" → Precio actual del stop loss
            "ganancia"  → Ganancia/pérdida actual en $
            "fase"      → Fase actual del trailing (1, 2 o 3)
            "cerrar"    → True si se debe cerrar el trade
        """
        # Actualizar precio máximo alcanzado
        if precio_actual > self.precio_maximo:
            self.precio_maximo = precio_actual

        # Calcular ganancia actual
        ganancia_pct = (precio_actual - self.precio_entrada) / self.precio_entrada * 100
        ganancia_usd = self.capital_usado * (ganancia_pct / 100)

        # ── ¿Se tocó el Stop Loss actual? ──
        if precio_actual <= self.sl_actual:
            return self._cerrar("TRAILING_STOP" if self.fase > 1 else "STOP_LOSS",
                                precio_actual, ganancia_usd)

        # ── ¿Se tocó el Take Profit? ──
        if precio_actual >= self.tp_actual:
            return self._cerrar("TAKE_PROFIT", precio_actual, ganancia_usd)

        # ── Actualizar SL según la fase ──
        sl_anterior = self.sl_actual
        self._actualizar_fase(precio_actual, ganancia_pct)

        if self.sl_actual != sl_anterior:
            self._registrar(precio_actual, f"SL_SUBIDO_FASE{self.fase}")
            print(f"[TrailingStop] SL subio: ${sl_anterior:,.2f} -> ${self.sl_actual:,.2f} (Fase {self.fase})")

        return {
            "estado"          : "ABIERTO",
            "sl_actual"       : round(self.sl_actual, 2),
            "sl_inicial"      : round(self.sl_inicial, 2),
            "tp_actual"       : round(self.tp_actual, 2),
            "precio_entrada"  : self.precio_entrada,
            "precio_actual"   : precio_actual,
            "precio_maximo"   : round(self.precio_maximo, 2),
            "ganancia_pct"    : round(ganancia_pct, 2),
            "ganancia_usd"    : round(ganancia_usd, 2),
            "fase"            : self.fase,
            "cerrar"          : False,
            "protegido"       : self.fase >= 2,  # True = ya no puedes perder
        }

    def _actualizar_fase(self, precio_actual: float, ganancia_pct: float):
        """Lógica de las 3 fases del trailing stop."""

        # ── FASE 1 -> FASE 2: Precio sube +0.7% ──
        if ganancia_pct >= 0.7 and self.fase == 1:
            self.sl_actual = self.precio_entrada        # Breakeven
            self.fase      = 2
            print(f"[TrailingStop] FASE 2 - SL en breakeven ${self.sl_actual:,.2f}")

        # ── FASE 2 -> FASE 3: Precio sube +1.3% ──
        elif ganancia_pct >= 1.3 and self.fase == 2:
            self.sl_actual = self.precio_entrada * 1.006  # +0.6% asegurado
            self.fase      = 3
            print(f"[TrailingStop] FASE 3 - SL asegura ganancia minima ${self.sl_actual:,.2f}")

        # ── FASE 3: Trailing dinámico (0.8% de distancia al máximo) ──
        elif self.fase == 3:
            nuevo_sl = self.precio_maximo * (1 - 0.8 / 100)
            if nuevo_sl > self.sl_actual:
                self.sl_actual = nuevo_sl

    def _cerrar(self, motivo: str, precio_actual: float, ganancia_usd: float) -> dict:
        ganancia_pct = (precio_actual - self.precio_entrada) / self.precio_entrada * 100
        duracion_min = int((datetime.now() - self.hora_inicio).total_seconds() / 60)

        signo = "+" if ganancia_usd >= 0 else ""
        print(f"[TrailingStop] Cerrando por {motivo} | {signo}${ganancia_usd:.2f} ({signo}{ganancia_pct:.2f}%)")

        return {
            "estado"         : motivo,
            "sl_actual"      : round(self.sl_actual, 2),
            "sl_inicial"     : round(self.sl_inicial, 2),
            "tp_actual"      : round(self.tp_actual, 2),
            "precio_entrada" : self.precio_entrada,
            "precio_actual"  : precio_actual,
            "precio_maximo"  : round(self.precio_maximo, 2),
            "ganancia_pct"   : round(ganancia_pct, 2),
            "ganancia_usd"   : round(ganancia_usd, 2),
            "fase_alcanzada" : self.fase,
            "duracion_min"   : duracion_min,
            "cerrar"         : True,
        }

    def _registrar(self, precio: float, evento: str):
        self.historial_sl.append({
            "hora"    : datetime.now().strftime("%H:%M:%S"),
            "precio"  : round(precio, 2),
            "sl"      : round(self.sl_actual, 2),
            "evento"  : evento,
        })

    def resumen(self) -> str:
        """Texto corto para incluir en emails."""
        return (
            f"Entrada: ${self.precio_entrada:,.2f} | "
            f"SL: ${self.sl_actual:,.2f} | "
            f"Máximo: ${self.precio_maximo:,.2f} | "
            f"Fase: {self.fase}"
        )


# ════════════════════════════════════════════
# TEST RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  TEST - TRAILING STOP DINAMICO")
    print("=" * 55)

    ts = TrailingStop(precio_entrada=65000.0, capital_usado=100.0)

    simulacion = [
        65100, 65300, 65600, 65800,    # Sube -> activa fase 2
        66000, 66300, 66500, 66800,    # Sube mas -> activa fase 3
        67000, 67200, 67100, 66900,    # Sigue subiendo, luego baja un poco
        66500,                          # Baja mas -> trailing lo detiene
    ]

    print(f"\n{'Precio':>10} {'SL':>10} {'Ganancia':>10} {'Fase':>6} {'Estado':>15}")
    print("-" * 55)

    for precio in simulacion:
        r = ts.actualizar(precio)
        signo = "+" if r["ganancia_usd"] >= 0 else ""
        print(
            f"${precio:>9,.0f} "
            f"${r['sl_actual']:>9,.0f} "
            f"{signo}${r['ganancia_usd']:>8.2f} "
            f"  Fase {r.get('fase', r.get('fase_alcanzada', 1))} "
            f"  {r['estado']:>12}"
        )
        if r["cerrar"]:
            print(f"\n[OK] Trade cerrado: {r['estado']} | Ganancia final: ${r['ganancia_usd']:.2f}")
            break

    print("=" * 55)
