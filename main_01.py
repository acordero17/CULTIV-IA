import streamlit as st
import requests
import pandas as pd
import unicodedata
from openai import OpenAI
from utils import recomendar_cultivos,construir_df_economico, cargar_costos, get_info_cultivo

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def preguntar_llm(prompt):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Eres un ingeniero agrónomo experto en México.
Das recomendaciones claras, prácticas y profesionales.
No inventas datos.
"""},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=400
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

# 🌦️ CLIMA ACTUAL
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
    url = "https://api.opencagedata.com/geocode/v1/json"

    params = {
        "q": ubicacion,
        "key": st.secrets["OPENCAGE_API_KEY"],
        "limit": 1,
        "language": "es"
    }

    try:
        r = requests.get(url, params=params, timeout=5)

        if r.status_code != 200:
            return None

        data = r.json()

        if not data["results"]:
            return None

        result = data["results"][0]

        return {
            "lat": result["geometry"]["lat"],
            "lon": result["geometry"]["lng"],
            "address": result["components"]
        }

    except Exception:
        return None

def extraer_municipio(data):
    addr = data["address"]

    municipio = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("county")
    )

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

        df_res, cluster = recomendar_cultivos(input_dict, municipio)
        # 🔥 ECONÓMICO
        df_costos = cargar_costos()
        df_costos["nomcultivo"] = df_costos["nomcultivo"].str.lower().str.strip()
        df_precios = pd.read_csv("modelos/precios.csv")
        df_precios["nomcultivo"] = df_precios["nomcultivo"].str.lower().str.strip()

        df_economico = df_costos.merge(
            df_precios,
            on="nomcultivo",
            how="left"
        )

        st.session_state.df_economico = df_economico

        # guardar
        st.session_state.df_res = df_res
        st.session_state.cluster = cluster
        st.session_state.ubicacion_data = (municipio, estado, actual, clima)
        st.session_state.input_dict = input_dict  # 🔥 clave para what-if

# =========================
# RESULTADOS
# =========================

# 🔒 VALIDACIÓN GLOBAL
if st.session_state.df_res is None:
    st.stop()

# 👉 ahora sí puedes usar variables
df_res = st.session_state.df_res
cluster = st.session_state.cluster
municipio, estado, actual, clima = st.session_state.ubicacion_data

st.success(f"{municipio}, {estado}")

# 🌦️ ACTUAL
st.subheader("🌦️ Condición actual")
c1, c2 = st.columns(2)
c1.metric("🌡️ Temperatura actual", f"{actual['temp']:.1f} °C")
c2.metric("🌧️ Lluvia actual", f"{actual['precip']:.1f} mm")

# 🌍 HISTÓRICO
st.subheader("🌍 Climatología histórica (2018–2023)")
c1, c2 = st.columns(2)
c1.metric("🌡️ Temp promedio", f"{clima['temp_avg']:.1f} °C")
c2.metric("🌧️ Precipitación anual", f"{clima['precip_total']:.0f} mm")

# 🌍 CLUSTER
cluster_map = {
    0: "Zona agrícola de alto potencial",
    1: "Zona productiva tecnificada",
    2: "Zona de bajo rendimiento por suelo",
    3: "Zona con suelo arcilloso",
    4: "Zona húmeda de bajo rendimiento"
}

st.subheader("🌍 Tipo de municipio")
st.success(cluster_map.get(cluster, cluster))

# 🧠 score explicación
st.info("🧠 Score = rendimiento esperado - riesgo (penaliza incertidumbre)")

# 🎛️ selector
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

# 🧱 CARDS
for i, (_, row) in enumerate(top5.iterrows(), 1):

    riesgo = row["riesgo"]

    st.markdown(f"""
    <div class="card">
        <h3>#{i} 🌱 {row['cultivo']}</h3>
        <p><b>Tipo:</b> {row['tipo_cultivo']} | <b>Clasificación:</b> {row['clasificacion']}</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    col1.metric("📈 Rendimiento (ton/ha)", f"{row['rendimiento']:.1f}")
    col2.metric("⚠️ Riesgo", f"{riesgo:.1f}")
    col3.metric("🧠 Score", f"{row['score']:.1f}")

    st.caption(f"Rango: {row['low']:.1f} – {row['high']:.1f}")

    # 🔥 ECONÓMICO
    if "df_economico" in st.session_state:

        df_econ = st.session_state.df_economico
        cultivo_nombre = row["cultivo"].lower().strip()

        row_econ = df_econ[df_econ["nomcultivo"] == cultivo_nombre]

        if not row_econ.empty:

            costo = row_econ["costo"].values[0]
            precio = row_econ["precio"].values[0]

            if pd.notna(costo) and pd.notna(precio):

                ingreso = row["rendimiento"] * precio
                ganancia = ingreso - costo

                if ganancia > 0:
                    st.success(f"💰 Ganancia estimada: ${ganancia:,.0f} / ha")
                else:
                    st.error(f"📉 Pérdida estimada: ${ganancia:,.0f} / ha")

            else:
                st.warning("⚠️ No se tiene el dato del costo actual")

        else:
            st.warning("⚠️ No se tiene el dato del costo actual")

    # 🔬 WHAT-IF
    st.subheader("🔬 What-if (simulación rápida)")

    cultivo_sel = st.selectbox("Selecciona cultivo", df_res["cultivo"])

    temp_delta = st.slider("🌡️ Cambio temperatura (°C)", -5.0, 5.0, 0.0)
    precip_delta = st.slider("🌧️ Cambio precipitación (%)", -50, 50, 0)

    if st.button("Simular escenario"):

        input_mod = st.session_state.input_dict.copy()

        input_mod["temp_avg"] += temp_delta
        input_mod["temp_max"] += temp_delta
        input_mod["temp_min"] += temp_delta
        input_mod["precip_total"] *= (1 + precip_delta / 100)

        df_new, _ = recomendar_cultivos(input_mod,municipio)

        row_new = df_new[df_new["cultivo"] == cultivo_sel].iloc[0]

        st.markdown("### 📊 Resultado simulado")

        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Rendimiento (ton/ha)", f"{row_new['rendimiento']:.1f}")
        c2.metric("⚠️ Riesgo", f"{row_new['riesgo']:.1f}")
        c3.metric("🧠 Score", f"{row_new['score']:.1f}")

# =========================
# 🧠 ASESOR AGRÍCOLA (INTERACTIVO)
# =========================

st.markdown("---")
st.subheader("🧠 Asesor agrícola")

decision = st.radio(
    "¿Ya seleccionaste un cultivo o necesitas ayuda para decidir?",
    ["❓ Necesito ayuda para decidir", "✅ Ya elegí un cultivo"],
    horizontal=True
)

# =========================
# 🔍 AYUDA PARA DECIDIR
# =========================

if decision == "❓ Necesito ayuda para decidir":

    # 👉 BOTÓN PRINCIPAL
    if st.button("🧠 Ayúdame a decidir"):

        top = df_res.head(3)

        prompt = f"""
Eres un ingeniero agrónomo experto en México.

REGLAS:
- Máximo 6 líneas
- NO listar todos los cultivos
- NO repetir tablas
- Sé directo

Ubicación: {municipio}, {estado}

Resultados:
{top[['cultivo','rendimiento','riesgo','score']].to_string()}

INSTRUCCIONES:
1. Elige el mejor cultivo
2. Explica brevemente por qué
3. Da una segunda opción
4. Termina EXACTAMENTE con:

"¿Te convence esta opción o prefieres la alternativa?"
"""

        with st.spinner("🧠 Analizando..."):
            respuesta = preguntar_llm(prompt)

        # 👉 GUARDAMOS RESPUESTA
        st.session_state.recomendacion = respuesta

    # 👉 MOSTRAR RESPUESTA SI YA EXISTE
    if "recomendacion" in st.session_state:

        st.markdown("### 🧠 Recomendación")
        st.write(st.session_state.recomendacion)

        # 👉 INTERACCIÓN DEL USUARIO
        decision_usuario = st.radio(
            "¿Qué quieres hacer?",
            ["✅ Sí, analizar esta opción", "🔄 Ver alternativa"]
        )

        # =========================
        # ✔️ USUARIO ACEPTA
        # =========================

        if decision_usuario == "✅ Sí, analizar esta opción":

            cultivo_top = df_res.iloc[0]

            if st.button("📘 Ver análisis completo"):

                prompt_cultivo = f"""
Cultivo: {cultivo_top['cultivo']}
Ubicación: {municipio}, {estado}

Explica de forma clara y práctica:

- condiciones óptimas
- comparación con las actuales
- plagas comunes
- recomendaciones

REGLAS OBLIGATORIAS:
- Máximo 8 líneas
- NO hacer texto largo tipo reporte
- Sé directo y útil

IMPORTANTE:
La última línea DEBE ser EXACTAMENTE esta pregunta:

"¿Hay algo más que quieras analizar o mejorar?"

NO agregues nada después de esa pregunta.
"""

                with st.spinner("🌱 Analizando cultivo..."):
                    st.write(preguntar_llm(prompt_cultivo))

        # =========================
        # ❌ USUARIO QUIERE ALTERNATIVA
        # =========================

        elif decision_usuario == "🔄 Ver alternativa":

            cultivo_alt = df_res.iloc[1]

            if st.button("🌱 Analizar alternativa"):

                prompt_alt = f"""
El usuario NO eligió la primera opción.

Recomienda este cultivo como alternativa:
{cultivo_alt['cultivo']}

Ubicación: {municipio}, {estado}

Explica brevemente:
- por qué es buena opción
- en qué casos es mejor que la primera

Termina con:
"¿Te gustaría analizar este cultivo?"
"""

                with st.spinner("🌱 Analizando alternativa..."):
                    st.write(preguntar_llm(prompt_alt))


# =========================
# 🌱 YA ELIGIÓ DIRECTAMENTE
# =========================

else:

    if st.session_state.df_res is None:
        st.warning("👆 Primero analiza una ubicación")
        st.stop()

    df_res = st.session_state.df_res

    cultivo_final = st.selectbox(
        "🌱 ¿Qué cultivo elegiste?",
        df_res["cultivo"]
    )

    if st.button("📘 Analizar cultivo"):

        row = df_res[df_res["cultivo"] == cultivo_final].iloc[0]

        prompt = f"""
Cultivo: {cultivo_final}
Ubicación: {municipio}, {estado}

Condiciones actuales:
Temp: {actual['temp']} °C
Precipitación: {clima['precip_total']} mm

Rendimiento: {row['rendimiento']}
Riesgo: {row['riesgo']}

Explica de forma clara y práctica:

- condiciones óptimas
- comparación con las actuales
- plagas comunes
- recomendaciones

REGLAS OBLIGATORIAS:
- Máximo 8 líneas
- NO hacer texto largo tipo reporte
- Sé directo y útil

IMPORTANTE:
La última línea DEBE ser EXACTAMENTE esta pregunta:

"¿Hay algo más que quieras analizar o mejorar?"

NO agregues nada después de esa pregunta.
"""

        with st.spinner("🌱 Analizando cultivo..."):
            st.write(preguntar_llm(prompt))
            # =========================
            # 💬 CONTINUAR CONVERSACIÓN
            # =========================

            st.markdown("---")
            st.subheader("💬 Continuar conversación")

            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            user_msg = st.text_input("Escribe tu pregunta...")

            if st.button("Enviar mensaje"):

                if user_msg.strip() != "":

                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": user_msg
                    })

                    contexto = ""
                    for m in st.session_state.chat_history[-5:]:
                        contexto += f"{m['role']}: {m['content']}\n"

                    prompt = f"""
            Eres un ingeniero agrónomo experto en México.

            Contexto:
            {contexto}

            Responde claro, breve y útil.
            Máximo 6 líneas.
            """

                    with st.spinner("🧠 Pensando..."):
                        respuesta = preguntar_llm(prompt)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": respuesta
                    })

# mostrar historial
            if st.session_state.chat_history:
                for m in st.session_state.chat_history:
                    if m["role"] == "user":
                        st.markdown(f"**👤 Tú:** {m['content']}")
                    else:
                        st.markdown(f"**🌱 Asesor:** {m['content']}")
    # 🔄 RESET
    st.markdown("---")
    if st.button("🔄 ¿Quieres analizar otro municipio?"):

        for key in ["df_res", "cluster", "ubicacion_data", "input_dict", "chat_history"]:
            if key in st.session_state:
                del st.session_state[key]

        st.rerun()
