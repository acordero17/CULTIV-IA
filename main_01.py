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
                "content": """
Eres un ingeniero agrónomo experto en México.

Ayudas a productores a decidir qué cultivar usando:
- clima
- suelo
- rendimiento estimado
- riesgo

Responde:
- claro
- práctico
- sin tecnicismos innecesarios
- con recomendaciones accionables
"""
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

def obtener_suelo(municipio):
    m = limpiar_texto(municipio)
    row = df_suelos[df_suelos["municipio_clean"].str.contains(m, na=False)]

    if len(row) > 0:
        row = row.iloc[0]
        return row.to_dict()

    return {
        "suelo_arcilloso": 30,
        "suelo_arenoso": 30,
        "suelo_fertil": 50,
        "suelo_limitado": 10,
    }

def obtener_clima_actual(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    data = requests.get(url, params=params).json()

    return {
        "temp": data["main"]["temp"],
        "precip": data.get("rain", {}).get("1h", 0)
    }

def obtener_datos_ubicacion(ubicacion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": ubicacion, "format": "json", "addressdetails": 1}
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

# =========================
# ANALIZAR
# =========================

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)

    if data is None:
        st.error("No se encontró la ubicación")
        st.stop()

    municipio, estado = extraer_municipio(data)

    lat = float(data["lat"])
    lon = float(data["lon"])

    actual = obtener_clima_actual(lat, lon)
    suelo = obtener_suelo(municipio)

    input_dict = {
        "temp_avg": actual["temp"],
        "temp_max": actual["temp"],
        "temp_min": actual["temp"],
        "precip_total": actual["precip"] * 365,
        "precip_avg": actual["precip"],
        "nomestado": "MEXICO",
        "nomcicloproductivo": "PV",
        "nommodalidad": "RIEGO"
    }

    input_dict.update(suelo)

    df_res, cluster = recomendar_cultivos(input_dict)

    st.session_state.df_res = df_res
    st.session_state.cluster = cluster
    st.session_state.ubicacion_data = (municipio, estado, actual)


# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    df_res = st.session_state.df_res
    municipio, estado, actual = st.session_state.ubicacion_data

    st.success(f"{municipio}, {estado}")

    st.subheader("🌾 Mejores cultivos")

    for _, row in df_res.head(5).iterrows():
        st.write(f"{row['cultivo']} → {row['rendimiento']:.1f} ton/ha")

    # =========================
    # 🧠 ASESOR (AHORA SÍ FUNCIONA)
    # =========================

    st.markdown("---")
    st.subheader("🧠 Asesor agrícola")

    decision = st.radio(
        "¿Ya seleccionaste un cultivo?",
        ["❓ Necesito ayuda para decidir", "✅ Ya elegí un cultivo"],
        horizontal=True
    )

    # 👉 AYUDA
    if decision == "❓ Necesito ayuda para decidir":

        if st.button("🧠 Ayúdame a decidir"):

            top = df_res.head(3)

            prompt = f"""
Municipio: {municipio}, {estado}

Opciones:
{top[['cultivo','rendimiento','riesgo','score']].to_string()}

Recomienda el mejor cultivo y explica por qué.
Incluye riesgos y consejos prácticos.
"""

            st.write(preguntar_llm(prompt))

    # 👉 YA ELIGIÓ
    else:

        cultivo_sel = st.selectbox("🌱 ¿Qué cultivo elegiste?", df_res["cultivo"])

        if st.button("📘 Analizar cultivo"):

            row = df_res[df_res["cultivo"] == cultivo_sel].iloc[0]

            prompt = f"""
Cultivo: {cultivo_sel}
Municipio: {municipio}

Temperatura: {actual['temp']}
Precipitación: {actual['precip']}

Rendimiento estimado: {row['rendimiento']}
Riesgo: {row['riesgo']}

Explica:
- condiciones óptimas
- comparación con condiciones actuales
- plagas comunes
- recomendaciones

Termina preguntando si necesita más ayuda.
"""

            st.write(preguntar_llm(prompt))
