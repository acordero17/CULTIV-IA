import pandas as pd
import numpy as np
import joblib

# =========================
# 📦 MODELOS
# =========================

model_reg = joblib.load("modelos/modelo_regresion.pkl")
model_cluster = joblib.load("modelos/modelo_cluster.pkl")

scaler_cluster = joblib.load("modelos/scaler_cluster.pkl")

features_modelo = joblib.load("modelos/features.pkl")
features_cluster = joblib.load("modelos/features_cluster.pkl")

cultivos = joblib.load("modelos/cultivos.pkl")
df_tipos = pd.read_csv("modelos/tipos_cultivo.csv")

# =========================
# 🔧 INPUT
# =========================

def preparar_input_modelo(input_dict):
    df = pd.DataFrame([input_dict])
    df = pd.get_dummies(df)
    df = df.reindex(columns=features_modelo, fill_value=0)
    return df


def preparar_input_cluster(input_dict):
    df = pd.DataFrame([input_dict])
    df = pd.get_dummies(df)
    df = df.reindex(columns=features_cluster, fill_value=0)
    df = df[scaler_cluster.feature_names_in_]
    return df


# =========================
# 🌍 CLUSTER
# =========================

def obtener_cluster(input_base):
    df = preparar_input_cluster(input_base)
    df_scaled = scaler_cluster.transform(df)
    return model_cluster.predict(df_scaled)[0]


# =========================
# 🧠 CLASIFICACIÓN
# =========================

def clasificar_rendimiento(r):
    if r > 70:
        return "alto"
    elif r > 40:
        return "medio"
    else:
        return "bajo"


# =========================
# 🚀 RECOMENDACIÓN
# =========================

def recomendar_cultivos(input_base):

    resultados = []

    cluster = obtener_cluster(input_base)

    for cultivo in cultivos:

        input_dict = input_base.copy()
        input_dict["nomcultivo"] = cultivo

        df = preparar_input_modelo(input_dict)

        preds = np.array([tree.predict(df)[0] for tree in model_reg.estimators_])

        mean = float(np.mean(preds))
        low = float(np.percentile(preds, 15))
        high = float(np.percentile(preds, 85))

        riesgo = high - low
        score = mean - riesgo

        tipo_row = df_tipos[df_tipos["nomcultivo"] == cultivo]
        tipo = tipo_row["tipo_cultivo"].values[0] if len(tipo_row) else "otro"

        resultados.append({
            "cultivo": cultivo,
            "tipo_cultivo": tipo,
            "rendimiento": mean,
            "low": low,
            "high": high,
            "riesgo": riesgo,
            "score": score,
            "clasificacion": clasificar_rendimiento(mean),
            "cluster": cluster
        })

    df_res = pd.DataFrame(resultados).sort_values(by="score", ascending=False)

    return df_res, cluster


# =========================
# 🧪 WHAT IF
# =========================

def simular_cultivo(input_base, cultivo):

    input_dict = input_base.copy()
    input_dict["nomcultivo"] = cultivo

    df = preparar_input_modelo(input_dict)

    preds = np.array([tree.predict(df)[0] for tree in model_reg.estimators_])

    mean = float(np.mean(preds))
    low = float(np.percentile(preds, 15))
    high = float(np.percentile(preds, 85))

    riesgo = high - low
    score = mean - riesgo

    return {
        "rendimiento": mean,
        "low": low,
        "high": high,
        "riesgo": riesgo,
        "score": score
    }
