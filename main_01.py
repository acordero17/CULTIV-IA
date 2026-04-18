import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos

st.set_page_config(page_title="Cultiv-IA", layout="wide")

api_key = st.secrets["OPENWEATHER_API_KEY"]

# =========================
# SESSION STATE
# =========================

if "df_res" not in st.session_state:
    st.session_state.df_res = None

if "cluster" not in st.session_state:
    st.session_state.cluster = None

if "ubicacion_data" not in st.session_state:
    st.session_state.ubicacion_data = None

# =========================
# FUNCIONES
# =========================

def limpiar_texto(texto):
    texto = texto.upper()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto.strip()


@st.cache_data
def cargar_suelos():
    df = pd.read_csv("modelos/suelos.csv")
    df["municipio_clean"] = df["municipio"].apply(limpiar_texto)
    return df


df_suelos = cargar_suelos()


@st.cache_data
def obtener_suelo(municipio):
    m = limpiar_texto(municipio)
    row = df_suelos[df_suelos["municipio_clean"].str.contains(m, na=False)]

    if len(row) > 0:
        row = row.iloc[0]
        return {
            "suelo_arcilloso": row["suelo_arcilloso"],
            "suelo_arenoso": row["suelo_arenoso"],
            "suelo_fertil": row["suelo_fertil"],
            "suelo_limitado": row["suelo_limitado"],
        }

    return {
        "suelo_arcilloso": 30,
        "suelo_arenoso": 30,
        "suelo_fertil": 50,
        "suelo_limitado": 10,
    }


@st.cache_data(ttl=1800)
def obtener_forecast(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }

    data = requests.get(url, params=params, timeout=5).json()

    temps = []
    lluvia_total = 0

    for item in data["list"]:
        temps.append(item["main"]["temp"])
        lluvia_total += item.get("rain", {}).get("3h", 0)

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": lluvia_total,
    }


# 🔥 NUEVO: OpenCage
@st.cache_data(ttl=3600)
def obtener_datos_ubicacion(ubicacion):

    url = "https://api.opencagedata.com/geocode/v1/json"

    params = {
        "q": ubicacion + ", Mexico",
        "key": st.secrets["OPENCAGE_API_KEY"],
        "countrycode": "mx",
        "limit": 1,
        "no_annotations": 1
    }

    response = requests.get(url, params=params, timeout=5)

    if response.status_code != 200:
        st.error("Error en geocoding")
        st.write(response.text)
        return None

    data = response.json()

    if not data.get("results"):
        return None

    result = data["results"][0]

    return {
        "lat": float(result["geometry"]["lat"]),
        "lon": float(result["geometry"]["lng"]),
        "components": result["components"]
    }


def extraer_municipio(data):
    comp = data["components"]

    municipio = (
        comp.get("city") or
        comp.get("town") or
        comp.get("village") or
        comp.get("county")
    )

    estado = comp.get("state")

    return municipio, estado


# =========================
# UI
# =========================

st.title("🌱 Cultiv-IA")

ubicacion = st.text_input("📍 Ubicación", "Texcoco, México")

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)

    if data is None:
        st.error("No se encontró la ubicación")
        st.stop()

    municipio, estado = extraer_municipio(data)

    lat = data["lat"]
    lon = data["lon"]

    forecast = obtener_forecast(lat, lon)
    suelo = obtener_suelo(municipio)

    precip_total = forecast["precip_total"] * 50
    precip_avg = precip_total / 365

    input_dict = {
        "temp_avg": forecast["temp_avg"],
        "temp_max": forecast["temp_avg"],
        "temp_min": forecast["temp_avg"],
        "precip_total": precip_total,
        "precip_avg": precip_avg,
        "nomestado": "MEXICO",
        "nomcicloproductivo": "PV",
        "nommodalidad": "RIEGO"
    }

    input_dict.update(suelo)

    df_res, cluster = recomendar_cultivos(input_dict)

    st.success(f"{municipio}, {estado}")
    st.dataframe(df_res.head(5))
