# ============================================================
#   BOT DE TRADING — GESTOR DE IA
#   Archivo: ia_manager.py
#   Descripción: Maneja todas las llamadas a Groq (gratis).
#                Lo usan sentimiento.py y grafico_analizador.py
# ============================================================

from groq import Groq
import config
import time


class GestorIA:
    """
    Interfaz única para consultar a la IA con Groq (100% gratis).
    Usa Llama 3.3 70B, excelente para análisis de mercado.
    """

    def __init__(self):
        self.cliente  = Groq(api_key=config.GROQ_API_KEY)
        self.modelo   = "llama-3.3-70b-versatile"  # Gratis y muy capaz
        self.intentos = 3

    def preguntar(self, mensaje: str, sistema: str = "") -> str:
        """
        Envía una pregunta a la IA y devuelve la respuesta como texto.

        mensaje: Lo que quieres preguntarle
        sistema: Instrucciones de comportamiento para la IA
        """
        for intento in range(self.intentos):
            try:
                respuesta = self.cliente.chat.completions.create(
                    model    = self.modelo,
                    messages = [
                        {"role": "system", "content": sistema if sistema else "Eres un experto en trading de criptomonedas."},
                        {"role": "user",   "content": mensaje}
                    ],
                    max_tokens  = 800,
                    temperature = 0.3,
                )
                return respuesta.choices[0].message.content.strip()

            except Exception as e:
                error = str(e).lower()
                if "auth" in error or "api key" in error:
                    print("[IA] ❌ API Key de Groq inválida. Revisa GROQ_API_KEY en config.py")
                    return ""
                elif "rate" in error:
                    print(f"[IA] Rate limit — esperando 30s (intento {intento+1}/{self.intentos})")
                    time.sleep(30)
                else:
                    print(f"[IA] Error: {e} (intento {intento+1}/{self.intentos})")
                    time.sleep(5)

        print("[IA] ❌ No se pudo obtener respuesta tras 3 intentos.")
        return ""


# ════════════════════════════════════════════
# TEST RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    ia = GestorIA()
    respuesta = ia.preguntar("Responde solo con la palabra: OK")
    print(f"[IA] Test: {'OK Funciona' if 'OK' in respuesta else 'FALLO'}")
    print(f"[IA] Respuesta: {respuesta}")
