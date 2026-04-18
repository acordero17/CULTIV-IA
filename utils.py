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
# 🔧 INPUT MODELO
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

    # 🔥 alinear con scaler
    df = df[scaler_cluster.feature_names_in_]

    return df


# =========================
# 🌱 TIPO CULTIVO
# =========================

def obtener_tipo_cultivo(cultivo):
    row = df_tipos[df_tipos["nomcultivo"] == cultivo]
    if len(row) > 0:
        return row["tipo_cultivo"].values[0]
    return "otro"


# =========================
# 🌍 CLUSTER
# =========================

def obtener_cluster(input_base):
    df = preparar_input_cluster(input_base)
    df_scaled = scaler_cluster.transform(df)
    return model_cluster.predict(df_scaled)[0]


# =========================
# 🧠 CLASIFICACIÓN POR REGLAS
# =========================

def clasificar_rendimiento(r):
    if r > 70:
        return "alto"
    elif r > 40:
        return "medio"
    else:
        return "bajo"


# =========================
# 🚀 MAIN
# =========================

def recomendar_cultivos_fast(input_base):

    resultados = []

    cluster = obtener_cluster(input_base)

    for cultivo in cultivos:

        try:
            input_dict = input_base.copy()
            input_dict["nomcultivo"] = cultivo

            df = preparar_input_modelo(input_dict)

            pred = float(model_reg.predict(df)[0])

            resultados.append({
                "cultivo": cultivo,
                "tipo_cultivo": obtener_tipo_cultivo(cultivo),
                "rendimiento": pred,
                "score": pred,
                "clasificacion": clasificar_rendimiento(pred),
                "riesgo": 0,
                "low": pred,
                "high": pred,
                "cluster": cluster
            })

        except Exception as e:
            print(f"Error {cultivo}: {e}")

    df_res = pd.DataFrame(resultados)

    return df_res.sort_values(by="rendimiento", ascending=False), cluster
    
def predecir_cultivo(input_dict, cultivo):

    input_dict = input_dict.copy()
    input_dict["nomcultivo"] = cultivo

    df = preparar_input_modelo(input_dict)

    pred = model_reg.predict(df)[0]

    return float(pred)
def predecir_con_incertidumbre(input_dict, cultivo):

    import numpy as np

    input_dict = input_dict.copy()
    input_dict["nomcultivo"] = cultivo

    df = preparar_input_modelo(input_dict)

    # 🔥 usamos árboles directamente (rápido)
    preds = [tree.predict(df)[0] for tree in model_reg.estimators_]

    mean = float(np.mean(preds))
    std = float(np.std(preds))

    low = max(0, mean - std)
    high = mean + std

    return {
        "mean": mean,
        "low": low,
        "high": high,
        "riesgo": std
    }
