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
df_suelos = pd.read_csv("modelos/suelos.csv")

# =========================
# SESSION STATE
# =========================

if "df_res" not in st.session_state:
    st.session_state.df_res = None

if "cluster" not in st.session_state:
    st.session_state.cluster = None

if "ubicacion_data" not in st.session_state:
    st.session_state.ubicacion_data = None

if "input_base" not in st.session_state:
    st.session_state.input_base = None

# =========================
# ESTILOS
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

    with st.spinner("🌱 Analizando condiciones..."):

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

        df_res, cluster = recomendar_cultivos(input_dict)

        st.session_state.df_res = df_res
        st.session_state.cluster = cluster
        st.session_state.ubicacion_data = (municipio, estado, lat, lon)
        st.session_state.input_base = input_dict

# =========================
# RESULTADOS
# =========================

if st.session_state.df_res is not None:

    df_res = st.session_state.df_res
    cluster = st.session_state.cluster
    municipio, estado, lat, lon = st.session_state.ubicacion_data
    input_dict = st.session_state.input_base

    st.success(f"{municipio}, {estado}")
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

    # selector
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

    # =========================
    # CARDS
    # =========================

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        st.markdown(f"""
        <div class="card">
            <h3>#{i} 🌱 {row['cultivo']}</h3>
            <p><b>Tipo:</b> {row['tipo_cultivo']} | <b>Clasificación:</b> {row['clasificacion']}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        col1.metric("📈 Rendimiento", f"{row['rendimiento']:.1f}")
        col2.metric("⚠️ Riesgo", f"{row['riesgo']:.1f}")
        col3.metric("🧠 Score", f"{row['score']:.1f}")

        st.caption(f"Rango: {row['low']:.1f} – {row['high']:.1f}")

    # =========================
    # WHAT IF PRO
    # =========================

    st.markdown("---")
    st.subheader("🧪 Simulación Agronómica")

    escenario = st.selectbox(
        "Escenario climático",
        ["Base", "🌵 Sequía", "🔥 Ola de calor", "🌧️ Lluvias intensas"]
    )

    col1, col2 = st.columns(2)

    with col1:
        delta_temp = st.slider("Temperatura (°C)", -10, 10, 0)

    with col2:
        delta_precip = st.slider("Precipitación (%)", -50, 50, 0)

    input_sim = input_dict.copy()

    if escenario == "🌵 Sequía":
        input_sim["precip_total"] *= 0.6

    elif escenario == "🔥 Ola de calor":
        input_sim["temp_avg"] += 5
        input_sim["temp_min"] += 5
        input_sim["temp_max"] += 5

    elif escenario == "🌧️ Lluvias intensas":
        input_sim["precip_total"] *= 1.5

    input_sim["temp_avg"] += delta_temp
    input_sim["temp_min"] += delta_temp
    input_sim["temp_max"] += delta_temp

    input_sim["precip_total"] *= (1 + delta_precip / 100)

    df_sim, _ = recomendar_cultivos(input_sim)

    if modo == "🌾 Mayor rendimiento":
        df_sim = df_sim.sort_values(by="rendimiento", ascending=False)
    else:
        df_sim = df_sim.sort_values(by="score", ascending=False)

    st.subheader("📊 Impacto")

    df_compare = df_res[["cultivo", "rendimiento"]].merge(
        df_sim[["cultivo", "rendimiento"]],
        on="cultivo",
        suffixes=("_base", "_sim")
    )

    df_compare["delta"] = df_compare["rendimiento_sim"] - df_compare["rendimiento_base"]

    st.bar_chart(df_compare.set_index("cultivo")[["rendimiento_base", "rendimiento_sim"]])

    # =========================
    # ANÁLISIS POR CULTIVO
    # =========================

    cultivo_sel = st.selectbox("Analizar cultivo", df_res["cultivo"].unique())

    base_row = df_res[df_res["cultivo"] == cultivo_sel].iloc[0]
    sim_row = df_sim[df_sim["cultivo"] == cultivo_sel].iloc[0]

    col1, col2, col3 = st.columns(3)

    col1.metric("Base", f"{base_row['rendimiento']:.1f}")
    col2.metric("Simulado", f"{sim_row['rendimiento']:.1f}")
    col3.metric("Cambio", f"{sim_row['rendimiento'] - base_row['rendimiento']:.1f}")

    # =========================
    # SENSIBILIDAD
    # =========================

    st.subheader("📈 Sensibilidad a temperatura")

    temps = list(range(-5, 6))
    results = []

    for t in temps:
        temp_input = input_dict.copy()
        temp_input["temp_avg"] += t
        temp_input["temp_min"] += t
        temp_input["temp_max"] += t

        df_temp, _ = recomendar_cultivos(temp_input)

        val = df_temp[df_temp["cultivo"] == cultivo_sel]["rendimiento"].values[0]
        results.append(val)

    df_temp_curve = pd.DataFrame({
        "delta_temp": temps,
        "rendimiento": results
    })

    st.line_chart(df_temp_curve.set_index("delta_temp"))
