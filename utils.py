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
# ⚙️ CONFIG TURBO
# =========================

N_BOOTSTRAPS = 30
TREE_SUBSAMPLE = 0.6

rng = np.random.default_rng(42)

# =========================
# 🔧 INPUT
# =========================

def preparar_input_modelo_batch(input_base):

    rows = []

    for cultivo in cultivos:
        row = input_base.copy()
        row["nomcultivo"] = cultivo
        rows.append(row)

    df = pd.DataFrame(rows)
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
# 🌱 TIPO CULTIVO
# =========================

def obtener_tipo_cultivo_batch():
    return dict(zip(df_tipos["nomcultivo"], df_tipos["tipo_cultivo"]))


# =========================
# 🌍 CLUSTER
# =========================

def obtener_cluster(input_base):
    df = preparar_input_cluster(input_base)
    df_scaled = scaler_cluster.transform(df)
    return model_cluster.predict(df_scaled)[0]


# =========================
# 🧠 BOOTSTRAP CONTROLADO
# =========================

def bootstrap_predictions(df):

    n_trees = len(model_reg.estimators_)
    trees = model_reg.estimators_

    # 🔥 subset de árboles
    n_sub = int(n_trees * TREE_SUBSAMPLE)
    tree_idx = rng.choice(n_trees, n_sub, replace=False)
    selected_trees = [trees[i] for i in tree_idx]

    preds_boot = []

    for _ in range(N_BOOTSTRAPS):

        sample_idx = rng.choice(len(selected_trees), len(selected_trees), replace=True)
        trees_sample = [selected_trees[i] for i in sample_idx]

        preds = np.mean(
            [tree.predict(df) for tree in trees_sample],
            axis=0
        )

        preds_boot.append(preds)

    preds_boot = np.array(preds_boot)

    mean = preds_boot.mean(axis=0)

    # intervalos
    low = np.percentile(preds_boot, 15, axis=0)
    high = np.percentile(preds_boot, 85, axis=0)

    # regularización
    width = high - low
    max_width = np.maximum(mean * 0.8, 10)

    high = np.minimum(high, mean + max_width / 2)
    low = np.maximum(low, mean - max_width / 2)

    return mean, low, high


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
# 🚀 MAIN
# =========================

def recomendar_cultivos(input_base, top_n=None):

    df = preparar_input_modelo_batch(input_base)

    mean, low, high = bootstrap_predictions(df)

    riesgo = high - low
    score = mean - riesgo

    tipos = obtener_tipo_cultivo_batch()

    resultados = pd.DataFrame({
        "cultivo": cultivos,
        "tipo_cultivo": [tipos.get(c, "otro") for c in cultivos],
        "rendimiento": mean,
        "low": low,
        "high": high,
        "riesgo": riesgo,
        "score": score
    })

    resultados["clasificacion"] = resultados["rendimiento"].apply(clasificar_rendimiento)

    cluster = obtener_cluster(input_base)
    resultados["cluster"] = cluster

    resultados = resultados.sort_values(by="score", ascending=False)

    if top_n:
        resultados = resultados.head(top_n)

    return resultados, cluster
