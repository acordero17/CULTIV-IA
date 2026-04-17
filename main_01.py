import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos
import os
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

# Obtener API key desde Streamlit Secrets
api_key = st.secrets["OPENWEATHER_API_KEY"]

load_dotenv()

api_key = os.getenv("OPENWEATHER_API_KEY")

# 🔥 carga tu dataset real
df_suelos = pd.read_csv("modelos/suelos.csv")

# =========================
# 🔧 LIMPIEZA TEXTO
# =========================

def limpiar_texto(texto):
    texto = texto.upper()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto.strip()

df_suelos["municipio_clean"] = df_suelos["municipio"].apply(limpiar_texto)

# =========================
# 🌱 SUELO
# =========================

def obtener_suelo(municipio):

    m = limpiar_texto(municipio)

    row = df_suelos[
        df_suelos["municipio_clean"].str.contains(m, na=False)
    ]

    if len(row) > 0:
        row = row.iloc[0]

        return {
            "suelo_arcilloso": row["suelo_arcilloso"],
            "suelo_arenoso": row["suelo_arenoso"],
            "suelo_fertil": row["suelo_fertil"],
            "suelo_limitado" : row["suelo_limitado"],
        }

    # fallback
    return {
        "suelo_arcilloso": 30,
        "suelo_arenoso": 30,
        "suelo_fertil": 50,
        "suelo_limitado": 10,
    }

# =========================
# 🌦️ FORECAST
# =========================

def obtener_forecast(lat, lon):

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric"
    }

    data = requests.get(url, params=params).json()

    temps, temps_min, temps_max = [], [], []
    lluvia_total = 0

    for item in data["list"]:
        temps.append(item["main"]["temp"])
        temps_min.append(item["main"]["temp_min"])
        temps_max.append(item["main"]["temp_max"])
        lluvia_total += item.get("rain", {}).get("3h", 0)

    return {
        "temp_avg": sum(temps)/len(temps),
        "temp_min_avg": sum(temps_min)/len(temps_min),
        "temp_max_avg": sum(temps_max)/len(temps_max),
        "precip_total": lluvia_total,
    }

# =========================
# 🌍 GEO
# =========================

def obtener_datos_ubicacion(ubicacion):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": ubicacion,
        "format": "json",
        "addressdetails": 1
    }

    headers = {"User-Agent": "cultiv-ia"}

    data = requests.get(url, params=params, headers=headers).json()

    return data[0] if data else None


def extraer_municipio(data):
    addr = data["address"]
    municipio = addr.get("city") or addr.get("town") or addr.get("county")
    estado = addr.get("state")
    return municipio, estado

# =========================
# UI
# =========================

st.title("🌱 Cultiv-IA")

ubicacion = st.text_input("📍 Ubicación", "Texcoco, México")

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)

    municipio, estado = extraer_municipio(data)

    lat = float(data["lat"])
    lon = float(data["lon"])

    st.success(f"{municipio}, {estado}")

    forecast = obtener_forecast(lat, lon)

    # 🔥 ajustar precipitación
    precip_total = forecast["precip_total"] * 50
    precip_avg = precip_total / 365

    # 🔥 suelo real
    suelo = obtener_suelo(municipio)

    # =========================
    # 🤖 INPUT
    # =========================

    input_dict = {
        "temp_avg": forecast["temp_avg"],
        "temp_max": forecast["temp_max_avg"],
        "temp_min": forecast["temp_min_avg"],
        "precip_total": precip_total,
        "precip_avg": precip_avg,
        "nomestado": "MEXICO",
        "nomcicloproductivo": "PV",
        "nommodalidad": "RIEGO"
    }

    input_dict.update(suelo)

    top5, cluster = recomendar_cultivos(input_dict, 5)

    # =========================
    # RESULTADOS
    # =========================

    cluster_map = {
        0: "Zona agrícola de alto potencial",
        1: "Zona productiva tecnificada",
        2: "Zona de bajo rendimiento por suelo",
        3: "Zona con suelo arcilloso",
        4: "Zona húmeda de bajo rendimiento"
    }

    st.subheader("🌍 Tipo de municipio")
    st.success(cluster_map.get(cluster, cluster))

    st.subheader("🌾 Top cultivos")

    for _, row in top5.iterrows():
        st.write(f"🌱 {row['cultivo']}")
        st.write(f"Tipo: {row['tipo_cultivo']}")
        st.write(f"Rendimiento: {row['rendimiento']:.2f}")
        st.write(f"Clasificación: {row['clasificacion']}")
        st.write("---")