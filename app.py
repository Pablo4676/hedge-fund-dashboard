import streamlit as st
from datetime import datetime, timedelta
import pytz
import yfinance as yf  
import pandas as pd
import numpy as np 
import plotly.graph_objects as go  
from plotly.subplots import make_subplots 
import plotly.express as px 
import requests 
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# 1. CONFIGURACIÓN BASE DE LA PÁGINA
st.set_page_config(layout="wide", page_title="Plataforma de Inversión Institucional")

if 'portfolio_history' not in st.session_state:
    st.session_state.portfolio_history = None
    st.session_state.portfolio_total_usd = 0.0
    st.session_state.portfolio_tickers = []
    st.session_state.portfolio_weights = []

# 2. INYECCIÓN DE CSS PERSONALIZADO
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Arial', sans-serif !important; }
    [data-testid="stSidebar"] { background-color: #A09E96 !important; }
    .titulo-principal { font-size: 18px !important; font-weight: bold !important; color: #000000; margin-bottom: 10px; }
    .sub-menu { font-size: 14px !important; font-weight: bold !important; color: #222222; margin-top: 15px; margin-bottom: 5px; }
    .stSelectbox label, .stRadio label { font-size: 10px !important; color: #333333 !important; }
    .titulo-indicador { font-size: 20px !important; font-weight: bold !important; text-align: center; border-bottom: 2px solid #D3D3D3; padding-bottom: 10px; margin-bottom: 20px; }
    
    .texto-extendido { color: #555555; font-size: 14px; margin-top: -15px; margin-bottom: 15px; font-weight: 500;}
    .vol-compra { color: #26A69A; font-weight: bold; }
    .vol-venta { color: #EF5350; font-weight: bold; }
    
    .estado-compra { background-color: #E8F5E9; color: #2E7D32; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 18px; border: 1px solid #A5D6A7;}
    .estado-venta { background-color: #FFEBEE; color: #C62828; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 18px; border: 1px solid #EF9A9A;}
    .estado-neutral { background-color: #FFF3E0; color: #EF6C00; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 18px; border: 1px solid #FFCC80;}
    
    .quant-card { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border-left: 5px solid #29B6F6; margin-bottom: 15px; height: 100%;}
    .quant-title { font-size: 16px; font-weight: bold; color: #333; margin-bottom: 5px;}
    .quant-value { font-size: 24px; font-weight: bold; color: #0277BD; margin-bottom: 10px;}
    .quant-desc { font-size: 12px; color: #666;}
    </style>
""", unsafe_allow_html=True)

# 3. ACTUALIZACIÓN AUTOMÁTICA (CADA 3 MINUTOS = 180000 ms)
if st_autorefresh:
    st_autorefresh(interval=180000, key="data_refresh")

# 4. FECHA Y HORA DE ARGENTINA
tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
hora_actual = datetime.now(tz_arg).strftime("%d/%m/%Y %H:%M:%S")

col_espacio, col_reloj = st.columns([8, 2])
with col_reloj:
    st.markdown(f"**ARG:** {hora_actual}")

# --- COTIZACIONES GLOBALES CORREGIDAS (DÓLAR REAL SIN TEXTO API) ---
try:
    req_mep = requests.get("https://dolarapi.com/v1/dolares/bolsa", timeout=5).json()
    req_ccl = requests.get("https://dolarapi.com/v1/dolares/contadoconliqui", timeout=5).json()
    dolar_mep = float(req_mep['venta'])
    dolar_ccl = float(req_ccl['venta'])
except:
    try:
        ggal_ar = yf.Ticker("GGAL.BA").history(period="1d")['Close'].iloc[-1]
        ggal_us = yf.Ticker("GGAL").history(period="1d")['Close'].iloc[-1]
        dolar_ccl = (ggal_ar * 10) / ggal_us
        dolar_mep = dolar_ccl * 0.96  
    except:
        dolar_ccl, dolar_mep = 1100.0, 1050.0

# 5. INICIALIZACIÓN DE LA BASE DE DATOS
if 'bases_activos' not in st.session_state or "GGAL.BA" not in st.session_state.bases_activos.get("MERVAL", {}).get("Finanzas", []):
    st.session_state.bases_activos = {
        "ETF": ["SPY", "QQQ", "DIA", "IWM", "EEM", "EWZ", "XLF", "XLE", "XLK", "XLU", "XLY", "XLP", "XLI", "XLV", "XLB", "XLC", "ARKK", "BITO"],
        "MERVAL": {
            "Energía": ["YPFD.BA", "PAMP.BA", "TGSU2.BA", "TGNO4.BA"],
            "Finanzas": ["GGAL.BA", "BMA.BA", "BBAR.BA", "SUPV.BA", "VALO.BA", "BYMA.BA"],
            "Utilities": ["EDN.BA", "CEPU.BA", "TRAN.BA", "CGPA2.BA"],
            "Materiales Básicos": ["ALUA.BA", "TXAR.BA", "LOMA.BA"],
            "Comunicaciones": ["TECO2.BA", "CVH.BA"],
            "Industrias": ["MIRG.BA", "AGRO.BA", "FERR.BA"],
            "Consumo Cíclicos": ["IRSA.BA", "MOLI.BA", "SAMI.BA"],
            "Consumos No Cíclicos": ["MORI.BA", "LEDE.BA"],
            "Tecnología": [] 
        },
        "CEDEARS": {
            "Tecnología": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD"], 
            "Consumo Cíclicos": ["AMZN", "TSLA", "MELI"],
            "Comunicaciones": ["NFLX", "DIS"],
            "Finanzas": ["V", "MA", "JPM", "BAC"],
            "Consumos No Cíclicos": ["KO", "PEP", "WMT"],
            "Energía": ["XOM", "CVX"],
            "Utilities": ["NEE"],
            "Industrias": ["CAT", "BA"],
            "Materiales Básicos": ["GOLD", "BHP"]
        }
    }

def obtener_tickers(mercado, categoria):
    return sorted(st.session_state.bases_activos.get(mercado, {}).get(categoria, []))

# 6. CONSTRUCCIÓN DE LA BARRA LATERAL (GESTIÓN DE ACTIVOS INCLUIDA)
categorias = ["Comunicaciones", "Consumo Cíclicos", "Consumos No Cíclicos", "Energía", "Finanzas", "Industrias", "Materiales Básicos", "Tecnología", "Utilities"]

with st.sidebar:
    st.markdown('<div class="titulo-principal">MENÚ DE ANÁLISIS</div>', unsafe_allow_html=True)
    mercado_activo = st.radio("Seleccione el Mercado a operar:", ["ETF", "MERVAL", "CEDEARS"])
    
    if mercado_activo == "ETF":
        ticker_seleccionado = st.selectbox("Activo ETF:", sorted(st.session_state.bases_activos["ETF"]) + ["Ninguno"], key="tick_etf")
    elif mercado_activo == "MERVAL":
        cat_seleccionada = st.selectbox("Categoría MERVAL:", categorias, key="cat_merval")
        ticker_seleccionado = st.selectbox("Activo MERVAL:", obtener_tickers("MERVAL", cat_seleccionada) + ["Ninguno"], key="tick_merval")
    else: 
        cat_seleccionada = st.selectbox("Categoría CEDEARS:", categorias, key="cat_cedear")
        ticker_seleccionado = st.selectbox("Activo CEDEARS:", obtener_tickers("CEDEARS", cat_seleccionada) + ["Ninguno"], key="tick_cedear")

    st.markdown("---")
    opciones_periodo = {"1 Día": 1, "1 Semana": 7, "1 Mes": 30, "6 Meses": 180, "1 Año": 365, "2 Años": 730, "5 Años": 1825, "Máximo (20 años)": 7300}
    periodo_visual = st.selectbox("Periodo a analizar:", list(opciones_periodo.keys()), index=4) 
    dias_recorte = opciones_periodo[periodo_visual]
    
    opciones_intervalo = {"5 Minutos": "5m", "15 Minutos": "15m", "1 Hora": "1h", "1 Día": "1d", "1 Semana": "1wk", "1 Mes": "1mo"}
    intervalo_visual = st.selectbox("Intervalo de velas:", list(opciones_intervalo.keys()), index=3) 
    intervalo_yf = opciones_intervalo[intervalo_visual]

    st.markdown("---")
    st.markdown('<div class="sub-menu">GESTIÓN DE ACTIVOS</div>', unsafe_allow_html=True)
    accion_gestion = st.radio("Acción:", ["Agregar", "Eliminar"], horizontal=True)
    mercado_gestion = st.selectbox("Mercado:", ["ETF", "MERVAL", "CEDEARS"], key="mercado_gestion")
    
    if mercado_gestion != "ETF":
        cat_gestion = st.selectbox("Categoría:", categorias, key="cat_gestion")
    else:
        cat_gestion = None

    if accion_gestion == "Agregar":
        ticker_nuevo = st.text_input("Ticker a agregar (Ej: KO):", key="ticker_nuevo").upper()
        if st.button("Agregar a la base"):
            if ticker_nuevo:
                if mercado_gestion == "ETF":
                    if ticker_nuevo not in st.session_state.bases_activos["ETF"]:
                        st.session_state.bases_activos["ETF"].append(ticker_nuevo)
                        st.success(f"¡{ticker_nuevo} agregado!")
                        st.rerun() 
                else:
                    if cat_gestion not in st.session_state.bases_activos[mercado_gestion]:
                        st.session_state.bases_activos[mercado_gestion][cat_gestion] = []
                    if ticker_nuevo not in st.session_state.bases_activos[mercado_gestion][cat_gestion]:
                        st.session_state.bases_activos[mercado_gestion][cat_gestion].append(ticker_nuevo)
                        st.success(f"¡{ticker_nuevo} agregado!")
                        st.rerun() 
    else: 
        if mercado_gestion == "ETF":
            lista_eliminar = sorted(st.session_state.bases_activos["ETF"])
        else:
            lista_eliminar = obtener_tickers(mercado_gestion, cat_gestion)
            
        ticker_eliminar = st.selectbox("Activo a eliminar:", lista_eliminar, key="ticker_eliminar")
        if st.button("Eliminar de la base"):
            if ticker_eliminar:
                if mercado_gestion == "ETF":
                    st.session_state.bases_activos["ETF"].remove(ticker_eliminar)
                else:
                    st.session_state.bases_activos[mercado_gestion][cat_gestion].remove(ticker_eliminar)
                st.success(f"¡{ticker_eliminar} eliminado!")
                st.rerun()

# --- FUNCIONES DE APOYO Y MATEMÁTICAS ---
def descargar_y_procesar(ticker, intervalo, dias_recorte, es_eeuu=False):
    periodo_descarga = "10y"
    if intervalo in ["5m", "15m"]: periodo_descarga = "60d"
    elif intervalo == "1h": periodo_descarga = "730d"
    
    df = yf.Ticker(ticker).history(period=periodo_descarga, interval=intervalo, prepost=es_eeuu)
    if df.empty: return df, df
    
    df['SMA_21'] = df['Close'].rolling(window=21).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).rolling(window=21).sum() / df['Volume'].rolling(window=21).sum()
    
    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Histograma'] = df['MACD'] - df['Signal']

    fecha_limite = df.index.max() - timedelta(days=dias_recorte)
    return df, df[df.index >= fecha_limite].copy()

def formatear_volumen(vol):
    if vol >= 1e6: return f"{vol/1e6:.2f} M"
    elif vol >= 1e3: return f"{vol/1e3:.2f} K"
    return str(int(vol))

def crear_grafico_velas(df_recortado, titulo):
    colores_volumen = ['#26A69A' if close >= open_ else '#EF5350' for open_, close in zip(df_recortado['Open'], df_recortado['Close'])]
    colores_macd = ['#26A69A' if val >= 0 else '#EF5350' for val in df_recortado['Histograma']]

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df_recortado.index, open=df_recortado['Open'], high=df_recortado['High'], low=df_recortado['Low'], close=df_recortado['Close'], increasing_line_color='#26A69A', decreasing_line_color='#EF5350', name="Precio"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['SMA_21'], line=dict(color='blue', width=1), name='SMA 21'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['SMA_50'], line=dict(color='orange', width=1.5), name='SMA 50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['SMA_200'], line=dict(color='red', width=2), name='SMA 200'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['VWAP'], line=dict(color='#9C27B0', width=2, dash='dot'), name='VWAP Institucional'), row=1, col=1)
    
    fig.add_trace(go.Bar(x=df_recortado.index, y=df_recortado['Volume'], marker_color=colores_volumen, name='Volumen'), row=2, col=1)
    fig.add_trace(go.Bar(x=df_recortado.index, y=df_recortado['Histograma'], marker_color=colores_macd, name='Histograma'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['MACD'], line=dict(color='black', width=1), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_recortado.index, y=df_recortado['Signal'], line=dict(color='red', width=1), name='Señal'), row=3, col=1)

    in_zone = False; start_x = None; cruce_compra_x, cruce_compra_y, cruce_venta_x, cruce_venta_y = [], [], [], []
    for i in range(1, len(df_recortado)):
        if df_recortado['Histograma'].iloc[i] < 0:
            if not in_zone: start_x = df_recortado.index[i]; in_zone = True
        else:
            if in_zone: fig.add_vrect(x0=start_x, x1=df_recortado.index[i], fillcolor="lightgray", opacity=0.4, layer="below", line_width=0, row=3, col=1); in_zone = False
        if df_recortado['MACD'].iloc[i] > df_recortado['Signal'].iloc[i] and df_recortado['MACD'].iloc[i-1] <= df_recortado['Signal'].iloc[i-1]:
            cruce_compra_x.append(df_recortado.index[i]); cruce_compra_y.append(df_recortado['MACD'].iloc[i])
        elif df_recortado['MACD'].iloc[i] < df_recortado['Signal'].iloc[i] and df_recortado['MACD'].iloc[i-1] >= df_recortado['Signal'].iloc[i-1]:
            cruce_venta_x.append(df_recortado.index[i]); cruce_venta_y.append(df_recortado['MACD'].iloc[i])

    if in_zone: fig.add_vrect(x0=start_x, x1=df_recortado.index[-1], fillcolor="lightgray", opacity=0.4, layer="below", line_width=0, row=3, col=1)
    fig.add_trace(go.Scatter(x=cruce_compra_x, y=cruce_compra_y, mode='markers', marker=dict(symbol='star', size=10, color='green'), name='Compra'), row=3, col=1)
    fig.add_trace(go.Scatter(x=cruce_venta_x, y=cruce_venta_y, mode='markers', marker=dict(symbol='star', size=10, color='red'), name='Venta'), row=3, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(title=titulo, template="plotly_white", height=750, margin=dict(l=0, r=0, t=40, b=0), showlegend=False, xaxis_rangeslider_visible=False)
    return fig

def calcular_variacion(df, dias):
    if len(df) < dias + 1: return 0.0
    return ((df['Close'].iloc[-1] - df['Close'].iloc[-(dias + 1)]) / df['Close'].iloc[-(dias + 1)]) * 100

def evaluar_estado_tecnico(df):
    if df.empty or len(df) < 50: return "Datos Insuficientes", "estado-neutral"
    precio = df['Close'].iloc[-1]
    sma50 = df['SMA_50'].iloc[-1]
    macd = df['MACD'].iloc[-1]
    senal = df['Signal'].iloc[-1]
    puntaje = 0
    if precio > sma50: puntaje += 1
    if macd > senal: puntaje += 1
    if puntaje == 2: return "🟢 TENDENCIA DE COMPRA", "estado-compra"
    elif puntaje == 0: return "🔴 TENDENCIA DE VENTA", "estado-venta"
    else: return "🟡 ESTADO NEUTRAL", "estado-neutral"

def format_num(val):
    if val is None or val == 'N/A' or pd.isna(val): return 0
    return float(val)

def render_metric_nativo(label, value_str, condition_color, icon):
    st.markdown(f"**{label}**")
    st.markdown(f"<h3 style='margin-top: -15px; color: {condition_color};'>{icon} {value_str}</h3>", unsafe_allow_html=True)

def evaluar_pe(val):
    if val <= 0: return '🔴', '#EF5350' 
    if val < 15: return '🟢', '#26A69A' 
    if val <= 25: return '🟡', '#F9A825' 
    return '🔴', '#EF5350' 
def evaluar_pb(val):
    if val <= 0: return '🔴', '#EF5350'
    if val < 1.5: return '🟢', '#26A69A'
    if val <= 3: return '🟡', '#F9A825'
    return '🔴', '#EF5350'
def evaluar_porcentaje(val):
    if val > 0.15: return '🟢', '#26A69A' 
    if val >= 0.05: return '🟡', '#F9A825' 
    return '🔴', '#EF5350' 
def evaluar_deuda(val): 
    if val < 50: return '🟢', '#26A69A' 
    if val <= 100: return '🟡', '#F9A825' 
    return '🔴', '#EF5350' 
def evaluar_flujo(val):
    if val > 0: return '🟢', '#26A69A' 
    return '🔴', '#EF5350' 

def en_cartera(tck, cartera_set):
    return tck in cartera_set or f"{tck}.BA" in cartera_set or tck.replace(".BA", "") in cartera_set

# 7. ÁREA PRINCIPAL CON 7 PESTAÑAS COMPLETAS (REORGANIZADAS)
st.markdown('<div class="titulo-indicador">ÁREA DE GRÁFICOS E INDICADORES</div>', unsafe_allow_html=True)

tab_radar, tab_tecnico, tab_fundamental, tab_portfolio, tab_predictivo, tab_backtest, tab_estres = st.tabs([
    "🎯 Radar VIX & Screener",
    "📊 Análisis Técnico", 
    "🏢 Análisis Fundamental", 
    "💼 Mi Portfolio", 
    "🤖 Modelos Predictivos", 
    "⏱️ Backtesting",
    "🚨 Riesgos y Estrés"
])

# --- PESTAÑA 1 (RADAR VIX & SCREENER) ---
with tab_radar:
    st.markdown("## 🎯 Radar de Mercado y Contexto VIX")
    
    st.markdown("### 📉 1. Contexto Global: Índice VIX (El Miedo de Wall Street)")
    try:
        vix_data = yf.Ticker("^VIX").history(period="1mo")
        if not vix_data.empty:
            vix_actual = vix_data['Close'].iloc[-1]
            vix_prev = vix_data['Close'].iloc[-2]
            var_vix = ((vix_actual - vix_prev) / vix_prev) * 100
            
            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                st.metric("VIX Actual", f"{vix_actual:.2f}", f"{var_vix:.2f}% Diario", delta_color="inverse")
            
            with col_v2:
                if vix_actual < 15:
                    st.success("🟢 **Régimen de Complacencia:** El mercado está confiado (VIX bajo). Las tendencias alcistas tienen vía libre, pero evite comprar tras subidas muy prolongadas (riesgo de sobrecompra).")
                elif 15 <= vix_actual <= 25:
                    st.warning("🟡 **Régimen Normal:** Volatilidad estándar. Este es el entorno ideal donde los indicadores técnicos (como el cruce de medias y MACD) funcionan con mayor fiabilidad matemática.")
                else:
                    st.error("🔴 **Régimen de Pánico:** Miedo extremo (VIX alto). Se activan liquidaciones masivas. Las 'Señales de Compra' aquí son de alto riesgo, pero si sobreviven, marcan el piso histórico del mercado.")
        else:
            st.warning("No se pudo descargar la cotización del VIX.")
    except Exception as e:
        st.error(f"Error al cargar VIX: {e}")

    st.markdown("---")
    st.markdown("### 🕵️‍♂️ 2. Screener Cuantitativo de Oportunidades")
    st.write("El algoritmo evalúa todos los activos en su base de datos buscando la 'Triple Confirmación' matemática institucional.")

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        btn_scan = st.button("🚀 Escaneo Manual Único", type="primary")
    with col_s2:
        auto_scan = st.toggle("🔄 Mantener Escaneo Automático (Actualiza cada 3 minutos)", value=False)

    if btn_scan or auto_scan:
        todos_los_tickers = st.session_state.bases_activos["ETF"].copy()
        for cat, tcks in st.session_state.bases_activos["MERVAL"].items():
            todos_los_tickers.extend(tcks)
        for cat, tcks in st.session_state.bases_activos["CEDEARS"].items():
            todos_los_tickers.extend(tcks)
        
        todos_los_tickers = list(set(todos_los_tickers))
        compras_data = []
        ventas_data = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        cartera_set = set(st.session_state.portfolio_tickers)
        
        for i, tck in enumerate(todos_los_tickers):
            status_text.text(f"Auditando métricas en {tck}... ({i+1}/{len(todos_los_tickers)})")
            progress_bar.progress((i + 1) / len(todos_los_tickers))
            try:
                df_scan = yf.Ticker(tck).history(period="3mo", interval="1d")
                if len(df_scan) < 50: continue
                
                p_val = df_scan['Close'].iloc[-1]
                s50_val = df_scan['Close'].rolling(window=50).mean().iloc[-1]
                
                typical = (df_scan['High'] + df_scan['Low'] + df_scan['Close']) / 3
                vwap_val = ((typical * df_scan['Volume']).rolling(window=21).sum() / df_scan['Volume'].rolling(window=21).sum()).iloc[-1]
                
                e12 = df_scan['Close'].ewm(span=12, adjust=False).mean()
                e26 = df_scan['Close'].ewm(span=26, adjust=False).mean()
                macd_val = (e12 - e26).iloc[-1]
                sig_val = (e12 - e26).ewm(span=9, adjust=False).mean().iloc[-1]
                
                es_compra = (p_val > s50_val) and (macd_val > sig_val) and (p_val > vwap_val)
                es_venta = (p_val < s50_val) and (macd_val < sig_val) and (p_val < vwap_val)
                
                if es_compra: 
                    compras_data.append({
                        "Activo": tck,
                        "En Cartera": "⭐ SÍ" if en_cartera(tck, cartera_set) else "No",
                        "Precio Cierre": p_val,
                        "Tendencia (vs SMA50)": ((p_val - s50_val) / s50_val) * 100,
                        "Apoyo Inst. (vs VWAP)": ((p_val - vwap_val) / vwap_val) * 100,
                        "Fuerza MACD (Hist)": macd_val - sig_val
                    })
                elif es_venta: 
                    ventas_data.append({
                        "Activo": tck,
                        "En Cartera": "⚠️ PELIGRO" if en_cartera(tck, cartera_set) else "No",
                        "Precio Cierre": p_val,
                        "Desviación (vs SMA50)": ((p_val - s50_val) / s50_val) * 100,
                        "Fuga Inst. (vs VWAP)": ((p_val - vwap_val) / vwap_val) * 100,
                        "Caída MACD (Hist)": macd_val - sig_val
                    })
            except: pass
            
        status_text.text("Escaneo cuantitativo finalizado con éxito.")
        
        def color_positivo(val):
            if isinstance(val, str): return ''
            color = '#26A69A' if val > 0 else '#EF5350' if val < 0 else 'gray'
            return f'color: {color}; font-weight: bold;'
            
        def color_alerta(val):
            if "PELIGRO" in str(val): return 'color: #EF5350; font-weight: bold;'
            elif "SÍ" in str(val): return 'color: #26A69A; font-weight: bold;'
            return ''

        st.markdown("#### 🟢 Activos con Señal de COMPRA Fuerte (Alineación Alcista Total)")
        if compras_data:
            df_compras = pd.DataFrame(compras_data)
            styler_compras = df_compras.style.format({
                "Precio Cierre": "${:.2f}",
                "Tendencia (vs SMA50)": "{:.2f}%",
                "Apoyo Inst. (vs VWAP)": "{:.2f}%",
                "Fuerza MACD (Hist)": "{:.3f}"
            }).map(color_positivo, subset=["Tendencia (vs SMA50)", "Apoyo Inst. (vs VWAP)", "Fuerza MACD (Hist)"]).map(color_alerta, subset=["En Cartera"])
            st.dataframe(styler_compras, use_container_width=True)
        else:
            st.info("Ningún activo de su base de datos presenta alineación de compra perfecta en este momento.")
            
        st.markdown("#### 🔴 Activos con Señal de VENTA Fuerte (Alineación Bajista Total)")
        if ventas_data:
            df_ventas = pd.DataFrame(ventas_data)
            styler_ventas = df_ventas.style.format({
                "Precio Cierre": "${:.2f}",
                "Desviación (vs SMA50)": "{:.2f}%",
                "Fuga Inst. (vs VWAP)": "{:.2f}%",
                "Caída MACD (Hist)": "{:.3f}"
            }).map(color_positivo, subset=["Desviación (vs SMA50)", "Fuga Inst. (vs VWAP)", "Caída MACD (Hist)"]).map(color_alerta, subset=["En Cartera"])
            st.dataframe(styler_ventas, use_container_width=True)
        else:
            st.info("Ningún activo presenta una estructura de colapso bajista total.")
            
        with st.expander("💡 ¿Cómo lee el Screener las oportunidades? (Teoría de Modelos Algorítmicos)"):
            st.write("Al igual que los robots de seguimiento de tendencias descritos por *Y. Hilpisch*, esta tabla no se basa en opiniones, sino en la validación simultánea de 3 variables:")
            st.write("1. **Tendencia (SMA50):** Filtro principal. Solo compramos si el precio actual está superando estadísticamente la media del último trimestre bursátil.")
            st.write("2. **Fuerza MACD:** Verifica que el cruce de medias exponenciales de corto plazo esté generando una aceleración del precio hacia arriba (Momentum).")
            st.write("3. **Apoyo Inst. (VWAP):** La métrica de mercado más usada por *Hedge Funds*. Nos asegura que estamos comprando por encima del 'precio de equilibrio' del dinero institucional, lo que significa que el mercado tiene incentivos para defender la subida.")
            st.write("📌 *Recomendación:* Utilice esta tabla interactiva ordenando por 'Apoyo Inst.' o 'Fuerza MACD' para elegir los activos con la matemática más robusta.")

# --- PESTAÑA 2: TÉCNICO ---
with tab_tecnico:
    if ticker_seleccionado and ticker_seleccionado != "Ninguno":
        ticker_ar = ticker_seleccionado if ticker_seleccionado.endswith(".BA") else f"{ticker_seleccionado}.BA"
        ticker_us = ticker_seleccionado.replace(".BA", "")
        try:
            info_us = yf.Ticker(ticker_us).info
            nombre_oficial = info_us.get('longName', info_us.get('shortName', ticker_us))
            st.markdown(f"### 📈 {nombre_oficial} | {periodo_visual}")
            col_us, col_ar = st.columns(2)
            with col_us:
                st.markdown(f"**Mercado EEUU ({ticker_us}) - USD**")
                df_us_full, df_us_recortado = descargar_y_procesar(ticker_us, intervalo_yf, dias_recorte, es_eeuu=True)
                if not df_us_recortado.empty:
                    st.metric(label="Precio Cierre (USD)", value=f"${df_us_recortado['Close'].iloc[-1]:.2f}", delta=f"{calcular_variacion(df_us_recortado, 1):.2f}% Diario")
                    st.write(f"📈 Var. Semanal: **{calcular_variacion(df_us_recortado, 5):.2f}%** | 📅 Mensual: **{calcular_variacion(df_us_recortado, 20):.2f}%**")
                    
                    vol_compras_us = df_us_recortado[df_us_recortado['Close'] >= df_us_recortado['Open']]['Volume'].sum()
                    vol_ventas_us = df_us_recortado[df_us_recortado['Close'] < df_us_recortado['Open']]['Volume'].sum()
                    st.markdown(f"Volumen Operado: <span class='vol-compra'>Compras: {formatear_volumen(vol_compras_us)}</span> | <span class='vol-venta'>Ventas: {formatear_volumen(vol_ventas_us)}</span>", unsafe_allow_html=True)
                    
                    precio_post = info_us.get('postMarketPrice')
                    var_post = info_us.get('postMarketChangePercent') 
                    precio_pre = info_us.get('preMarketPrice')
                    var_pre = info_us.get('preMarketChangePercent')
                    texto_ext = ""
                    if precio_post: texto_ext = f"🌙 <b>Post-Market:</b> ${precio_post:.2f} ({var_post:.2f}%)" if var_post else f"🌙 <b>Post-Market:</b> ${precio_post:.2f}"
                    elif precio_pre: texto_ext = f"☀️ <b>Pre-Market:</b> ${precio_pre:.2f} ({var_pre:.2f}%)" if var_pre else f"☀️ <b>Pre-Market:</b> ${precio_pre:.2f}"
                    if texto_ext: st.markdown(f"<div class='texto-extendido'>{texto_ext}</div>", unsafe_allow_html=True)
                    
                    st.plotly_chart(crear_grafico_velas(df_us_recortado, f"Gráfico {ticker_us} (EEUU)"), use_container_width=True)
                    estado_us, clase_us = evaluar_estado_tecnico(df_us_recortado)
                    st.markdown(f"<div class='{clase_us}'>Señal Técnica: {estado_us}</div>", unsafe_allow_html=True)
                    
                    with st.expander("💡 Análisis Dinámico del Gráfico Técnico", expanded=True):
                        precio = df_us_recortado['Close'].iloc[-1]
                        sma50 = df_us_recortado['SMA_50'].iloc[-1] if not pd.isna(df_us_recortado['SMA_50'].iloc[-1]) else precio
                        macd = df_us_recortado['MACD'].iloc[-1]
                        signal = df_us_recortado['Signal'].iloc[-1]
                        vwap = df_us_recortado['VWAP'].iloc[-1] if not pd.isna(df_us_recortado['VWAP'].iloc[-1]) else precio
                        
                        tendencia = "alcista" if precio > sma50 else "bajista"
                        pos_precio = "por encima" if tendencia == "alcista" else "por debajo"
                        momentum = "fuerza compradora activa (MACD sobre su Señal)" if macd > signal else "presión vendedora (MACD bajo su Señal)"
                        inst_status = "acumulación institucional activa (precio sobre VWAP)" if precio > vwap else "distribución institucional (precio bajo VWAP)"
                        
                        st.write(f"El análisis matemático indica que **{ticker_us}** se encuentra en una **tendencia de mediano plazo {tendencia}**, dado que su precio actual de ${precio:.2f} se sostiene {pos_precio} de la Media Móvil de 50 días (${sma50:.2f}). El oscilador MACD muestra **{momentum}**. Finalmente, el volumen revela **{inst_status}**, con un precio promedio ponderado en los ${vwap:.2f}.")
                else: st.warning("Sin datos en este periodo.")

            with col_ar:
                st.markdown(f"**Mercado ARG ({ticker_ar}) - ARS**")
                df_ar_full, df_ar_recortado = descargar_y_procesar(ticker_ar, intervalo_yf, dias_recorte, es_eeuu=False)
                if not df_ar_recortado.empty:
                    st.metric(label="Precio Cierre (ARS)", value=f"${df_ar_recortado['Close'].iloc[-1]:.2f}", delta=f"{calcular_variacion(df_ar_recortado, 1):.2f}% Diario")
                    st.write(f"📈 Var. Semanal: **{calcular_variacion(df_ar_recortado, 5):.2f}%** | 📅 Mensual: **{calcular_variacion(df_ar_recortado, 20):.2f}%**")
                    
                    vol_compras_ar = df_ar_recortado[df_ar_recortado['Close'] >= df_ar_recortado['Open']]['Volume'].sum()
                    vol_ventas_ar = df_ar_recortado[df_ar_recortado['Close'] < df_ar_recortado['Open']]['Volume'].sum()
                    st.markdown(f"Volumen Operado: <span class='vol-compra'>Compras: {formatear_volumen(vol_compras_ar)}</span> | <span class='vol-venta'>Ventas: {formatear_volumen(vol_ventas_ar)}</span>", unsafe_allow_html=True)
                    
                    st.plotly_chart(crear_grafico_velas(df_ar_recortado, f"Gráfico {ticker_ar} (Argentina)"), use_container_width=True)
                    estado_ar, clase_ar = evaluar_estado_tecnico(df_ar_recortado)
                    st.markdown(f"<div class='{clase_ar}'>Señal Técnica: {estado_ar}</div>", unsafe_allow_html=True)
                    
                    with st.expander("💡 Análisis Dinámico del Gráfico Técnico", expanded=True):
                        precio_ar = df_ar_recortado['Close'].iloc[-1]
                        sma50_ar = df_ar_recortado['SMA_50'].iloc[-1] if not pd.isna(df_ar_recortado['SMA_50'].iloc[-1]) else precio_ar
                        macd_ar = df_ar_recortado['MACD'].iloc[-1]
                        signal_ar = df_ar_recortado['Signal'].iloc[-1]
                        vwap_ar = df_ar_recortado['VWAP'].iloc[-1] if not pd.isna(df_ar_recortado['VWAP'].iloc[-1]) else precio_ar
                        
                        tendencia_ar = "alcista" if precio_ar > sma50_ar else "bajista"
                        pos_precio_ar = "por encima" if tendencia_ar == "alcista" else "por debajo"
                        momentum_ar = "fuerza compradora activa (MACD sobre su Señal)" if macd_ar > signal_ar else "presión vendedora (MACD bajo su Señal)"
                        inst_status_ar = "apoyo comprador (Precio > VWAP)" if precio_ar > vwap_ar else "resistencia vendedora (Precio < VWAP)"
                        
                        st.write(f"En el mercado local, **{ticker_ar}** presenta una **tendencia {tendencia_ar}**, al cotizar {pos_precio_ar} de su SMA 50. El MACD refleja **{momentum_ar}** y el volumen institucional marca **{inst_status_ar}**. *(Nota: Gráficos locales afectados por CCL)*.")
                        
            st.markdown("""
            ---
            **Referencias de los Gráficos:**
            * **Medias Móviles:** Azul (SMA 21), Naranja (SMA 50), Roja (SMA 200). 
            * **VWAP Institucional:** Línea Punteada Púrpura. Representa el precio promedio al que compraron los grandes fondos.
            * **MACD:** 🟢 Estrellas Verdes (Compra). 🔴 Estrellas Rojas (Venta).
            """)
        except Exception as e: st.error(f"Error procesando los datos.")

# --- PESTAÑA 3: FUNDAMENTAL ---
with tab_fundamental:
    if ticker_seleccionado and ticker_seleccionado != "Ninguno":
        ticker_us_base = ticker_seleccionado.replace(".BA", "")
        try: nombre_oficial_ia = yf.Ticker(ticker_us_base).info.get('shortName', ticker_us_base)
        except: nombre_oficial_ia = ticker_us_base
        st.markdown(f"## 🏢 Panel Fundamental: {nombre_oficial_ia}")
        
        if st.button("Generar Análisis Fundamental", type="primary"):
            with st.spinner("Extrayendo balances contables corporativos..."):
                try:
                    activo_info = yf.Ticker(ticker_us_base).info
                    pe_ratio = format_num(activo_info.get('trailingPE'))
                    fwd_pe = format_num(activo_info.get('forwardPE'))
                    pb_ratio = format_num(activo_info.get('priceToBook'))
                    roe = format_num(activo_info.get('returnOnEquity'))
                    deuda_capital = format_num(activo_info.get('debtToEquity'))
                    margen_operativo = format_num(activo_info.get('operatingMargins'))
                    precio_actual = format_num(activo_info.get('currentPrice', activo_info.get('regularMarketPrice')))
                    precio_objetivo = format_num(activo_info.get('targetMeanPrice'))
                    free_cashflow = format_num(activo_info.get('freeCashflow'))
                    operating_cashflow = format_num(activo_info.get('operatingCashflow'))
                    rev, net = None, None
                    
                    col_graf1, col_graf2 = st.columns([1, 1])
                    with col_graf1:
                        st.markdown("#### Valor Razonable (Target de Analistas)")
                        if precio_objetivo > 0 and precio_actual > 0:
                            fig_gauge = go.Figure(go.Indicator(
                                mode = "gauge+number+delta", value = precio_actual, domain = {'x': [0, 1], 'y': [0, 1]}, number = {'prefix': "$"},
                                delta = {'reference': precio_objetivo, 'position': "bottom", 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
                                gauge = {'axis': {'range': [None, max(precio_actual, precio_objetivo) * 1.3]}, 'bar': {'color': "darkblue"},
                                         'steps': [{'range': [0, precio_objetivo], 'color': "#A5D6A7"}, {'range': [precio_objetivo, max(precio_actual, precio_objetivo) * 1.3], 'color': "#EF9A9A"}],
                                         'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': precio_actual}}
                            ))
                            fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
                            st.plotly_chart(fig_gauge, use_container_width=True)
                        else: st.warning("Datos insuficientes para calcular el Valor Razonable.")
                        st.info("💡 **Análisis de Valor:** Compara el precio actual frente al consenso de Wall Street. La zona verde señala descuento potencial.")

                    with col_graf2:
                        st.markdown("#### Evolución de Ingresos vs Beneficios")
                        try:
                            fin = yf.Ticker(ticker_us_base).financials
                            if not fin.empty and 'Total Revenue' in fin.index and 'Net Income' in fin.index:
                                rev = fin.loc['Total Revenue'].dropna().iloc[::-1]
                                net = fin.loc['Net Income'].dropna().iloc[::-1]
                                fig_fin = go.Figure()
                                fig_fin.add_trace(go.Bar(x=rev.index.year, y=rev.values, name='Ingresos Totales', marker_color='#26A69A'))
                                fig_fin.add_trace(go.Bar(x=net.index.year, y=net.values, name='Beneficio Neto', marker_color='#1E88E5'))
                                fig_fin.update_layout(template="plotly_white", barmode='group', height=300, margin=dict(l=20, r=20, t=30, b=20), legend=dict(orientation="h", y=-0.2))
                                st.plotly_chart(fig_fin, use_container_width=True)
                            else: st.info("Estados contables no disponibles para este activo.")
                        except: st.info("Estados contables no disponibles.")
                        st.info("💡 **Análisis Contable:** Evalúa si el crecimiento de las ventas se traduce en ganancias reales netas. La sincronía alcista es ideal.")

                    st.markdown("---")
                    st.markdown("### 📊 Tabla de Métricas (Semáforo de Salud)")
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns(4)
                        i_pe, col_pe = evaluar_pe(pe_ratio)
                        with c1: render_metric_nativo("Ratio P/E", f"{pe_ratio:.2f}x" if pe_ratio>0 else "N/A", col_pe, i_pe)
                        i_pb, col_pb = evaluar_pb(pb_ratio)
                        with c2: render_metric_nativo("Ratio P/B", f"{pb_ratio:.2f}x" if pb_ratio>0 else "N/A", col_pb, i_pb)
                        i_roe, col_roe = evaluar_porcentaje(roe)
                        with c3: render_metric_nativo("ROE", f"{roe*100:.2f}%" if roe!=0 else "N/A", col_roe, i_roe)
                        i_margen, col_margen = evaluar_porcentaje(margen_operativo)
                        with c4: render_metric_nativo("Margen Operativo", f"{margen_operativo*100:.2f}%" if margen_operativo!=0 else "N/A", col_margen, i_margen)

                        st.markdown("<br>", unsafe_allow_html=True)
                        c5, c6, c7, c8 = st.columns(4)
                        i_deuda, col_deuda = evaluar_deuda(deuda_capital)
                        with c5: render_metric_nativo("Deuda/Capital", f"{deuda_capital:.2f}%" if deuda_capital>0 else "0%", col_deuda, i_deuda)
                        i_ocf, col_ocf = evaluar_flujo(operating_cashflow)
                        with c6: render_metric_nativo("Operating CashFlow", f"${operating_cashflow/1e9:.2f} B" if operating_cashflow!=0 else "N/A", col_ocf, i_ocf)
                        i_fcf, col_fcf = evaluar_flujo(free_cashflow)
                        with c7: render_metric_nativo("Free CashFlow", f"${free_cashflow/1e9:.2f} B" if free_cashflow!=0 else "N/A", col_fcf, i_fcf)
                    
                    st.caption("🟢 **Verde:** Excelente/Infravalorado | 🟡 **Amarillo:** Neutral/Razonable | 🔴 **Rojo:** Riesgo/Sobrevalorado")
                    
                    st.markdown("### 📝 Conclusión Fundamental Consolidada")
                    fortalezas, debilidades = [], []
                    if pe_ratio > 0 and pe_ratio < 20: fortalezas.append(f"un multiplicador de beneficios atractivo (PER {pe_ratio:.1f}x)")
                    elif pe_ratio >= 25: debilidades.append(f"una valoración exigente (PER {pe_ratio:.1f}x)")
                    if roe > 0.15: fortalezas.append(f"excelente eficiencia generando retorno (ROE {roe*100:.1f}%)")
                    elif roe > 0 and roe < 0.05: debilidades.append(f"baja rentabilidad financiera (ROE {roe*100:.1f}%)")
                    if margen_operativo > 0.15: fortalezas.append(f"fuertes márgenes operativos ({margen_operativo*100:.1f}%)")
                    elif margen_operativo < 0.05 and margen_operativo != 0: debilidades.append("márgenes operativos sumamente ajustados")
                    if 0 <= deuda_capital < 50: fortalezas.append(f"endeudamiento bajo y conservador (D/E {deuda_capital:.1f}%)")
                    elif deuda_capital > 100: debilidades.append(f"un nivel de deuda sobre capital elevado (D/E {deuda_capital:.1f}%)")
                    if free_cashflow > 0: fortalezas.append("sólida generación de Flujo de Caja Libre positivo")
                    elif free_cashflow < 0: debilidades.append("quema de caja operativa (FCF negativo)")

                    reporte = f"El presente análisis cuantitativo para **{nombre_oficial_ia}** abarca la lectura de su valoración y salud contable. "
                    if precio_objetivo > 0 and precio_actual > 0:
                        if precio_actual < precio_objetivo: reporte += f"Desde la óptica de valoración por consenso (Gráfico 1), el activo cotiza con un **descuento frente a su Valor Razonable** (${precio_objetivo:.2f}). "
                        else: reporte += f"Desde la óptica de valoración (Gráfico 1), el activo cotiza actualmente **por encima del precio objetivo** (${precio_objetivo:.2f}), indicando una posible sobrevaloración técnica. "
                            
                    try:
                        if rev is not None and net is not None and len(rev) >= 2 and len(net) >= 2:
                            crec_rev = (rev.iloc[-1] - rev.iloc[-2]) / rev.iloc[-2]
                            crec_net = (net.iloc[-1] - net.iloc[-2]) / net.iloc[-2]
                            if crec_rev > 0 and crec_net > 0: reporte += "El desempeño contable reciente (Gráfico 2) muestra una clara tendencia expansiva en ventas y ganancias. "
                            elif crec_rev > 0 and crec_net <= 0: reporte += "El desempeño contable (Gráfico 2) es mixto: las ventas crecen pero los márgenes netos se están contrayendo. "
                            else: reporte += "El historial contable demuestra un proceso de contracción en sus ingresos principales. "
                    except: pass
                        
                    if fortalezas: reporte += "\n\n**A nivel de balance, destacan como pilares fundamentales** " + ", y ".join(fortalezas) + ". "
                    if debilidades: reporte += "Por el contrario, **presenta debilidades en** " + ", e ".join(debilidades) + ". "
                        
                    if len(fortalezas) >= len(debilidades) and (precio_actual < precio_objetivo if precio_objetivo>0 else True):
                        st.success(reporte + "\n\n🎯 **VEREDICTO:** Fundamentos robustos y posicionamiento altamente favorable para la inversión.")
                    elif len(debilidades) > len(fortalezas):
                        st.error(reporte + "\n\n🎯 **VEREDICTO:** Estrés fundamental o sobrevaloración manifiesta. Se sugiere precaución.")
                    else:
                        st.warning(reporte + "\n\n🎯 **VEREDICTO:** Salud corporativa Neutral. Mantener monitoreo antes de ampliar ponderación.")
                except Exception as e: st.error(f"Error al obtener los datos fundamentales. ({e})")

# --- PESTAÑA 4: PORTFOLIO ---
with tab_portfolio:
    st.markdown("## 💼 Panel de Gestión de Portfolio y Riesgo Institucional")
    col_ccl, col_mep, col_esp = st.columns([1, 1, 2])
    col_ccl.metric("🇺🇸 Dólar CCL", f"${dolar_ccl:.2f}")
    col_mep.metric("🇦🇷 Dólar MEP", f"${dolar_mep:.2f}")
    st.markdown("---")
    
    def mapear_ticker_argentino(tck):
        tck_upper = str(tck).strip().upper()
        return {"BRKB": "BRK-B"}.get(tck_upper, tck_upper)

    def parsear_excel_estricto(df):
        df.rename(columns=lambda x: str(x).strip(), inplace=True)
        c_tipo = 'Tipo Transacción' if 'Tipo Transacción' in df.columns else None
        c_tck = 'Simbolo' if 'Simbolo' in df.columns else 'Ticker' if 'Ticker' in df.columns else 'Especie'
        c_cant = 'Cantidad' if 'Cantidad' in df.columns else 'Titulos'
        c_p_sin = 'Precio Ponderado' if 'Precio Ponderado' in df.columns else 'Precio'
        c_total = 'Total' if 'Total' in df.columns else 'Monto'
        
        if c_tck in df.columns and c_cant in df.columns and c_p_sin in df.columns:
            res = []
            for tck, group in df.groupby(c_tck):
                cant_total, inv_sin_imp, inv_con_imp, cant_comprada = 0, 0, 0, 0
                tck_corregido = mapear_ticker_argentino(tck)
                for _, row in group.iterrows():
                    tipo = str(row[c_tipo]).strip().lower() if c_tipo else 'compra'
                    try: cant = float(str(row[c_cant]).replace(',', ''))
                    except: cant = 0.0
                    if cant <= 0: continue
                    try: p_sin = float(str(row[c_p_sin]).replace(',', ''))
                    except: p_sin = 0.0
                    try: total_con_imp = float(str(row[c_total]).replace(',', '')) if c_total in df.columns else (cant * p_sin)
                    except: total_con_imp = (cant * p_sin)
                    if 'venta' not in tipo:
                        cant_total += cant; cant_comprada += cant
                        inv_sin_imp += (cant * p_sin); inv_con_imp += total_con_imp
                    else: cant_total -= cant 
                if cant_total > 0:
                    res.append({'Ticker_Original': str(tck).strip().upper(), 'Ticker_YF': tck_corregido, 'Cantidad': cant_total,
                                'P. Medio (Sin Imp)': inv_sin_imp / cant_comprada if cant_comprada > 0 else 0,
                                'P. Medio (Con Imp)': inv_con_imp / cant_comprada if cant_comprada > 0 else 0})
            return pd.DataFrame(res)
        return None

    archivo = st.file_uploader("Subir Cartera (Excel/CSV)", type=["csv", "xlsx", "xls"])
    if archivo is not None:
        if archivo.name.endswith('.csv'): df_crudo = pd.read_csv(archivo)
        else: df_crudo = pd.read_excel(archivo)
        df_limpio = parsear_excel_estricto(df_crudo)
        if df_limpio is not None and not df_limpio.empty:
            resultados, total_ars, total_ccl = [], 0, 0
            with st.spinner("Cotizando cartera..."):
                for index, row in df_limpio.iterrows():
                    tck_yf = row['Ticker_YF']
                    tck_ar = tck_yf if tck_yf.endswith(".BA") else f"{tck_yf}.BA"
                    hist = yf.Ticker(tck_ar).history(period="1d")
                    if not hist.empty:
                        p_actual = hist['Close'].iloc[-1] 
                        val_ars = row['Cantidad'] * p_actual
                        val_usd = val_ars / dolar_ccl
                        total_ars += val_ars; total_ccl += val_usd
                        resultados.append({"Activo": row['Ticker_Original'], "Símbolo YF": tck_ar, "Cant.": row['Cantidad'],
                                           "P. Medio (Con Imp)": row['P. Medio (Con Imp)'], "Precio Actual": p_actual,
                                           "Variación": ((p_actual - row['P. Medio (Con Imp)']) / row['P. Medio (Con Imp)']) * 100, 
                                           "Total (ARS)": val_ars})
            if resultados:
                st.markdown("### 💰 Resumen de Valor Total")
                c_tot1, c_tot2, c_tot3 = st.columns(3)
                c_tot1.metric("🇦🇷 Total (ARS)", f"${total_ars:,.2f}")
                c_tot2.metric("🇺🇸 Total (USD CCL)", f"${total_ccl:,.2f}")
                df_resultados = pd.DataFrame(resultados)
                styler = df_resultados.drop(columns=["Símbolo YF"]).style.format({
                    "P. Medio (Con Imp)": "${:,.2f}", "Precio Actual": "${:,.2f}", "Variación": "{:,.2f}%", "Total (ARS)": "${:,.2f}"
                }).map(lambda val: f'color: {"#26A69A" if val > 0 else "#EF5350" if val < 0 else "gray"}; font-weight: bold;', subset=['Variación'])
                st.dataframe(styler, use_container_width=True)
                
                st.session_state.portfolio_total_usd = total_ccl
                
                with st.spinner("Calculando Matrices..."):
                    try:
                        tickers_cartera = df_resultados['Símbolo YF'].tolist()
                        data_hist = yf.download(tickers_cartera + ['SPY.BA'], period="1y", interval="1d", progress=False)['Close']
                        if isinstance(data_hist, pd.Series): data_hist = pd.DataFrame(data_hist, columns=tickers_cartera + ['SPY.BA'])
                        data_hist = data_hist.dropna(axis=1, how='all')
                        retornos = data_hist.pct_change().dropna()
                        cols_activos = [c for c in tickers_cartera if c in retornos.columns]
                        
                        if len(cols_activos) > 1:
                            st.markdown("#### 🗺️ Diversificación Real: Mapa de Calor de Correlación")
                            corr_matrix = retornos[cols_activos].corr()
                            corr_matrix.columns = [c.replace('.BA', '') for c in corr_matrix.columns]
                            corr_matrix.index = corr_matrix.columns
                            fig_corr = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                            fig_corr.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
                            st.plotly_chart(fig_corr, use_container_width=True)
                            
                            with st.expander("💡 Análisis Dinámico de la Correlación", expanded=True):
                                st.write("El Mapa de Calor revela matemáticamente cómo interactúan los activos de su cartera entre sí. Un bloque **Rojo Oscuro (cercano a 1.00)** indica que esos activos suben y bajan de manera idéntica; tener demasiados bloques rojos destruye la verdadera diversificación. Por el contrario, los bloques en **Tonos Azules o Blancos (cercanos a 0)** representan activos que se mueven de forma independiente, protegiendo su cartera cuando un sector específico colapsa.")

                        pesos_dict = {row['Símbolo YF']: row['Total (ARS)']/total_ars for row in resultados}
                        pesos = np.array([pesos_dict.get(c, 0) for c in cols_activos])
                        if np.sum(pesos) > 0: pesos = pesos / np.sum(pesos) 
                        port_ret = retornos[cols_activos].dot(pesos)
                        
                        st.session_state.portfolio_history = port_ret
                        st.session_state.portfolio_tickers = cols_activos
                        st.session_state.portfolio_weights = pesos
                        
                        c_q1, c_q2 = st.columns(2)
                        with c_q1:
                            with st.container(border=True):
                                st.markdown("#### 📈 Markowitz (Diversificación)")
                                m1, m2 = st.columns(2)
                                m1.metric("Rendimiento Anualizado", f"{port_ret.mean() * 252 * 100:.2f}%")
                                m2.metric("Volatilidad Anual", f"{np.sqrt(np.dot(pesos.T, np.dot(retornos[cols_activos].cov() * 252, pesos))) * 100:.2f}%")
                        with c_q2:
                            with st.container(border=True):
                                st.markdown("#### 🚨 Gestión de Riesgo Institucional")
                                v1, v2 = st.columns(2)
                                v1.metric("Beta (vs Mercado SPY)", f"{np.cov(port_ret, retornos['SPY.BA'])[0, 1] / np.cov(port_ret, retornos['SPY.BA'])[1, 1]:.2f}" if 'SPY.BA' in retornos.columns else "N/A", help="Mide cuánto se mueve tu cartera respecto al mercado. >1.00 es agresivo, <1.00 es defensivo.")
                                v2.metric("VaR (95%)", f"{np.percentile(port_ret, 5) * 100:.2f}%", help="Value at Risk. Existe un 5% de probabilidad de que tu cartera pierda este porcentaje o más en un solo día.")
                            
                    except Exception as e: st.caption(f"Datos insuficientes para matrices cuantitativas.")
        else: st.error("❌ Archivo inválido.")

# --- PESTAÑA 5: MODELOS PREDICTIVOS ---
with tab_predictivo:
    st.markdown("## 🤖 Modelos Predictivos e Inteligencia Artificial")
    modo_simulacion = st.radio("Seleccione el Modelo Predictivo:", 
                               ["Machine Learning: Mi Cartera Completa (IA)",
                                "Monte Carlo: Mi Cartera Completa",
                                "Machine Learning: Activo Individual (IA)",
                                "Monte Carlo: Activo Individual"], horizontal=True)
    st.markdown("---")

    if modo_simulacion == "Machine Learning: Mi Cartera Completa (IA)":
        if not SKLEARN_AVAILABLE: st.error("⚠️ Ejecute `pip install scikit-learn` en su terminal.")
        elif st.session_state.portfolio_history is not None:
            if st.button("Entrenar IA Patrimonial", type="primary"):
                with st.spinner("Entrenando algoritmo..."):
                    try:
                        retornos_portfolio = st.session_state.portfolio_history
                        log_returns = np.log(1 + retornos_portfolio)
                        precio_portfolio = (log_returns.cumsum().apply(np.exp)) * 100
                        df_ml_port = pd.DataFrame({'Close': precio_portfolio})
                        df_ml_port['Retorno_Diario'] = df_ml_port['Close'].pct_change()
                        df_ml_port['SMA_21_Ratio'] = df_ml_port['Close'] / df_ml_port['Close'].rolling(window=21).mean()
                        df_ml_port['SMA_50_Ratio'] = df_ml_port['Close'] / df_ml_port['Close'].rolling(window=50).mean()
                        df_ml_port['Volatilidad_5d'] = df_ml_port['Retorno_Diario'].rolling(window=5).std()
                        ema_12 = df_ml_port['Close'].ewm(span=12, adjust=False).mean()
                        ema_26 = df_ml_port['Close'].ewm(span=26, adjust=False).mean()
                        df_ml_port['MACD'] = ema_12 - ema_26
                        df_ml_port['Target'] = (df_ml_port['Close'].shift(-1) > df_ml_port['Close']).astype(int)
                        df_ml_port = df_ml_port.dropna()
                        
                        if len(df_ml_port) > 50:
                            features_cols = ['Retorno_Diario', 'SMA_21_Ratio', 'SMA_50_Ratio', 'Volatilidad_5d', 'MACD']
                            X_pred_hoy = df_ml_port.iloc[-1:][features_cols]
                            data_fit = df_ml_port.iloc[:-1]
                            X, y = data_fit[features_cols], data_fit['Target']
                            split = int(len(X) * 0.8)
                            X_train, X_test, y_train, y_test = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]
                            
                            modelo_rf = RandomForestClassifier(n_estimators=150, random_state=42, max_depth=5)
                            modelo_rf.fit(X_train, y_train)
                            precision = accuracy_score(y_test, modelo_rf.predict(X_test))
                            prediccion_final = modelo_rf.predict(X_pred_hoy)[0]
                            probabilidad = modelo_rf.predict_proba(X_pred_hoy)[0]
                            
                            st.markdown("### 📊 Resultados IA: Tendencia del Patrimonio")
                            c_ia1, c_ia2, c_ia3 = st.columns(3)
                            c_ia1.metric("Tasa Acierto (Examen)", f"{precision*100:.1f}%")
                            with c_ia2:
                                if prediccion_final == 1: st.markdown("<h3 style='color: #26A69A;'>📈 PATRIMONIO ALCISTA</h3>", unsafe_allow_html=True)
                                else: st.markdown("<h3 style='color: #EF5350;'>📉 PATRIMONIO BAJISTA</h3>", unsafe_allow_html=True)
                            prob_certera = probabilidad[1] if prediccion_final == 1 else probabilidad[0]
                            c_ia3.metric("Certeza IA", f"{prob_certera*100:.1f}%")
                            
                            with st.expander("💡 Análisis Dinámico del Motor Predictivo", expanded=True):
                                if prediccion_final == 1:
                                    st.write(f"Basándose en el entrenamiento histórico, la Inteligencia Artificial detectó que los parámetros de volatilidad, cruces de medias y momentum actuales del mercado son similares a escenarios pasados que desembocaron en subidas. Con un **{prob_certera*100:.1f}% de certidumbre matemática**, pronostica una ventana favorable para el crecimiento de la cartera en el corto plazo.")
                                else:
                                    st.write(f"La Inteligencia Artificial ha encontrado debilidades sistémicas en la acción del precio actual (presión técnica o agotamiento de medias). Con un **{prob_certera*100:.1f}% de confianza**, el algoritmo estima que el patrimonio enfrentará una corrección o presión a la baja en la próxima jornada, sugiriendo cautela.")
                        else: st.warning("Historial insuficiente.")
                    except Exception as e: st.error(f"Error IA Cartera: {e}")
        else: st.warning("⚠️ Primero cargue su Excel en 'Mi Portfolio'.")

    elif modo_simulacion == "Monte Carlo: Mi Cartera Completa":
        if st.session_state.portfolio_history is not None and st.session_state.portfolio_total_usd > 0:
            if st.button("Simular el Futuro Patrimonial", type="primary"):
                with st.spinner("Generando trayectorias estocásticas..."):
                    try:
                        retornos = st.session_state.portfolio_history
                        drift = np.log(1 + retornos).mean() - (0.5 * np.log(1 + retornos).var())
                        stdev = np.log(1 + retornos).std()
                        t_intervals, iterations = 126, 100
                        daily_returns = np.exp(drift + stdev * np.random.standard_normal((t_intervals, iterations)))
                        S0 = st.session_state.portfolio_total_usd
                        price_list = np.zeros_like(daily_returns)
                        price_list[0] = S0
                        for t in range(1, t_intervals): price_list[t] = price_list[t - 1] * daily_returns[t]
                            
                        fig_mc = go.Figure()
                        for i in range(iterations): fig_mc.add_trace(go.Scatter(y=price_list[:, i], mode='lines', line=dict(width=1, color='rgba(2, 119, 189, 0.1)'), showlegend=False))
                        fig_mc.add_trace(go.Scatter(y=price_list.mean(axis=1), mode='lines', name='Promedio Esperado', line=dict(color='red', width=3)))
                        fig_mc.update_layout(title="Proyección Patrimonial Monte Carlo", template="plotly_white", height=500)
                        st.plotly_chart(fig_mc, use_container_width=True)
                        
                        precio_promedio_final = price_list[-1].mean()
                        peor_escenario = np.percentile(price_list[-1], 5)
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        col_m1.metric("Capital Actual", f"${S0:,.2f} USD")
                        col_m2.metric("Capital Promedio (6m)", f"${precio_promedio_final:,.2f} USD")
                        col_m3.metric("Peor Escenario (Riesgo 5%)", f"${peor_escenario:,.2f} USD", delta_color="inverse")
                        
                        with st.expander("💡 Análisis Dinámico de la Simulación", expanded=True):
                            diff = precio_promedio_final - S0
                            if diff > 0:
                                st.write(f"El modelo estocástico proyecta una **esperanza matemática positiva**. Dada la volatilidad y deriva histórica de sus activos cruzados, el escenario central prevé un crecimiento hacia los **${precio_promedio_final:,.2f} USD**. Sin embargo, la dispersión de la 'telaraña' marca el riesgo real: en un escenario de estrés agudo (peor 5%), su capital correría peligro de retroceder hacia la cota de los **${peor_escenario:,.2f} USD**.")
                            else:
                                st.write(f"El modelo alerta sobre una **deriva bajista**. El escenario central proyecta que el capital podría retroceder hacia los **${precio_promedio_final:,.2f} USD**. La combinación actual de activos sugiere vulnerabilidad estructural; de desatarse el peor escenario estadístico (cola del 5%), el piso estimado de soporte patrimonial caería peligrosamente hasta los **${peor_escenario:,.2f} USD**.")
                    except Exception as e: st.error(f"Error Monte Carlo Cartera: {e}")
        else: st.warning("⚠️ Primero cargue su Excel en 'Mi Portfolio'.")

    elif modo_simulacion == "Machine Learning: Activo Individual (IA)":
        if ticker_seleccionado and ticker_seleccionado != "Ninguno":
            ticker_us_base = ticker_seleccionado.replace(".BA", "")
            if not SKLEARN_AVAILABLE: st.error("Librería sklearn no instalada.")
            elif st.button(f"Entrenar IA {ticker_us_base}", type="primary"):
                with st.spinner("Entrenando algoritmo individual..."):
                    try:
                        df_ml = yf.Ticker(ticker_us_base).history(period="2y")
                        if len(df_ml) > 100:
                            df_ml['Retorno_Diario'] = df_ml['Close'].pct_change()
                            df_ml['SMA_21_Ratio'] = df_ml['Close'] / df_ml['Close'].rolling(window=21).mean()
                            df_ml['SMA_50_Ratio'] = df_ml['Close'] / df_ml['Close'].rolling(window=50).mean()
                            df_ml['Volatilidad_5d'] = df_ml['Retorno_Diario'].rolling(window=5).std()
                            ema_12, ema_26 = df_ml['Close'].ewm(span=12, adjust=False).mean(), df_ml['Close'].ewm(span=26, adjust=False).mean()
                            df_ml['MACD'] = ema_12 - ema_26
                            df_ml['Target'] = (df_ml['Close'].shift(-1) > df_ml['Close']).astype(int)
                            df_ml = df_ml.dropna()
                            
                            features = ['Retorno_Diario', 'SMA_21_Ratio', 'SMA_50_Ratio', 'Volatilidad_5d', 'MACD']
                            X_hoy = df_ml.iloc[-1:][features]
                            data_f, X, y = df_ml.iloc[:-1], df_ml.iloc[:-1][features], df_ml.iloc[:-1]['Target']
                            split = int(len(X) * 0.8)
                            modelo_rf = RandomForestClassifier(n_estimators=150, random_state=42, max_depth=5)
                            modelo_rf.fit(X.iloc[:split], y.iloc[:split])
                            
                            precision = accuracy_score(y.iloc[split:], modelo_rf.predict(X.iloc[split:]))
                            pred = modelo_rf.predict(X_hoy)[0]
                            prob = modelo_rf.predict_proba(X_hoy)[0]
                            
                            st.markdown("### 📊 Resultados IA Individual")
                            c_ia1, c_ia2, c_ia3 = st.columns(3)
                            c_ia1.metric("Tasa Acierto", f"{precision*100:.1f}%")
                            with c_ia2:
                                if pred == 1: st.markdown("<h3 style='color: #26A69A;'>📈 ALCISTA</h3>", unsafe_allow_html=True)
                                else: st.markdown("<h3 style='color: #EF5350;'>📉 BAJISTA</h3>", unsafe_allow_html=True)
                            prob_certera = prob[1] if pred==1 else prob[0]
                            c_ia3.metric("Certeza IA", f"{prob_certera*100:.1f}%")
                            
                            with st.expander("💡 Análisis Dinámico del Motor Predictivo", expanded=True):
                                if pred == 1:
                                    st.write(f"Al auditar 2 años de datos, el algoritmo de Bosques Aleatorios encontró un patrón. Con un **{prob_certera*100:.1f}% de certidumbre**, estima que el entorno técnico de {ticker_us_base} favorece una jornada en verde para la próxima sesión.")
                                else:
                                    st.write(f"La Inteligencia Artificial ha detectado agotamiento. Con un nivel de confianza del **{prob_certera*100:.1f}%**, el modelo anticipa que {ticker_us_base} cerrará en números rojos en el próximo lapso bursátil.")

                        else: st.warning("Datos insuficientes.")
                    except Exception as e: st.error(f"Error IA Individual: {e}")
        else: st.info("Seleccione un activo.")

    elif modo_simulacion == "Monte Carlo: Activo Individual":
        if ticker_seleccionado and ticker_seleccionado != "Ninguno":
            ticker_us_base = ticker_seleccionado.replace(".BA", "")
            if st.button("Simular (Próximos 6m)", type="primary"):
                with st.spinner(f"Generando rutas para {ticker_us_base}..."):
                    try:
                        data_mc = yf.Ticker(ticker_us_base).history(period="1y")['Close']
                        if len(data_mc) > 50:
                            rets = np.log(1 + data_mc.pct_change().dropna())
                            drift = rets.mean() - (0.5 * rets.var())
                            daily_returns = np.exp(drift + rets.std() * np.random.standard_normal((126, 100)))
                            S0 = data_mc.iloc[-1]
                            price_list = np.zeros_like(daily_returns)
                            price_list[0] = S0
                            for t in range(1, 126): price_list[t] = price_list[t - 1] * daily_returns[t]
                                
                            fig_mc = go.Figure()
                            for i in range(100): fig_mc.add_trace(go.Scatter(y=price_list[:, i], mode='lines', line=dict(width=1, color='rgba(2, 119, 189, 0.1)'), showlegend=False))
                            fig_mc.add_trace(go.Scatter(y=price_list.mean(axis=1), mode='lines', name='Promedio', line=dict(color='red', width=3)))
                            fig_mc.update_layout(title=f"Monte Carlo - {ticker_us_base}", template="plotly_white", height=500)
                            st.plotly_chart(fig_mc, use_container_width=True)
                            
                            precio_promedio_final = price_list[-1].mean()
                            peor_escenario = np.percentile(price_list[-1], 5)
                            
                            col_m1, col_m2, col_m3 = st.columns(3)
                            col_m1.metric("Precio Actual", f"${S0:.2f}")
                            col_m2.metric("Promedio Esperado", f"${precio_promedio_final:.2f}")
                            col_m3.metric("Riesgo (Peor 5%)", f"${peor_escenario:.2f}")
                            
                            with st.expander("💡 Análisis Dinámico de la Simulación", expanded=True):
                                diff = precio_promedio_final - S0
                                if diff > 0:
                                    st.write(f"Para el activo {ticker_us_base}, el modelo proyecta un **desempeño central alcista** hacia los ${precio_promedio_final:.2f} (ganancia esperada de {(diff/S0)*100:.2f}%). El parámetro de Riesgo de Cola advierte que, de repetirse los picos de volatilidad del último año, el activo podría quebrar a la baja buscando el piso de los ${peor_escenario:.2f}.")
                                else:
                                    st.write(f"Para el activo {ticker_us_base}, el modelo proyecta una **fuerte presión técnica bajista** hacia los ${precio_promedio_final:.2f}. Se requiere máxima precaución de stop-loss, ya que en el 5% de los escenarios de pánico el precio colapsaría hasta la zona de los ${peor_escenario:.2f}.")
                        else: st.warning("Datos insuficientes.")
                    except Exception as e: st.error(f"Error Monte Carlo Individual: {e}")
        else: st.info("Seleccione un activo.")

# --- PESTAÑA 6: BACKTESTING ---
with tab_backtest:
    st.markdown("## ⏱️ Simulador de Backtesting (Algoritmos vs Buy & Hold)")
    
    modo_backtest = st.radio("Seleccione el Objetivo de Simulación:", ["Activo Individual (Menú Lateral)", "Mi Cartera Completa (Requiere cargar Excel)"], horizontal=True)
    st.markdown("---")
    
    with st.expander("💡 Guía Rápida - ¿Qué son las Medias Móviles (SMA)?", expanded=True):
        st.write("El robot utiliza dos métricas. La **SMA Rápida** sigue de cerca el precio nervioso de corto plazo, mientras que la **SMA Lenta** dictamina la tendencia silenciosa de fondo. El algoritmo compra cuando la curva rápida rompe hacia arriba a la lenta (confirmación alcista), y vende todo para refugiarse en dólares cuando la corta hacia abajo (inminente colapso).")
    
    c_b1, c_b2, c_b3, c_b4 = st.columns(4)
    with c_b1:
        capital_ars = st.number_input("Inversión Inicial (ARS):", min_value=1000.0, value=1000000.0, step=50000.0)
        capital_usd = capital_ars / dolar_ccl
        st.caption(f"≈ **${capital_usd:,.2f} USD CCL**")
    with c_b2:
        anos_backtest = st.selectbox("Años de historia:", [1, 2, 5, 10], index=1)
    with c_b3:
        sma_rapida = st.number_input("SMA Rápida (Días)", min_value=5, max_value=50, value=21)
    with c_b4:
        sma_lenta = st.number_input("SMA Lenta (Días)", min_value=20, max_value=200, value=50)

    if st.button("🚀 Ejecutar Backtesting Estratégico", type="primary"):
        if modo_backtest == "Activo Individual (Menú Lateral)":
            if ticker_seleccionado and ticker_seleccionado != "Ninguno":
                ticker_us_base = ticker_seleccionado.replace(".BA", "")
                with st.spinner(f"Simulando {anos_backtest} años para {ticker_us_base}..."):
                    try:
                        data_bt = yf.Ticker(ticker_us_base).history(period=f"{anos_backtest}y")
                        if len(data_bt) > sma_lenta:
                            data_bt['SMA_Fast'] = data_bt['Close'].rolling(window=sma_rapida).mean()
                            data_bt['SMA_Slow'] = data_bt['Close'].rolling(window=sma_lenta).mean()
                            data_bt['Signal'] = np.where(data_bt['SMA_Fast'] > data_bt['SMA_Slow'], 1, 0)
                            data_bt['Retorno_Mercado'] = data_bt['Close'].pct_change()
                            data_bt['Retorno_Estrategia'] = data_bt['Retorno_Mercado'] * data_bt['Signal'].shift(1)
                            data_bt = data_bt.dropna()
                            data_bt['Capital_BuyHold'] = capital_usd * (1 + data_bt['Retorno_Mercado']).cumprod()
                            data_bt['Capital_Estrategia'] = capital_usd * (1 + data_bt['Retorno_Estrategia']).cumprod()
                            
                            fig_bt = go.Figure()
                            fig_bt.add_trace(go.Scatter(x=data_bt.index, y=data_bt['Capital_BuyHold'], mode='lines', name='Buy & Hold (Gris)', line=dict(color='gray', width=2)))
                            fig_bt.add_trace(go.Scatter(x=data_bt.index, y=data_bt['Capital_Estrategia'], mode='lines', name=f'Robot SMA (Verde)', line=dict(color='#26A69A', width=3)))
                            fig_bt.update_layout(title=f"Crecimiento del Capital Proyectado en USD CCL ({ticker_us_base})", template="plotly_white", height=450)
                            st.plotly_chart(fig_bt, use_container_width=True)
                            
                            final_bh = data_bt['Capital_BuyHold'].iloc[-1]
                            final_est = data_bt['Capital_Estrategia'].iloc[-1]
                            max_dd_bh = ((data_bt['Capital_BuyHold'] / data_bt['Capital_BuyHold'].cummax()) - 1).min() * 100
                            max_dd_est = ((data_bt['Capital_Estrategia'] / data_bt['Capital_Estrategia'].cummax()) - 1).min() * 100
                            trades = (data_bt['Signal'].diff() == 1).sum()
                            
                            c_r1, c_r2 = st.columns(2)
                            with c_r1:
                                with st.container(border=True):
                                    st.markdown("#### Estrategia Pasiva (Buy & Hold)")
                                    st.metric("Capital Final", f"${final_bh:,.2f} USD", f"{((final_bh-capital_usd)/capital_usd)*100:.2f}%")
                                    st.metric("Peor Caída (Riesgo)", f"{max_dd_bh:.2f}%", delta_color="inverse")
                            with c_r2:
                                with st.container(border=True):
                                    st.markdown("#### Robot Algorítmico")
                                    st.metric("Capital Final", f"${final_est:,.2f} USD", f"{((final_est-capital_usd)/capital_usd)*100:.2f}%")
                                    st.metric("Peor Caída (Riesgo)", f"{max_dd_est:.2f}%", delta_color="inverse")
                                    
                            with st.expander("💡 Conclusión Dinámica de la Simulación", expanded=True):
                                st.write(f"**1. La trampa del 'Rendimiento Total':** Es común que la estrategia pasiva (Gris) gane más dinero al final que el Robot (Verde). Esto ocurre porque en los grandes mercados alcistas ('Bull Markets'), el Robot entra tarde tras confirmar la tendencia. Además, esta simulación no resta comisiones ni impuestos por hacer {trades} operaciones reales.")
                                st.write("**2. El verdadero valor: El 'Max Drawdown' (Peor Caída):** Observa el indicador de 'Riesgo'. El objetivo principal de los fondos cuantitativos al usar cruces de medias móviles no es hacerse millonarios más rápido, sino **proteger el capital**. Cuando el mercado entra en pánico, la línea gris sufre el impacto total. El Robot detecta el cruce bajista, vende y se queda en liquidez (dólares), aplanando la caída y ahorrando angustia psicológica.")
                    except Exception as e: st.error(f"Error en simulación: {e}")
            else: st.warning("Seleccione un activo.")
            
        elif modo_backtest == "Mi Cartera Completa (Requiere cargar Excel)":
            if len(st.session_state.portfolio_tickers) > 0:
                with st.spinner(f"Descargando {anos_backtest} años de historia de su cartera entera..."):
                    try:
                        tickers = st.session_state.portfolio_tickers
                        pesos = st.session_state.portfolio_weights
                        data_hist = yf.download(tickers, period=f"{anos_backtest}y", interval="1d", progress=False)['Close']
                        if isinstance(data_hist, pd.Series): data_hist = pd.DataFrame(data_hist, columns=tickers)
                        data_hist = data_hist.dropna()
                        
                        if len(data_hist) > sma_lenta:
                            retornos = data_hist.pct_change().dropna()
                            cols_activos = [c for c in tickers if c in retornos.columns]
                            sub_pesos = np.array([pesos[tickers.index(c)] for c in cols_activos])
                            if np.sum(sub_pesos) > 0: sub_pesos = sub_pesos / np.sum(sub_pesos)
                            
                            df_bt = pd.DataFrame({'Retorno_Mercado': retornos[cols_activos].dot(sub_pesos)})
                            df_bt['Close'] = 100 * (1 + df_bt['Retorno_Mercado']).cumprod()
                            df_bt['SMA_Fast'] = df_bt['Close'].rolling(window=sma_rapida).mean()
                            df_bt['SMA_Slow'] = df_bt['Close'].rolling(window=sma_lenta).mean()
                            df_bt['Signal'] = np.where(df_bt['SMA_Fast'] > df_bt['SMA_Slow'], 1, 0)
                            df_bt['Retorno_Estrategia'] = df_bt['Retorno_Mercado'] * df_bt['Signal'].shift(1)
                            df_bt = df_bt.dropna()
                            
                            df_bt['Capital_BuyHold'] = capital_usd * (1 + df_bt['Retorno_Mercado']).cumprod()
                            df_bt['Capital_Estrategia'] = capital_usd * (1 + df_bt['Retorno_Estrategia']).cumprod()
                            
                            fig_bt = go.Figure()
                            fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['Capital_BuyHold'], mode='lines', name='Buy & Hold Patrimonial', line=dict(color='gray', width=2)))
                            fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['Capital_Estrategia'], mode='lines', name='Robot de Cartera', line=dict(color='#26A69A', width=3)))
                            fig_bt.update_layout(title="Crecimiento de Patrimonio Simulado", template="plotly_white", height=450)
                            st.plotly_chart(fig_bt, use_container_width=True)
                            
                            final_bh = df_bt['Capital_BuyHold'].iloc[-1]
                            final_est = df_bt['Capital_Estrategia'].iloc[-1]
                            max_dd_bh = ((df_bt['Capital_BuyHold'] / df_bt['Capital_BuyHold'].cummax()) - 1).min() * 100
                            max_dd_est = ((df_bt['Capital_Estrategia'] / df_bt['Capital_Estrategia'].cummax()) - 1).min() * 100
                            
                            c_r1, c_r2 = st.columns(2)
                            with c_r1:
                                with st.container(border=True):
                                    st.markdown("#### Patrimonio Estático (Buy & Hold)")
                                    st.metric("Capital Final", f"${final_bh:,.2f} USD", f"{((final_bh-capital_usd)/capital_usd)*100:.2f}%")
                                    st.metric("Peor Caída (Riesgo)", f"{max_dd_bh:.2f}%", delta_color="inverse")
                            with c_r2:
                                with st.container(border=True):
                                    st.markdown("#### Robot Patrimonial")
                                    st.metric("Capital Final", f"${final_est:,.2f} USD", f"{((final_est-capital_usd)/capital_usd)*100:.2f}%")
                                    st.metric("Peor Caída (Riesgo)", f"{max_dd_est:.2f}%", delta_color="inverse")
                            
                            with st.expander("💡 Conclusión Estratégica", expanded=True):
                                st.write("Mire el 'Max Drawdown'. El éxito del Robot sobre su cartera completa no se mide en cuánto superó al Buy&Hold, sino en cuánto logró aplanar la curva de pérdida (quedándose en liquidez) durante los mayores colapsos del mercado.")
                    except Exception as e: st.error(f"Error: {e}")
            else: st.warning("⚠️ Primero cargue su Excel en 'Mi Portfolio'.")

# --- PESTAÑA 7: RIESGO DE QUIEBRA Y ESTRÉS ---
with tab_estres:
    st.markdown("## 🚨 Pruebas de Estrés y Modelos de Quiebra")
    
    col_e1, col_e2 = st.columns([1, 1])
    with col_e1:
        st.markdown("### 📉 1. Riesgo de Quiebra Corporativa")
        if ticker_seleccionado and ticker_seleccionado != "Ninguno":
            tck_base = ticker_seleccionado.replace(".BA", "")
            if st.button("Auditar Balance Contable", type="primary"):
                with st.spinner("Extrayendo libros contables de la SEC..."):
                    try:
                        ticker_yf = yf.Ticker(tck_base)
                        bs = ticker_yf.balance_sheet
                        inc = ticker_yf.income_stmt
                        info = ticker_yf.info
                        
                        if not bs.empty and not inc.empty:
                            def get_safe(df, keys):
                                for k in keys:
                                    if k in df.index: return df.loc[k].iloc[0]
                                return 0.0

                            total_assets = get_safe(bs, ['Total Assets'])
                            total_liabilities = get_safe(bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
                            working_capital = get_safe(bs, ['Working Capital']) 
                            if working_capital == 0:
                                current_assets = get_safe(bs, ['Current Assets', 'Total Current Assets'])
                                current_liabilities = get_safe(bs, ['Current Liabilities', 'Total Current Liabilities'])
                                working_capital = current_assets - current_liabilities
                                
                            retained_earnings = get_safe(bs, ['Retained Earnings'])
                            ebit = get_safe(inc, ['EBIT', 'Operating Income', 'Pretax Income'])
                            sales = get_safe(inc, ['Total Revenue', 'Operating Revenue'])
                            market_cap = info.get('marketCap', 0.0)
                            
                            if total_assets > 0 and total_liabilities > 0:
                                A = working_capital / total_assets
                                B = retained_earnings / total_assets
                                C = ebit / total_assets
                                D = market_cap / total_liabilities
                                E = sales / total_assets
                                Z_score = (1.2 * A) + (1.4 * B) + (3.3 * C) + (0.6 * D) + (1.0 * E)
                                
                                with st.container(border=True):
                                    if Z_score >= 2.99:
                                        st.markdown("<h2 style='color: #2E7D32; text-align:center;'>🟢 ZONA SEGURA</h2>", unsafe_allow_html=True)
                                        st.markdown(f"<h1 style='text-align:center;'>Z-Score: {Z_score:.2f}</h1>", unsafe_allow_html=True)
                                        st.write("La empresa tiene una estructura financiera sumamente sólida. Las probabilidades de quiebra en los próximos 2 años son casi nulas.")
                                    elif 1.81 <= Z_score < 2.99:
                                        st.markdown("<h2 style='color: #F9A825; text-align:center;'>🟡 ZONA GRIS</h2>", unsafe_allow_html=True)
                                        st.markdown(f"<h1 style='text-align:center;'>Z-Score: {Z_score:.2f}</h1>", unsafe_allow_html=True)
                                        st.write("Situación financiera dudosa. No está en riesgo inminente, pero presenta debilidades que requieren monitoreo.")
                                    else:
                                        st.markdown("<h2 style='color: #C62828; text-align:center;'>🔴 ZONA DE PELIGRO</h2>", unsafe_allow_html=True)
                                        st.markdown(f"<h1 style='text-align:center;'>Z-Score: {Z_score:.2f}</h1>", unsafe_allow_html=True)
                                        st.write("ALERTA MÁXIMA. Muestra estrés severo. Existe una altísima probabilidad matemática de bancarrota inminente.")
                            else: st.warning("Datos incompletos para calcular el modelo.")
                        else: st.warning("No hay libros contables disponibles.")
                    except Exception as e: st.error(f"Error al calcular: {e}")
        else: st.info("Seleccione un activo en el menú lateral.")

    with col_e2:
        st.markdown("### 💥 2. Stress Testing de Cartera")
        if st.session_state.portfolio_history is not None:
            with st.spinner("Preparando simulador..."):
                try:
                    tickers = st.session_state.portfolio_tickers
                    pesos = st.session_state.portfolio_weights
                    data_s = yf.download(tickers + ['SPY.BA'], period="1y", interval="1d", progress=False)['Close']
                    if isinstance(data_s, pd.Series): data_s = pd.DataFrame(data_s, columns=tickers + ['SPY.BA'])
                    retornos_s = data_s.pct_change().dropna()
                    
                    port_ret_s = retornos_s[[c for c in tickers if c in retornos_s.columns]].dot(pesos)
                    if 'SPY.BA' in retornos_s.columns:
                        cov_m = np.cov(port_ret_s, retornos_s['SPY.BA'])
                        beta = cov_m[0, 1] / cov_m[1, 1] if cov_m[1, 1] != 0 else 1.0
                    else: beta = 1.0
                    
                    st.success(f"**Beta de Cartera Identificado:** {beta:.2f}")
                    capital = st.session_state.portfolio_total_usd
                    
                    escenarios = {
                        "Crisis Subprime 2008 (Lehman Brothers)": -57.0,
                        "Estallido Dot-Com 2000": -49.0,
                        "Crash del COVID-19 (Marzo 2020)": -34.0,
                        "Lunes Negro 1987": -22.6
                    }
                    
                    escenario_elegido = st.selectbox("Seleccione el escenario a simular:", list(escenarios.keys()))
                    caida_sp500 = escenarios[escenario_elegido]
                    caida_cartera = caida_sp500 * beta
                    dinero_perdido = capital * (caida_cartera / 100)
                    capital_restante = capital + dinero_perdido 
                    
                    with st.container(border=True):
                        st.markdown(f"#### Impacto de la {escenario_elegido}")
                        st.markdown(f"<h1 style='color:#EF5350; text-align:center;'>{caida_cartera:.1f}%</h1>", unsafe_allow_html=True)
                        s_c1, s_c2 = st.columns(2)
                        s_c1.metric("Pérdida en Dólares", f"${dinero_perdido:,.2f} USD")
                        s_c2.metric("Su Patrimonio Quedaría En", f"${max(0, capital_restante):,.2f} USD")
                except Exception as e: st.error(f"Error: {e}")
        else: st.warning("⚠️ Primero cargue su Excel en la Pestaña 'Mi Portfolio'.")