import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos_fast, predecir_con_incertidumbre

# =========================
# CONFIG
# =========================

st.set_page_config(page_title="Cultiv-IA", layout="wide")

api_key = st.secrets["OPENWEATHER_API_KEY"]
df_suelos = pd.read_csv("modelos/suelos.csv")

# =========================
# SESSION STATE
# =========================

if "analizado" not in st.session_state:
    st.session_state.analizado = False

if "df_res" not in st.session_state:
    st.session_state.df_res = None

if "input_base" not in st.session_state:
    st.session_state.input_base = None

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

df_suelos["municipio_clean"] = df_suelos["municipio"].apply(limpiar_texto)

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

def obtener_forecast(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }

    data = requests.get(url, params=params).json()

    temps = []
    lluvia_total = 0

    for item in data["list"]:
        temps.append(item["main"]["temp"])
        lluvia_total += item.get("rain", {}).get("3h", 0)

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": lluvia_total,
    }

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
    return (
        addr.get("city") or addr.get("town") or addr.get("county"),
        addr.get("state")
    )

# =========================
# UI
# =========================

st.title("🌱 Cultiv-IA")

ubicacion = st.text_input("📍 Ubicación", "Texcoco, México")

if st.button("Analizar"):
    st.session_state.analizado = True
    st.session_state.df_res = None  # 🔥 fuerza recalculo

# =========================
# PROCESO PRINCIPAL
# =========================

if st.session_state.analizado and st.session_state.df_res is None:

    with st.spinner("Analizando..."):

        data = obtener_datos_ubicacion(ubicacion)

        municipio, estado = extraer_municipio(data)

        lat = float(data["lat"])
        lon = float(data["lon"])

        forecast = obtener_forecast(lat, lon)
        suelo = obtener_suelo(municipio)

        precip_total = forecast["precip_total"] * 50
        precip_avg = precip_total / 365

        input_dict = {
            "temp_avg": forecast["temp_avg"],
            "temp_min": forecast["temp_avg"],
            "temp_max": forecast["temp_avg"],
            "precip_total": precip_total,
            "precip_avg": precip_avg,
            "nomestado": "MEXICO",
            "nomcicloproductivo": "PV",
            "nommodalidad": "RIEGO"
        }

        input_dict.update(suelo)

        df_res, cluster = recomendar_cultivos_fast(input_dict)

        st.session_state.df_res = df_res
        st.session_state.input_base = input_dict
        st.session_state.ubicacion_data = (municipio, estado, lat, lon)

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    df_res = st.session_state.df_res
    municipio, estado, lat, lon = st.session_state.ubicacion_data
    input_dict = st.session_state.input_base

    st.success(f"{municipio}, {estado}")
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

    df_res = df_res.sort_values(by="rendimiento", ascending=False)
    top5 = df_res.head(5)

    st.subheader("🌾 Top cultivos")

    for _, row in top5.iterrows():
        st.write(f"🌱 {row['cultivo']} — {row['rendimiento']:.1f}")

    # =========================
    # WHAT IF
    # =========================

    st.markdown("---")
    st.subheader("🧪 Simulación por cultivo")

    cultivo_sel = st.selectbox("Cultivo", df_res["cultivo"].unique())

    delta_temp = st.slider("Temperatura", -10, 10, 0)
    delta_precip = st.slider("Precipitación (%)", -50, 50, 0)

    if st.button("Simular"):

        input_sim = input_dict.copy()

        input_sim["temp_avg"] += delta_temp
        input_sim["temp_min"] += delta_temp
        input_sim["temp_max"] += delta_temp
        input_sim["precip_total"] *= (1 + delta_precip / 100)

        resultado = predecir_con_incertidumbre(input_sim, cultivo_sel)

        st.write("Resultado:")
        st.write(resultado)
