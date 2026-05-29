# ============================================================
#   BOT DE TRADING — CEREBRO DE IA HÍBRIDO (ML + DL)
#   Archivo: ml_dl_hybrid.py
#   Descripción: Implementa modelos LSTM (PyTorch) y XGBoost 
#                para predicción de tendencias y éxito de trades.
#                Diseñado y optimizado para ejecutarse en CPU (8GB RAM).
# ============================================================

import os
import json
import numpy as np
import pandas as pd
import config

# Importamos las librerías de IA con control de errores por si aún se están instalando
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb
    IA_DISPONIBLE = True
except ImportError:
    IA_DISPONIBLE = False


# ════════════════════════════════════════════
# 1. DEEP LEARNING: MODELO LSTM (PyTorch CPU)
# ════════════════════════════════════════════

class LSTMNet(nn.Module):
    """
    Red Neuronal LSTM ultra-ligera.
    Procesa secuencias de tiempo de velas de BTC.
    """
    def __init__(self, input_dim=2, hidden_dim=64, num_layers=2, output_dim=1):
        super(LSTMNet, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # Capa LSTM optimizada para CPU
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        # Capa de salida lineal para clasificación binaria
        self.fc = nn.Linear(hidden_dim, output_dim)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # Inicializar estados ocultos
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).to(x.device)
        
        # Propagación hacia adelante
        out, _ = self.lstm(x, (h0, c0))
        # Tomar la salida del último paso temporal de la secuencia
        out = self.fc(out[:, -1, :])
        return self.sigmoid(out)


class LSTMPredictor:
    """
    Manejador del modelo LSTM para predecir la tendencia del precio de BTC.
    """
    def __init__(self, secuencia_velas=30):
        self.secuencia_velas = secuencia_velas
        self.modelo = None
        self.scaler = StandardScaler()
        self.ruta_modelo = "data/modelo_lstm.pth"
        
        if IA_DISPONIBLE:
            self.modelo = LSTMNet(input_dim=2, hidden_dim=64, num_layers=2)
            self.cargar_modelo()

    def entrenar(self, df_velas: pd.DataFrame, epocas=15, lr=0.01):
        """
        Entrena el modelo LSTM con datos secuenciales de velas.
        df_velas debe tener al menos: 'cierre', 'volumen'
        """
        if not IA_DISPONIBLE or len(df_velas) < self.secuencia_velas + 10:
            print("[LSTM] ⚠️ No hay suficientes datos de velas para entrenar el LSTM.")
            return False

        print("[LSTM] 🧠 Entrenando Red Neuronal en CPU...")
        
        # Preprocesar datos
        features = df_velas[['cierre', 'volumen']].values
        # Escalar datos para mejor convergencia del LSTM
        features_escalados = self.scaler.fit_transform(features)
        
        X, y = [], []
        for i in range(len(features_escalados) - self.secuencia_velas):
            X.append(features_escalados[i : i + self.secuencia_velas])
            # Etiqueta: 1 si el precio de cierre futuro (por ejemplo, 4 velas después) sube
            precio_futuro = df_velas['cierre'].iloc[i + self.secuencia_velas]
            precio_actual = df_velas['cierre'].iloc[i + self.secuencia_velas - 1]
            y.append(1.0 if precio_futuro > precio_actual else 0.0)

        X = torch.FloatTensor(np.array(X))
        y = torch.FloatTensor(np.array(y)).unsqueeze(1)

        # Configurar entrenamiento
        self.modelo.train()
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.modelo.parameters(), lr=lr)

        # Bucle de entrenamiento ligero (pocas épocas, CPU friendly)
        for epoch in range(epocas):
            optimizer.zero_grad()
            outputs = self.modelo(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 5 == 0:
                print(f"[LSTM] Epoca [{epoch+1}/{epocas}] - Loss: {loss.item():.4f}")

        self.guardar_modelo()
        print("[LSTM] OK: Modelo entrenado con exito.")
        return True

    def predecir_tendencia(self, ultimas_velas: list) -> float:
        """
        Toma una lista de las últimas velas y predice si la tendencia es ALCISTA.
        Retorna la probabilidad (0.0 a 1.0).
        """
        if not IA_DISPONIBLE or self.modelo is None:
            return 0.5

        try:
            if len(ultimas_velas) < self.secuencia_velas:
                return 0.5

            # Tomar exactamente las velas requeridas
            datos = np.array(ultimas_velas[-self.secuencia_velas:])
            
            # Si el scaler no ha sido ajustado (fit) aún, hacemos un fit rápido
            if not hasattr(self.scaler, "mean_"):
                datos_escalados = self.scaler.fit_transform(datos)
            else:
                datos_escalados = self.scaler.transform(datos)
            
            x_input = torch.FloatTensor(datos_escalados).unsqueeze(0)  # Agregar dimensión de batch
            
            self.modelo.eval()
            with torch.no_grad():
                probabilidad = self.modelo(x_input).item()
            return probabilidad
        except Exception as e:
            print(f"[LSTM] AVISO: Error en prediccion: {e}")
            return 0.5

    def guardar_modelo(self):
        os.makedirs("data", exist_ok=True)
        torch.save(self.modelo.state_dict(), self.ruta_modelo)

    def cargar_modelo(self):
        if os.path.exists(self.ruta_modelo):
            try:
                self.modelo.load_state_dict(torch.load(self.ruta_modelo, map_location=torch.device('cpu')))
                self.modelo.eval()
            except Exception as e:
                print(f"[LSTM] AVISO: Error al cargar modelo guardado: {e}")



# ════════════════════════════════════════════
# 2. MACHINE LEARNING: CLASIFICADOR XGBOOST
# ════════════════════════════════════════════

class XGBoostPredictor:
    """
    Predice la probabilidad de éxito de un trade basado en métricas puntuales del mercado.
    """
    def __init__(self):
        self.modelo = None
        self.ruta_modelo = "data/modelo_xgboost.json"
        
        if IA_DISPONIBLE:
            # XGBoost con hiperparámetros ultra-regulares para evitar sobreajuste en CPU
            self.modelo = xgb.XGBClassifier(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.08,
                objective='binary:logistic',
                eval_metric='logloss',
                random_state=42
            )
            self.cargar_modelo()

    def entrenar(self, df_trades: pd.DataFrame):
        """
        Entrena el modelo XGBoost basándose en el historial de trades pasados.
        df_trades debe tener columnas numéricas del estado del mercado y una columna 'ganancia'.
        """
        if not IA_DISPONIBLE or len(df_trades) < 10:
            print("[XGBoost] ⚠️ No hay suficientes trades históricos para entrenar XGBoost (mínimo 10).")
            return False

        print(f"[XGBoost] 🧠 Entrenando clasificador con {len(df_trades)} registros...")
        
        # Definir X (features) e y (target)
        features_columnas = ['rsi', 'score_tecnico', 'fear_greed', 'imbalance_libro', 'ballenas_neto',
                             'cambio_vela_1', 'cambio_vela_2', 'cambio_vela_3',
                             'distancia_soporte', 'atr_relativo']
        
        # Asegurarnos de que las columnas existan
        for col in features_columnas:
            if col not in df_trades.columns:
                df_trades[col] = 50.0 if col == 'fear_greed' else 0.0

        X = df_trades[features_columnas].values
        # Target: 1 si el trade dio ganancias, 0 si dio pérdidas
        y = (df_trades['ganancia'].values > 0).astype(int)

        try:
            self.modelo.fit(X, y)
            self.guardar_modelo()
            print("[XGBoost] ✅ Modelo entrenado correctamente.")
            return True
        except Exception as e:
            print(f"[XGBoost] ❌ Error en entrenamiento: {e}")
            return False

    def predecir_probabilidad(self, features: dict) -> float:
        """
        Calcula la probabilidad de que un trade sea exitoso dada una foto de indicadores.
        """
        if not IA_DISPONIBLE or self.modelo is None:
            return 0.5

        try:
            # Orden de features esperado
            valores = [
                float(features.get('rsi', 50.0)),
                float(features.get('score_tecnico', 50.0)),
                float(features.get('fear_greed', 50.0)),
                float(features.get('imbalance_libro', 1.0)),
                float(features.get('ballenas_neto', 0.0)),
                float(features.get('cambio_vela_1', 0.0)),
                float(features.get('cambio_vela_2', 0.0)),
                float(features.get('cambio_vela_3', 0.0)),
                float(features.get('distancia_soporte', 0.0)),
                float(features.get('atr_relativo', 0.0)),
            ]
            X_input = np.array([valores])
            
            # Predict_proba devuelve [[prob_loss, prob_win]]
            probabilidades = self.modelo.predict_proba(X_input)
            return float(probabilidades[0][1])  # Probabilidad de ganar
        except Exception:
            # Fallback en caso de que no esté entrenado del todo
            return 0.5

    def guardar_modelo(self):
        os.makedirs("data", exist_ok=True)
        self.modelo.save_model(self.ruta_modelo)

    def cargar_modelo(self):
        if os.path.exists(self.ruta_modelo):
            try:
                self.modelo.load_model(self.ruta_modelo)
            except Exception as e:
                print(f"[XGBoost] ⚠️ Error al cargar modelo guardado: {e}")

    def validar_precision(self) -> bool:
        """
        Si el XGBoost tiene menos del 55% de precisión
        en los últimos 20 trades, se desactiva temporalmente.
        """
        from historial import leer_todos
        trades = leer_todos()[-20:]

        if len(trades) < 20:
            return True  # Sin suficientes datos, dejar pasar

        correctos = 0
        for t in trades:
            ganancia   = float(t.get("ganancia", 0))
            prediccion = float(t.get("prob_xgboost", 0.5))
            if ganancia > 0 and prediccion >= 0.60:
                correctos += 1
            elif ganancia <= 0 and prediccion < 0.60:
                correctos += 1

        precision = correctos / len(trades)
        if precision < 0.55:
            print(f"[XGBoost] ⚠️ Precisión baja ({precision:.1%}) — desactivado temporalmente")
            return False

        print(f"[XGBoost] ✅ Precisión: {precision:.1%}")
        return True


# ════════════════════════════════════════════
# 3. COORDINADOR DE IA HÍBRIDO (HybridBrain)
# ════════════════════════════════════════════

class HybridBrain:
    """
    Coordinador maestro de IA que integra LSTM y XGBoost.
    Sirve como la interfaz única que usará main.py.
    """
    def __init__(self):
        self.lstm = LSTMPredictor()
        self.xgb = XGBoostPredictor()

    def evaluar_entrada(self, ultimas_velas: list, indicadores_actuales: dict) -> dict:
        """
        Ejecuta el veto híbrido:
        1. LSTM analiza la tendencia de la serie de precios.
        2. XGBoost estima la probabilidad de ganar basándose en los indicadores.
        """
        if not IA_DISPONIBLE:
            return {"aprobado": True, "motivo": "Librerías de IA no disponibles (Fallback técnico activado)"}

        # 1. Ejecutar predicción LSTM
        prob_tendencia = self.lstm.predecir_tendencia(ultimas_velas)
        es_alcista = prob_tendencia > 0.52

        # 2. Ejecutar predicción XGBoost
        prob_exito = self.xgb.predecir_probabilidad(indicadores_actuales)
        prob_exito_pct = prob_exito * 100

        # Umbrales
        umbral_xgb = getattr(config, "UMBRAL_PROBABILIDAD_XGB", 60.0)
        
        # Lógica de veto híbrido:
        # Aprobamos si: La probabilidad de éxito de XGBoost es buena Y la tendencia es alcista
        aprobado = (prob_exito_pct >= umbral_xgb) and es_alcista

        # Excepción: Si XGBoost da una probabilidad abrumadora (> 75%), aprobamos incluso si el LSTM es neutral
        if prob_exito_pct >= 75.0:
            aprobado = True

        motivo = f"IA Híbrida: XGBoost Prob: {prob_exito_pct:.1f}% (mín {umbral_xgb}%) | LSTM Tendencia: {'ALCISTA' if es_alcista else 'NEUTRAL/BAJISTA'} ({prob_tendencia:.2f})"
        
        return {
            "aprobado"      : aprobado,
            "prob_exito"    : prob_exito_pct,
            "prob_tendencia": prob_tendencia,
            "motivo"        : motivo
        }

    def entrenar_con_datos(self, df_velas: pd.DataFrame, df_trades: pd.DataFrame):
        """
        Entrena ambos modelos.
        """
        print("[IA Híbrida] 📊 Iniciando re-entrenamiento del cerebro híbrido...")
        ok_lstm = self.lstm.entrenar(df_velas)
        ok_xgb = self.xgb.entrenar(df_trades)
        
        return ok_lstm and ok_xgb


# ════════════════════════════════════════════
# TEST INTEGRIDAD RÁPIDO
# ════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  TEST - CEREBRO DE IA HIBRIDO")
    print("=" * 55)
    
    if not IA_DISPONIBLE:
        print("Warning: Las librerias de IA (torch, xgboost) aun no estan listas en el sistema.")
    else:
        print("OK: Entorno de IA listo. Probando inicializacion de componentes...")
        cerebro = HybridBrain()
        
        # Simular indicadores actuales de prueba
        test_indicators = {
            'rsi': 35.0,
            'score_tecnico': 75.0,
            'fear_greed': 20.0,
            'imbalance_libro': 1.6,
            'ballenas_neto': 45000.0
        }
        
        # Simular 30 velas de cierre y volumen (cierre, volumen)
        test_candles = [[65000 + i * 50, 1.2 + i * 0.1] for i in range(30)]
        
        decision = cerebro.evaluar_entrada(test_candles, test_indicators)
        print(f"Resultado del Test de Decision: {decision}")
    print("=" * 55)

