import pandas as pd
import numpy as np

# asumo que ya tienes:
# model_reg
# cultivos
# preparar_input_modelo
# obtener_tipo_cultivo
# clasificar_rendimiento
# obtener_cluster


def recomendar_cultivos_fast(input_base):

    rows = []

    for cultivo in cultivos:
        d = input_base.copy()
        d["nomcultivo"] = cultivo
        rows.append(d)

    df_all = pd.DataFrame(rows)

    # 🔥 UNA sola transformación
    df_model = preparar_input_modelo(df_all)

    # 🔥 predicción vectorizada
    preds = model_reg.predict(df_model)

    resultados = []

    for cultivo, pred in zip(cultivos, preds):
        resultados.append({
            "cultivo": cultivo,
            "tipo_cultivo": obtener_tipo_cultivo(cultivo),
            "rendimiento": float(pred),
            "score": float(pred),
            "clasificacion": clasificar_rendimiento(pred),
            "riesgo": 0,
            "low": pred,
            "high": pred
        })

    df_res = pd.DataFrame(resultados)

    return df_res.sort_values(by="rendimiento", ascending=False), obtener_cluster(input_base)


def predecir_con_incertidumbre(input_dict, cultivo):

    input_dict = input_dict.copy()
    input_dict["nomcultivo"] = cultivo

    df = preparar_input_modelo(pd.DataFrame([input_dict]))

    preds = [tree.predict(df)[0] for tree in model_reg.estimators_]

    mean = float(np.mean(preds))
    std = float(np.std(preds))

    return {
        "mean": mean,
        "low": max(0, mean - std),
        "high": mean + std,
        "riesgo": std
    }
