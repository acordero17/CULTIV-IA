import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos

st.set_page_config(page_title="Cultiv-IA", layout="wide")

api_key = st.secrets["OPENWEATHER_API_KEY"]

# 🛡️ FIX SESSION STATE
if "ubicacion_data" in st.session_state:
    if not isinstance(st.session_state.ubicacion_data, dict):
        st.session_state.clear()

if "df_res" not in st.session_state:
    st.session_state.df_res = None

if "cluster" not in st.session_state:
    st.session_state.cluster = None

if "ubicacion_data" not in st.session_state:
    st.session_state.ubicacion_data = None

# 🎨 estilos
st.markdown("""<style>
.stApp {background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)),
url("https://images.unsplash.com/photo-1500382017468-9049fed747ef");background-size: cover;}
.block-container {background: rgba(0,0,0,0.5);padding: 2rem;border-radius: 16px;}
.card {background: rgba(255,255,255,0.08);padding: 15px;border-radius: 12px;margin-bottom: 15px;}
</style>""", unsafe_allow_html=True)

def limpiar_texto(texto):
    texto = texto.upper()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
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
    return {"suelo_arcilloso": 30, "suelo_arenoso": 30,
            "suelo_fertil": 50, "suelo_limitado": 10}

# 🌦️ clima actual
@st.cache_data(ttl=1800)
def obtener_forecast(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    data = requests.get(url, params=params, timeout=5).json()

    temps = [i["main"]["temp"] for i in data["list"]]
    lluvia = sum(i.get("rain", {}).get("3h", 0) for i in data["list"])

    return {"temp_avg": sum(temps)/len(temps), "precip_total": lluvia}

# 🌍 climatología NASA
@st.cache_data(ttl=86400)
def obtener_climatologia(lat, lon):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,PRECTOT",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": "20180101",
        "end": "20231231",
        "format": "JSON"
    }

    r = requests.get(url, params=params, timeout=15).json()
    p = r["properties"]["parameter"]

    temps = [v for v in p["T2M"].values() if v != -999]
    precip = [v for v in p["PRECTOT"].values() if v != -999]

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": sum(precip)
    }

# 📍 geocoding
@st.cache_data(ttl=3600)
def obtener_datos_ubicacion(ubicacion):
    url = "https://api.opencagedata.com/geocode/v1/json"
    params = {
        "q": ubicacion + ", Mexico",
        "key": st.secrets["OPENCAGE_API_KEY"],
        "countrycode": "mx",
        "limit": 1
    }
    data = requests.get(url, params=params).json()
    if not data["results"]:
        return None

    r = data["results"][0]
    return {
        "lat": r["geometry"]["lat"],
        "lon": r["geometry"]["lng"],
        "components": r["components"]
    }

def extraer_municipio(data):
    comp = data["components"]
    municipio = comp.get("city") or comp.get("town") or comp.get("county")
    estado = comp.get("state")
    return municipio, estado

# UI
st.title("🌱 Cultiv-IA")
ubicacion = st.text_input("📍 Ubicación", "Texcoco, México")

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)
    municipio, estado = extraer_municipio(data)

    lat, lon = data["lat"], data["lon"]

    forecast = obtener_forecast(lat, lon)
    clima = obtener_climatologia(lat, lon)
    suelo = obtener_suelo(municipio)

    # 🔥 mezcla inteligente
    temp_final = clima["temp_avg"] + (forecast["temp_avg"] - clima["temp_avg"]) * 0.3

    input_dict = {
        "temp_avg": temp_final,
        "temp_max": temp_final,
        "temp_min": temp_final,
        "precip_total": clima["precip_total"],
        "precip_avg": clima["precip_total"]/365,
        "nomestado": "MEXICO",
        "nomcicloproductivo": "PV",
        "nommodalidad": "RIEGO"
    }

    input_dict.update(suelo)

    df_res, cluster = recomendar_cultivos(input_dict)

    st.session_state.df_res = df_res
    st.session_state.cluster = cluster
    st.session_state.ubicacion_data = {
        "municipio": municipio,
        "estado": estado,
        "forecast": forecast,
        "clima": clima
    }

# RESULTADOS
if st.session_state.df_res is not None:

    data = st.session_state.ubicacion_data

    st.success(f"{data['municipio']}, {data['estado']}")

    col1, col2 = st.columns(2)
    col1.metric("🌍 Temp histórica", f"{data['clima']['temp_avg']:.1f} °C")
    col2.metric("🌦️ Temp actual", f"{data['forecast']['temp_avg']:.1f} °C")

    st.dataframe(st.session_state.df_res.head(5))
