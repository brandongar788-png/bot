# ============================================================
#   BOT DE TRADING — GESTOR DE RIESGO DINÁMICO
#   gestor_riesgo.py
#   Ajusta el capital y el stop loss según el rendimiento
# ============================================================

import config
from historial import leer_estadisticas, leer_del_dia
from indicadores import calcular_atr


class GestorRiesgo:

    def __init__(self):
        self.perdida_maxima_dia = 1.5   # Máx pérdida diaria: 1.5% del capital = $15 de $1000. Protección máxima.
        self.racha_actual       = 0     # + ganando, - perdiendo

    def calcular_capital_trade(self, capital_total: float) -> float:
        """
        Ajusta el capital según la racha actual.
        Ganando seguido → sube capital
        Perdiendo seguido → baja capital
        """
        stats = leer_estadisticas()
        trades_hoy = leer_del_dia()

        # Calcular racha del día
        racha = 0
        for t in reversed(trades_hoy[-5:]):
            if float(t.get("ganancia", 0)) > 0:
                racha += 1
            else:
                racha -= 1

        # Ajustar capital según racha
        if racha >= 3:
            pct = 0.30    # Racha ganadora → más capital (30% = $300 de $1000)
        elif racha >= 1:
            pct = 0.25    # Buena racha → 25%
        elif racha == 0:
            pct = 0.20    # Neutro → capital base 20% = $200
        elif racha >= -1:
            pct = 0.12    # Una pérdida → reducir bastante
        else:
            pct = 0.08    # Racha perdedora → mínimo defensivo

        capital = round(capital_total * pct, 2)
        print(f"[Riesgo] Racha: {racha:+d} | Capital trade: ${capital} ({pct*100:.0f}%)")
        return capital

    def calcular_sl_dinamico(self, precio: float, velas_high: list,
                              velas_low: list, velas_close: list) -> float:
        """
        Stop Loss basado en ATR (volatilidad real del mercado).
        Días volátiles = SL más amplio
        Días tranquilos = SL más ajustado
        """
        atr = calcular_atr(velas_high, velas_low, velas_close)

        if atr == 0:
            return precio * (1 - config.STOP_LOSS_PCT / 100)

        # SL = 1.5x ATR por debajo del precio
        sl = precio - (atr * 1.5)
        sl_pct = (precio - sl) / precio * 100

        # No dejar que el SL sea menor al 0.5% ni mayor al 1.2%
        sl_pct = max(0.5, min(1.2, sl_pct))
        sl_final = precio * (1 - sl_pct / 100)

        print(f"[Riesgo] ATR: ${atr:.0f} | SL dinámico: ${sl_final:,.2f} ({sl_pct:.1f}%)")
        return round(sl_final, 2)

    def calcular_tp_dinamico(self, precio: float, velas_high: list,
                              velas_low: list, velas_close: list) -> float:
        """
        Take Profit basado en ATR (volatilidad real del mercado).
        Mercado volátil = TP más amplio.
        Mercado lento/plano = TP más corto para salir rápido con ganancias.
        """
        atr = calcular_atr(velas_high, velas_low, velas_close)

        if atr == 0:
            return config.TAKE_PROFIT_PCT

        # TP = 2.0x ATR por encima del precio, convertido a porcentaje
        tp_pct = (atr * 2.0) / precio * 100

        # No dejar que el TP sea menor a 0.7% ni mayor a 2.5%
        tp_pct = max(0.7, min(2.5, tp_pct))

        print(f"[Riesgo] ATR: ${atr:.0f} | TP dinámico calculado: {tp_pct:.2f}%")
        return round(tp_pct, 2)

    def verificar_perdida_maxima_dia(self, capital_total: float) -> bool:
        """
        Retorna True si se debe pausar por pérdida máxima del día.
        """
        trades_hoy = leer_del_dia()
        perdida_hoy = sum(
            float(t.get("ganancia", 0))
            for t in trades_hoy
            if float(t.get("ganancia", 0)) < 0
        )
        perdida_pct = abs(perdida_hoy) / capital_total * 100

        if perdida_pct >= self.perdida_maxima_dia:
            print(f"[Riesgo] 🛑 Pérdida máxima alcanzada: {perdida_pct:.1f}% — pausando hasta mañana")
            return True
        return False
