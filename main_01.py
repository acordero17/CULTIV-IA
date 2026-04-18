import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos

# =========================
# 🤖 OPENAI
# =========================

from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def preguntar_llm(prompt):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Eres un ingeniero agrónomo experto en México. Responde claro, práctico y profesional."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=300
    )

    return response.choices[0].message.content


# =========================
# CONFIG
# =========================

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

if "input_dict" not in st.session_state:
    st.session_state.input_dict = None

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

    try:
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            return None

        data = r.json()
        p = data["properties"]["parameter"]

        temps = [v for v in p["T2M"].values() if v != -999]

        precip = None
        for key in ["PRECTOTCORR", "PRECTOT", "PRECTOT_LAND"]:
            if key in p:
                precip = [v for v in p[key].values() if v != -999]
                break

        if precip is None:
            return None

        return {
            "temp_avg": sum(temps) / len(temps),
            "precip_total": sum(precip) / (len(precip) / 365)
        }

    except:
        return None

@st.cache_data(ttl=3600)
def obtener_datos_ubicacion(ubicacion):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": ubicacion,
        "format": "json",
        "addressdetails": 1
    }

    headers = {"User-Agent": "cultiv-ia"}

    data = requests.get(url, params=params, headers=headers, timeout=5).json()

    return data[0] if data else None

def extraer_municipio(data):
    addr = data["address"]
    municipio = addr.get("city") or addr.get("town") or addr.get("county")
    estado = addr.get("state")
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

    st.session_state.df_res = None

    with st.spinner("🌱 Analizando condiciones..."):

        data = obtener_datos_ubicacion(ubicacion)

        if data is None:
            st.error("No se pudo encontrar la ubicación")
            st.stop()

        municipio, estado = extraer_municipio(data)

        lat = float(data["lat"])
        lon = float(data["lon"])

        actual = obtener_clima_actual(lat, lon)
        clima = obtener_climatologia(lat, lon)

        if clima is None:
            clima = {
                "temp_avg": actual["temp"],
                "precip_total": actual["precip"] * 365
            }

        suelo = obtener_suelo(municipio)

        temp_final = clima["temp_avg"] + (actual["temp"] - clima["temp_avg"]) * 0.3

        precip_total = clima["precip_total"]
        precip_avg = precip_total / 365

        input_dict = {
            "temp_avg": temp_final,
            "temp_max": temp_final,
            "temp_min": temp_final,
            "precip_total": precip_total,
            "precip_avg": precip_avg,
            "nomestado": "MEXICO",
            "nomcicloproductivo": "PV",
            "nommodalidad": "RIEGO"
        }

        input_dict.update(suelo)

        df_res, cluster = recomendar_cultivos(input_dict)

        st.session_state.df_res = df_res
        st.session_state.cluster = cluster
        st.session_state.ubicacion_data = (municipio, estado, actual, clima)
        st.session_state.input_dict = input_dict

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    df_res = st.session_state.df_res
    cluster = st.session_state.cluster
    municipio, estado, actual, clima = st.session_state.ubicacion_data

    st.success(f"{municipio}, {estado}")

    st.subheader("🌦️ Condición actual")
    c1, c2 = st.columns(2)
    c1.metric("🌡️ Temperatura actual", f"{actual['temp']:.1f} °C")
    c2.metric("🌧️ Lluvia actual", f"{actual['precip']:.1f} mm")

    st.subheader("🌍 Climatología histórica (2018–2023)")
    c1, c2 = st.columns(2)
    c1.metric("🌡️ Temp promedio", f"{clima['temp_avg']:.1f} °C")
    c2.metric("🌧️ Precipitación anual", f"{clima['precip_total']:.0f} mm")

    st.subheader("🌍 Tipo de municipio")
    st.success(cluster)

    st.info("🧠 Score = rendimiento esperado - riesgo")

    top5 = df_res.head(5)

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        st.markdown(f"### {i}. {row['cultivo']}")
        st.write(f"Rendimiento: {row['rendimiento']:.1f} ton/ha")

    # =========================
    # 🧠 ASESOR
    # =========================

    st.markdown("---")
    st.subheader("🧠 Asesor agrícola")

    decision = st.radio(
        "¿Ya seleccionaste un cultivo?",
        ["❓ Necesito ayuda", "✅ Ya elegí"],
        horizontal=True
    )

    if decision == "❓ Necesito ayuda":

        if st.button("Ayúdame a decidir"):

            top = df_res.head(3)

            prompt = f"""
            Municipio: {municipio}

            Cultivos:
            {top[['cultivo','rendimiento','riesgo','score']].to_string()}

            Recomienda el mejor cultivo y explica por qué.
            """

            st.write(preguntar_llm(prompt))

    else:

        cultivo_final = st.selectbox("Selecciona cultivo", df_res["cultivo"])

        if st.button("Analizar cultivo"):

            row = df_res[df_res["cultivo"] == cultivo_final].iloc[0]

            prompt = f"""
            Cultivo: {cultivo_final}
            Temperatura: {actual['temp']}
            Precipitación: {clima['precip_total']}

            Explica condiciones óptimas, plagas y recomendaciones.
            """

            st.write(preguntar_llm(prompt))
