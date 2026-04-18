import streamlit as st
import requests
import pandas as pd
import unicodedata

from utils import recomendar_cultivos

# =========================
# 🎨 ESTILOS
# =========================

st.set_page_config(page_title="Cultiv-IA", layout="wide")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0.55)),
    url("https://images.unsplash.com/photo-1500382017468-9049fed747ef");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

.block-container {
    background: rgba(0, 0, 0, 0.5);
    padding: 2rem;
    border-radius: 16px;
}

h1, h2, h3 {
    color: #E8F5E9;
}

.stButton>button {
    background-color: #4CAF50;
    color: white;
    border-radius: 10px;
    font-weight: bold;
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
# CONFIG
# =========================

api_key = st.secrets["OPENWEATHER_API_KEY"]

df_suelos = pd.read_csv("modelos/suelos.csv")

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
# INPUT
# =========================

st.markdown("### 📍 Ingresa tu ubicación")
ubicacion = st.text_input("", "Texcoco, México")

# =========================
# MAIN FLOW
# =========================

if st.button("Analizar"):

    data = obtener_datos_ubicacion(ubicacion)

    municipio, estado = extraer_municipio(data)

    lat = float(data["lat"])
    lon = float(data["lon"])

    st.success(f"{municipio}, {estado}")

    # 🗺️ MAPA
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

    forecast = obtener_forecast(lat, lon)

    precip_total = forecast["precip_total"] * 50
    precip_avg = precip_total / 365

    suelo = obtener_suelo(municipio)

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

    # =========================
    # SELECTOR
    # =========================

    modo = st.radio(
        "¿Qué prefieres?",
        ["🌾 Mayor rendimiento", "🧠 Mayor estabilidad"],
        horizontal=True
    )

    if modo == "🌾 Mayor rendimiento":
        df_res = df_res.sort_values(by="rendimiento", ascending=False)
        st.subheader("Top por rendimiento")
    else:
        df_res = df_res.sort_values(by="score", ascending=False)
        st.subheader("Top balanceado")

    top5 = df_res.head(5)

    # =========================
    # CARDS
    # =========================

    for i, (_, row) in enumerate(top5.iterrows(), 1):

        riesgo = row["high"] - row["low"]

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
