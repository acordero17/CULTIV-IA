import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos

# =========================
# CONFIG
# =========================

st.set_page_config(page_title="Cultiv-IA", layout="wide")

api_key = st.secrets["OPENWEATHER_API_KEY"]

# =========================
# 🛡️ SESSION STATE ROBUSTO
# =========================

if "ubicacion_data" in st.session_state:
    if not isinstance(st.session_state.ubicacion_data, dict):
        st.session_state.clear()

if "df_res" not in st.session_state:
    st.session_state.df_res = None

if "cluster" not in st.session_state:
    st.session_state.cluster = None

if "ubicacion_data" not in st.session_state:
    st.session_state.ubicacion_data = None

# =========================
# 🎨 ESTILOS
# =========================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)),
    url("https://images.unsplash.com/photo-1500382017468-9049fed747ef");
    background-size: cover;
}
.block-container {
    background: rgba(0,0,0,0.5);
    padding: 2rem;
    border-radius: 16px;
}
.card {
    background: rgba(255,255,255,0.08);
    padding: 15px;
    border-radius: 12px;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

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

# 🌦️ clima actual
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

    temps = [i["main"]["temp"] for i in data["list"]]
    lluvia = sum(i.get("rain", {}).get("3h", 0) for i in data["list"])

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": lluvia
    }

# 🌍 NASA climatología (ROBUSTA)
@st.cache_data(ttl=86400)
def obtener_climatologia(lat, lon):

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    params = {
        "parameters": "T2M,PRECTOTCORR,PRECTOT,PRECTOT_LAND",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": "20180101",
        "end": "20231231",
        "format": "JSON"
    }

    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        st.error("Error NASA POWER")
        return None

    data = response.json()
    p = data["properties"]["parameter"]

    # temperatura
    temps = [v for v in p.get("T2M", {}).values() if v != -999]

    # precipitación dinámica
    precip_key = None
    for key in ["PRECTOTCORR", "PRECTOT", "PRECTOT_LAND"]:
        if key in p:
            precip_key = key
            break

    if precip_key is None:
        st.error("No se encontró precipitación en NASA")
        return None

    precip = [v for v in p[precip_key].values() if v != -999]

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": sum(precip),
        "precip_source": precip_key
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

    if not data.get("results"):
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

# =========================
# UI
# =========================

st.title("🌱 Cultiv-IA")
st.caption("Ejemplo: Texcoco, Estado de México")

ubicacion = st.text_input("📍 Ubicación", "Texcoco, México")

# =========================
# BOTÓN
# =========================

if st.button("Analizar"):

    status = st.empty()

    status.info("📍 Buscando ubicación...")
    data = obtener_datos_ubicacion(ubicacion)

    if data is None:
        st.error("No se encontró la ubicación")
        st.stop()

    municipio, estado = extraer_municipio(data)

    lat, lon = data["lat"], data["lon"]

    status.info("🌦️ Clima actual...")
    forecast = obtener_forecast(lat, lon)

    status.info("🌍 Clima histórico...")
    clima = obtener_climatologia(lat, lon)

    status.info("🌱 Suelo...")
    suelo = obtener_suelo(municipio)

    status.info("🧠 Modelo...")

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

    status.empty()

    st.session_state.df_res = df_res
    st.session_state.cluster = cluster
    st.session_state.ubicacion_data = {
        "municipio": municipio,
        "estado": estado,
        "forecast": forecast,
        "clima": clima,
        "input_dict": input_dict
    }

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    data = st.session_state.ubicacion_data

    if "clima" not in data:
        st.session_state.clear()
        st.rerun()

    df_res = st.session_state.df_res

    st.success(f"{data['municipio']}, {data['estado']}")

    # 📊 condiciones
    st.subheader("📊 Condiciones")

    col1, col2, col3 = st.columns(3)
    col1.metric("🌍 Temp histórica", f"{data['clima']['temp_avg']:.1f} °C")
    col2.metric("🌦️ Temp actual", f"{data['forecast']['temp_avg']:.1f} °C")
    col3.metric("🌧️ Precipitación", f"{data['clima']['precip_total']:.0f} mm")

    st.caption(f"Fuente precipitación: {data['clima']['precip_source']}")

    # 📈 resultados
    top5 = df_res.head(5)

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        st.markdown(f"""
        <div class="card">
            <h3>#{i} 🌱 {row['cultivo']}</h3>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Rendimiento (ton/ha)", f"{row['rendimiento']:.1f}")
        c2.metric("⚠️ Riesgo", f"{row['riesgo']:.1f}")
        c3.metric("🧠 Score", f"{row['score']:.1f}")

    # 🔄 reset
    if st.button("🔄 Probar otra ubicación"):
        st.session_state.clear()
        st.rerun()
