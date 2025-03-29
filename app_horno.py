# termografia_horno_app.py con plantilla PDF personalizada y todas las gráficas
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import datetime
import fitz  # PyMuPDF
import os
import numpy as np

st.set_page_config(page_title="Informe de Termografía", layout="wide")
st.title("Informe Termografía Metalquimica Ltda")

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    plantilla_pdf = st.file_uploader("📌 Cargar plantilla PDF para el informe:", type=["pdf"])
with col2:
    datos_datalogger = st.file_uploader("📂 Subir datos del datalogger (CSV o Excel):", type=["csv", "xlsx"])

# --- CAMPOS DE INFORMACIÓN ---
st.sidebar.header("📋 Información del informe")
cliente = st.sidebar.text_input("Cliente")
producto = st.sidebar.text_input("Producto")
fecha = st.sidebar.date_input("Fecha de medición", datetime.date.today())

hora_inicio_horno = st.sidebar.text_input("Hora inicio horno (HH:MM)", "9:45")
hora_inicio_logger = st.sidebar.text_input("Hora inicio datalogger (HH:MM)", "9:45")
hora_fin_logger = st.sidebar.text_input("Hora fin datalogger (HH:MM)", "10:37")
temp_inicial = st.sidebar.number_input("Temp. inicial (°C)", 0.0, 100.0, 24.8)
temp_max = st.sidebar.number_input("Temp. máxima (°C)", 0.0, 300.0, 179.5)
tiempo_total = st.sidebar.number_input("Tiempo total horneo (min)", 0.0, 120.0, 39.0)
tiempo_caldo = st.sidebar.number_input("Tiempo de calentamiento (min)", 0.0, 120.0, 33.0)
tiempo_curado = st.sidebar.number_input("Tiempo de curado (min)", 0.0, 120.0, 6.0)
temp_prom_curado = st.sidebar.number_input("Temp. promedio curado (°C)", 0.0, 300.0, 166.8)
rapidez_prom = st.sidebar.number_input("Rapidez promedio (°C/min)", 0.0, 10.0, 3.2)
umbral_curado = st.sidebar.number_input("Umbral de curado (°C)", 100.0, 300.0, 160.0)

intervalos_str = st.sidebar.text_input(
    "Intervalos de temperatura para analizar comportamiento del horno (°C)",
    value="100,120,140,160,180,200"
)

conclusiones = st.sidebar.text_area("✍️ Conclusiones", height=150)
recomendaciones = st.sidebar.text_area("💡 Recomendaciones", height=150)

# --- PROCESAMIENTO ---
if plantilla_pdf and datos_datalogger:
    try:
        if datos_datalogger.name.endswith(".csv"):
            df = pd.read_csv(datos_datalogger)
        else:
            df = pd.read_excel(datos_datalogger)

        df.dropna(how="all", axis=1, inplace=True)
        df.columns = [col.strip() for col in df.columns]

        time_col = None
        for col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].notna().sum() > 0:
                    time_col = col
                    break
            except:
                continue

        if time_col:
            df.rename(columns={time_col: "Tiempo"}, inplace=True)
            df.dropna(subset=["Tiempo"], inplace=True)
            df.set_index("Tiempo", inplace=True)
        else:
            st.error("No se detectó una columna de tiempo válida.")

        temp_cols = [col for col in df.columns if df[col].dtype in ["float64", "int64"]]
        display_col = st.selectbox("Columna del display del horno:", temp_cols)
        referencia_col = st.selectbox("Canal de referencia para desviación:", temp_cols, index=temp_cols.index(display_col))
        sondas_cols = st.multiselect("Columnas de las sondas internas:", temp_cols, default=temp_cols)

        # --- ANÁLISIS DE INTERVALOS DE TEMPERATURA (COMBINADO) ---
        bins = [float(x.strip()) for x in intervalos_str.split(",")]
        bin_labels = [f"{bins[i]}–{bins[i + 1]}°C" for i in range(len(bins) - 1)]
        tiempo_muestreo = df.index.to_series().diff().median().total_seconds() / 60

        tabla_combinada = pd.DataFrame(index=bin_labels)
        for col in sondas_cols:
            categorias = pd.cut(df[col], bins=bins, labels=bin_labels, include_lowest=True)
            conteo = categorias.value_counts().sort_index()
            tabla_combinada[col] = conteo * tiempo_muestreo

        tabla_combinada["Total (min)"] = tabla_combinada.sum(axis=1)
        tabla_combinada["% total"] = 100 * tabla_combinada["Total (min)"] / tabla_combinada["Total (min)"].sum()
        totales = tabla_combinada.sum(numeric_only=True).to_frame().T
        totales.index = ["Total"]
        tabla_combinada = pd.concat([tabla_combinada, totales])

        st.subheader("📊 Tabla de tiempos por intervalo de temperatura")
        st.dataframe(tabla_combinada.style.format("{:.2f}"))

        fig_comb, ax_comb = plt.subplots(figsize=(10, 5))
        width = 0.8 / len(sondas_cols)
        x = np.arange(len(bin_labels))

        for i, col in enumerate(sondas_cols):
            valores = tabla_combinada.loc[bin_labels, col]
            barras = ax_comb.bar(x + i * width, valores, width=width, label=col)
            for bar in barras:
                height = bar.get_height()
                if height > 0:
                    ax_comb.annotate(f'{height:.1f}',
                                     xy=(bar.get_x() + bar.get_width() / 2, height),
                                     xytext=(0, 3),
                                     textcoords="offset points",
                                     ha='center', va='bottom', fontsize=8)

        ax_comb.set_xticks(x + width * len(sondas_cols) / 2)
        ax_comb.set_xticklabels(bin_labels, rotation=45)
        ax_comb.set_ylabel("Tiempo (min)")
        ax_comb.set_title("Distribución de temperatura por intervalo y canal")
        ax_comb.legend(title="Canal")
        ax_comb.grid(axis='y')
        st.pyplot(fig_comb)

        # --- GRÁFICA DE CURADO ---
        fig_temp, ax_temp = plt.subplots(figsize=(12, 5))
        for col in sondas_cols:
            if col != display_col:
                ax_temp.plot(df.index, df[col], label=col)
        ax_temp.plot(df.index, df[display_col], label="Display", linestyle="--", linewidth=2, color="red")
        ax_temp.axhline(y=umbral_curado, color='black', linestyle='-', linewidth=1.5, label=f"Umbral: {umbral_curado}°C")
        zona_curado = df[df[sondas_cols].ge(umbral_curado).any(axis=1)]
        if not zona_curado.empty:
            ax_temp.axvline(x=zona_curado.index[0], color='black', linestyle='-', linewidth=1.5)
            ax_temp.axvline(x=zona_curado.index[-1], color='black', linestyle='-', linewidth=1.5)
        ax_temp.set_title("Curva de curado")
        ax_temp.set_xlabel("Tiempo Horneo (minutos)")
        ax_temp.set_ylabel("Temperatura Horno (°C)")
        ax_temp.legend()
        ax_temp.grid(True)
        st.subheader("Curva de curado")
        st.pyplot(fig_temp)

        # --- GRÁFICA DE DESVIACIÓN ---
        fig_desv, ax_desv = plt.subplots(figsize=(12, 5))
        for col in sondas_cols:
            if col != referencia_col:
                desviacion = df[col] - df[referencia_col]
                ax_desv.plot(df.index, desviacion, label=f"{col} - {referencia_col}")
        ax_desv.axhline(0, color='red', linestyle='--', linewidth=1.5, label="Diferencia = 0")
        ax_desv.set_title(f"Desviación de temperatura vs {referencia_col}")
        ax_desv.set_xlabel("Tiempo")
        ax_desv.set_ylabel("Desviación (°C)")
        ax_desv.legend()
        ax_desv.grid(True)
        st.subheader(f"📉 Desviación respecto a {referencia_col}")
        st.pyplot(fig_desv)
        st.markdown("""
        <div style='background-color: #f9f9f9; border-left: 6px solid #2196F3; padding: 10px; margin-top: 10px;'>
        <b>Interpretación:</b> Si la diferencia de temperatura entre cada canal y el canal de referencia es mínima, 
        la curva se mantendrá cercana a cero, a mayor diferencia la curva se alejará del cero. Si la temperatura del canal es mayor que la del canal de referencia, 
        la curva estará por encima de cero. Si es menor, estará por debajo de cero.
        </div>
        """, unsafe_allow_html=True)

        # --- GRÁFICO BOXPLOT ---
        st.subheader("📦 Homogeneidad térmica")
        st.markdown("""
        <div style='background-color: #f9f9f9; border-left: 6px solid #4CAF50; padding: 10px; margin-top: 10px;'>
        <b>Interpretación:</b> Este gráfico muestra la dispersión de temperaturas por cada canal. La línea del centro indica la mediana,
        los bordes de la caja indican el 25% y 75% de los datos, y los extremos de las lineas los minimos y maximos.
        Los puntos fuera indica son valores atípicos.
        </div>
        """, unsafe_allow_html=True)
        fig_box, ax_box = plt.subplots(figsize=(10, 5))
        data = [df[col].dropna() for col in sondas_cols]
        ax_box.boxplot(data, labels=sondas_cols, patch_artist=True)
        ax_box.set_title("Distribución de temperaturas por canal")
        ax_box.set_ylabel("Temperatura (°C)")
        ax_box.grid(True, axis='y')
        st.pyplot(fig_box)

    except Exception as e:
        st.error(f"❌ Error al procesar los datos: {e}")
