import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos, simular_cultivo

st.set_page_config(page_title="Cultiv-IA", layout="wide")

api_key = st.secrets["OPENWEATHER_API_KEY"]

# =========================
# INIT SESSION STATE (robusto)
# =========================

for key in ["df_res", "forecast", "suelo", "input_base", "municipio", "estado"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =========================
# HEADER
# =========================

st.title("🌱 Cultiv-IA")
st.caption("Recomendaciones inteligentes para el campo")

st.info("📍 Ingresa la ubicación en formato: Municipio, Estado (ej. Texcoco, Estado de México)")

ubicacion = st.text_input("Ubicación", key="ubicacion_input")

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
    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
    data = requests.get(url, params=params).json()

    temps, lluvia, hum = [], 0, []

    for i in data["list"]:
        temps.append(i["main"]["temp"])
        hum.append(i["main"]["humidity"])
        lluvia += i.get("rain", {}).get("3h", 0)

    return {
        "temp_avg": sum(temps)/len(temps),
        "precip_total": lluvia,
        "humidity": sum(hum)/len(hum)
    }

def obtener_datos_ubicacion(ubicacion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": ubicacion, "format": "json", "addressdetails": 1}

    try:
        res = requests.get(url, params=params)
        data = res.json()  # igual que antes
        return data[0] if data else None

    except Exception:
        return None

def extraer_municipio(data):
    addr = data["address"]
    return addr.get("city") or addr.get("town") or addr.get("county"), addr.get("state")

# =========================
# BOTÓN
# =========================

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)

    if not data:
        st.error("No se encontró la ubicación. Usa formato: Municipio, Estado")
        st.stop()

    municipio, estado = extraer_municipio(data)

    lat, lon = float(data["lat"]), float(data["lon"])

    forecast = obtener_forecast(lat, lon)
    suelo = obtener_suelo(municipio)

    input_base = {
        "temp_avg": forecast["temp_avg"],
        "temp_max": forecast["temp_avg"],
        "temp_min": forecast["temp_avg"],
        "precip_total": forecast["precip_total"] * 50,
        "precip_avg": forecast["precip_total"],
        "nomestado": "MEXICO",
        "nomcicloproductivo": "PV",
        "nommodalidad": "RIEGO"
    }

    input_base.update(suelo)

    df_res, cluster = recomendar_cultivos(input_base)

    st.session_state.df_res = df_res
    st.session_state.input_base = input_base
    st.session_state.forecast = forecast
    st.session_state.suelo = suelo
    st.session_state.municipio = municipio
    st.session_state.estado = estado

# =========================
# RESULTADOS
# =========================

data_ready = all(
    st.session_state[k] is not None
    for k in ["df_res", "forecast", "suelo", "input_base", "municipio", "estado"]
)

if data_ready:

    df_res = st.session_state.df_res
    forecast = st.session_state.forecast
    suelo = st.session_state.suelo
    municipio = st.session_state.municipio
    estado = st.session_state.estado

    st.success(f"📍 {municipio}, {estado}")

    # =========================
    # 🌍 CONDICIONES
    # =========================

    st.subheader("🌍 Condiciones actuales del municipio")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🌡️ Temperatura", f"{forecast['temp_avg']:.1f} °C")
    col2.metric("🌧️ Precipitación", f"{forecast['precip_total']:.1f} mm")
    col3.metric("💧 Humedad", f"{forecast['humidity']:.0f} %")

    suelo_tipo = max(suelo, key=suelo.get)
    map_suelo = {
        "suelo_arcilloso": "Arcilloso",
        "suelo_arenoso": "Arenoso",
        "suelo_fertil": "Fértil",
        "suelo_limitado": "Limitado"
    }

    col4.metric("🌱 Suelo", map_suelo.get(suelo_tipo, suelo_tipo))

    st.caption("Condiciones promedio estimadas para apoyar decisiones agrícolas.")

    # =========================
    # 🌾 RESULTADOS
    # =========================

    st.subheader("🌾 Cultivos recomendados")
    st.caption("Rendimiento en toneladas por hectárea (ton/ha)")
    st.caption("Score = rendimiento esperado - riesgo")

    top5 = df_res.head(5)

    for _, row in top5.iterrows():
        st.write(f"### 🌱 {row['cultivo']}")
        st.write(f"Rendimiento: {row['rendimiento']:.1f} ton/ha")
        st.write(f"Riesgo: {row['riesgo']:.1f}")
        st.write(f"Score: {row['score']:.1f}")

    # =========================
    # 🧪 SIMULADOR
    # =========================

    st.markdown("---")
    st.subheader("🧪 Simulador climático")

    cultivo = st.selectbox("Selecciona cultivo", df_res["cultivo"])

    dtemp = st.slider("Cambio temperatura (°C)", -5.0, 5.0, 0.0)
    dprec = st.slider("Cambio precipitación (%)", -50, 50, 0)

    base = st.session_state.input_base.copy()

    base["temp_avg"] += dtemp
    base["temp_max"] += dtemp
    base["temp_min"] += dtemp
    base["precip_total"] *= (1 + dprec / 100)

    sim = simular_cultivo(base, cultivo)

    st.write("### Resultado simulado")
    st.write(f"Rendimiento: {sim['rendimiento']:.1f} ton/ha")
    st.write(f"Riesgo: {sim['riesgo']:.1f}")
    st.write(f"Score: {sim['score']:.1f}")
