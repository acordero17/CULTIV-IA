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

def preparar_input_modelo_batch(input_base, municipio):

    cultivos_validos = obtener_cultivos_municipio(municipio)

    rows = []

    for cultivo in cultivos_validos:
        row = input_base.copy()
        row["nomcultivo"] = cultivo
        rows.append(row)

    df = pd.DataFrame(rows)
    df = pd.get_dummies(df)
    df = df.reindex(columns=features_modelo, fill_value=0)

    return df, cultivos_validos


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

def recomendar_cultivos(input_base, municipio, top_n=None):

    df, cultivos_validos = preparar_input_modelo_batch(input_base, municipio)

    mean, low, high = bootstrap_predictions(df)

    riesgo = high - low
    score = mean - riesgo

    tipos = obtener_tipo_cultivo_batch()

    resultados = pd.DataFrame({
        "cultivo": cultivos_validos,  # 🔥 importante
        "tipo_cultivo": [tipos.get(c, "otro") for c in cultivos_validos],
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
df_hist = pd.read_csv("modelos/filtro.csv")

def limpiar_texto(texto):
    import unicodedata
    texto = texto.upper()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto.strip()

df_hist["municipio_clean"] = df_hist["municipio"].apply(limpiar_texto)
def obtener_cultivos_municipio(municipio):

    m = limpiar_texto(municipio)

    cults = df_hist[df_hist["municipio_clean"] == m]["cultivo"].unique()

    if len(cults) == 0:
        return cultivos  # fallback 🔥

    return cults
import pandas as pd

def cargar_costos(path="modelos/costos.csv"):
    return pd.read_csv(path)
