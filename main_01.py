import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import (
    recomendar_cultivos,
    obtener_descripcion_cluster
)

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

# 🌦️ CLIMA ACTUAL REAL
@st.cache_data(ttl=1800)
def obtener_clima_actual(lat, lon):

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }

    data = requests.get(url, params=params, timeout=5).json()

    return {
        "temp": data["main"]["temp"],
        "precip": data.get("rain", {}).get("1h", 0)
    }

# 🌍 NASA
@st.cache_data(ttl=86400)
def obtener_climatologia(lat, lon):

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    params = {
        "parameters": "T2M,PRECTOTCORR",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": "20180101",
        "end": "20231231",
        "format": "JSON"
    }

    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        return None

    data = response.json()

    if "properties" not in data:
        return None

    p = data["properties"].get("parameter", {})

    if "T2M" not in p:
        return None

    temps = [v for v in p["T2M"].values() if v != -999]

    precip = None
    for key in ["PRECTOTCORR", "PRECTOT", "PRECTOT_LAND"]:
        if key in p:
            precip = [v for v in p[key].values() if v != -999]
            break

    if precip is None:
        return None

    temp_avg = sum(temps) / len(temps)
    precip_total = sum(precip) / (len(precip) / 365)

    return {
        "temp_avg": temp_avg,
        "precip_total": precip_total,
    }

# 📍 GEOCODING
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
# HEADER
# =========================

col1, col2 = st.columns([1, 5])

with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/2909/2909762.png", width=80)

with col2:
    st.title("🌱 Cultiv-IA")
    st.caption("Recomendaciones inteligentes para el campo")

# =========================
# INPUT
# =========================

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

    lat = data["lat"]
    lon = data["lon"]

    status.info("🌦️ Clima actual...")
    actual = obtener_clima_actual(lat, lon)

    status.info("🌍 Clima histórico...")
    clima = obtener_climatologia(lat, lon)

    if clima is None:
        st.warning("Fallback clima actual")
        clima = {
            "temp_avg": actual["temp"],
            "precip_total": actual["precip"] * 365
        }

    status.info("🌱 Suelo...")
    suelo = obtener_suelo(municipio)

    status.info("🧠 Modelo...")

    temp_final = clima["temp_avg"] + (actual["temp"] - clima["temp_avg"]) * 0.3

    input_dict = {
        "temp_avg": temp_final,
        "temp_max": temp_final,
        "temp_min": temp_final,
        "precip_total": clima["precip_total"],
        "precip_avg": clima["precip_total"] / 365,
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
        "actual": actual,
        "clima": clima,
        "input_dict": input_dict
    }

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    data = st.session_state.ubicacion_data
    df_res = st.session_state.df_res
    cluster = st.session_state.cluster

    actual = data.get("actual")
    clima = data.get("clima")

    st.success(f"{data['municipio']}, {data['estado']}")

    # 🌦️ ACTUAL
    st.subheader("🌦️ Condición actual")
    col1, col2 = st.columns(2)
    col1.metric("🌡️ Temperatura actual", f"{actual['temp']:.1f} °C")
    col2.metric("🌧️ Lluvia actual", f"{actual['precip']:.1f} mm")

    # 🌍 HISTÓRICO
    st.subheader("🌍 Climatología histórica (2018–2023)")
    col1, col2 = st.columns(2)
    col1.metric("🌡️ Temp promedio", f"{clima['temp_avg']:.1f} °C")
    col2.metric("🌧️ Precipitación anual", f"{clima['precip_total']:.0f} mm")

    # 🧠 CLUSTER (TU MAPPING)
    st.subheader("🧠 Tipo de municipio")
    desc = obtener_descripcion_cluster(cluster)

    st.markdown(f"""
    <div class="card">
        <p>{desc}</p>
    </div>
    """, unsafe_allow_html=True)

    # 🎛️ SELECTOR
    st.subheader("📊 Ordenar por")

    opcion = st.radio("", ["Score", "Rendimiento"], horizontal=True)

    if opcion == "Score":
        df_res = df_res.sort_values("score", ascending=False)
    else:
        df_res = df_res.sort_values("rendimiento", ascending=False)

    # 🌱 RESULTADOS
    st.subheader("🌱 Mejores cultivos")

    top5 = df_res.head(5)

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        st.markdown(f"""
        <div class="card">
            <h3>#{i} 🌱 {row['cultivo']}</h3>
            <p><b>Tipo:</b> {row['tipo_cultivo']} | <b>Clasificación:</b> {row['clasificacion']}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        col1.metric("📈 Rendimiento (ton/ha)", f"{row['rendimiento']:.1f}")
        col2.metric("⚠️ Riesgo", f"{row['riesgo']:.1f}")
        col3.metric("🧠 Score", f"{row['score']:.1f}")

        st.caption(f"Rango: {row['low']:.1f} – {row['high']:.1f}")

    # 🔬 WHAT IF
    st.subheader("🔬 What-if")

    cultivo_sel = st.selectbox("Cultivo", df_res["cultivo"].values)

    temp_delta = st.slider("Temperatura (°C)", -5.0, 5.0, 0.0)
    precip_delta = st.slider("Precipitación (%)", -50, 50, 0)

    if st.button("Simular"):

        input_mod = data["input_dict"].copy()

        input_mod["temp_avg"] += temp_delta
        input_mod["temp_max"] += temp_delta
        input_mod["temp_min"] += temp_delta
        input_mod["precip_total"] *= (1 + precip_delta / 100)

        df_new, _ = recomendar_cultivos(input_mod)

        row_new = df_new[df_new["cultivo"] == cultivo_sel].iloc[0]

        st.markdown("### Resultado")

        col1, col2, col3 = st.columns(3)
        col1.metric("Rendimiento", f"{row_new['rendimiento']:.1f}")
        col2.metric("Riesgo", f"{row_new['riesgo']:.1f}")
        col3.metric("Score", f"{row_new['score']:.1f}")

    # RESET
    if st.button("🔄 Probar otra ubicación"):
        st.session_state.clear()
        st.rerun()
