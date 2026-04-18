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


# =========================
# 🔥 NUEVO: OpenCage (reemplazo de Nominatim)
# =========================

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

    try:
        response = requests.get(url, params=params, timeout=5)

        if response.status_code != 200:
            st.error(f"Error OpenCage: {response.status_code}")
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

    except Exception as e:
        st.error(f"Error en geocoding: {e}")
        return None


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

        st.session_state.df_res = df_res
        st.session_state.cluster = cluster
        st.session_state.ubicacion_data = (municipio, estado)

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    df_res = st.session_state.df_res
    cluster = st.session_state.cluster
    municipio, estado = st.session_state.ubicacion_data

    st.success(f"{municipio}, {estado}")

    cluster_map = {
        0: "Zona agrícola de alto potencial",
        1: "Zona productiva tecnificada",
        2: "Zona de bajo rendimiento por suelo",
        3: "Zona con suelo arcilloso",
        4: "Zona húmeda de bajo rendimiento"
    }

    st.subheader("🌍 Tipo de municipio")
    st.success(cluster_map.get(cluster, cluster))

    modo = st.radio(
        "¿Qué prefieres?",
        ["🌾 Mayor rendimiento", "🧠 Mayor estabilidad"],
        horizontal=True
    )

    if modo == "🌾 Mayor rendimiento":
        df_res = df_res.sort_values(by="rendimiento", ascending=False)
    else:
        df_res = df_res.sort_values(by="score", ascending=False)

    top5 = df_res.head(5)

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        riesgo = row["riesgo"]

        st.markdown(f"""
        <div class="card">
            <h3>#{i} 🌱 {row['cultivo']}</h3>
            <p><b>Tipo:</b> {row['tipo_cultivo']} | <b>Clasificación:</b> {row['clasificacion']}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        col1.metric("📈 Rendimiento", f"{row['rendimiento']:.1f}")
        col2.metric("⚠️ Riesgo", f"{riesgo:.1f}")
        col3.metric("🧠 Score", f"{row['score']:.1f}")

        st.caption(f"Rango: {row['low']:.1f} – {row['high']:.1f}")
