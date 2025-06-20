import streamlit as st
import gspread
import pandas as pd
import json
import os
import tempfile
from io import BytesIO
import requests
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="🔍 Buscador RRV Avanzado",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .search-box {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #2a5298;
        margin-bottom: 1rem;
    }
    .result-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .status-activo {
        background: #d4edda;
        color: #155724;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .status-inactivo {
        background: #f8d7da;
        color: #721c24;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .status-no-verificado {
        background: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .pegasus-section {
        background: #e8f4f8;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #17a2b8;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

class PegasusAPI:
    """Clase para manejar la API de Pegasus"""
    
    def __init__(self):
        self.base_url = "https://plataforma.rrvsac.com/api"
        self.token = None
        self.username = None
        self.password = None
    
    def set_credentials(self, username, password):
        """Configurar credenciales"""
        self.username = username
        self.password = password
    
    def authenticate(self):
        """Autenticar con la API de Pegasus"""
        try:
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.base_url}/login",
                json=login_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Intentar diferentes nombres de token
                self.token = data.get('token') or data.get('access_token') or data.get('bearer_token')
                return True, "Autenticación exitosa"
            else:
                return False, f"Error de autenticación: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {str(e)}"
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"
    
    def search_vehicle(self, license_plate):
        """Buscar vehículo en la plataforma Pegasus"""
        if not self.token:
            auth_success, auth_message = self.authenticate()
            if not auth_success:
                return None, auth_message
        
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/vehicles?",
                headers=headers,
                params={"search.info.license_plate=": license_plate},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data, "Búsqueda exitosa"
            elif response.status_code == 401:
                # Token expirado, intentar reautenticar
                auth_success, auth_message = self.authenticate()
                if auth_success:
                    return self.search_vehicle(license_plate)  # Reintentar
                else:
                    return None, "Token expirado y no se pudo reautenticar"
            else:
                return None, f"Error en búsqueda: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return None, f"Error de conexión: {str(e)}"
        except Exception as e:
            return None, f"Error inesperado: {str(e)}"

def configurar_credenciales_gspread():
    """Configurar credenciales de Google Sheets"""
    try:
        # Primero intentar con secrets de Streamlit Cloud
        if 'gcp_service_account' in st.secrets:
            credentials = st.secrets['gcp_service_account']
            # Crear archivo temporal con las credenciales
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(dict(credentials), f)
                return f.name
        else:
            # Buscar archivo JSON local
            json_files = [f for f in os.listdir('.') if f.endswith('.json')]
            if json_files:
                return json_files[0]
            else:
                st.error("❌ No se encontraron credenciales de Google Sheets")
                return None
    except Exception as e:
        st.error(f"❌ Error configurando credenciales: {e}")
        return None

def conectar_gspread():
    """Conectar con Google Sheets"""
    try:
        credentials_path = configurar_credenciales_gspread()
        if credentials_path:
            gc = gspread.service_account(filename=credentials_path)
            return gc
        return None
    except Exception as e:
        st.error(f"❌ Error conectando con Google Sheets: {e}")
        return None

def buscar_en_hojas_rrv(gc, termino_busqueda):
    """Buscar en las hojas RRV"""
    resultados = []
    hojas_rrv = [
        "RRV"
    ]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, nombre_hoja in enumerate(hojas_rrv):
        try:
            status_text.text(f"🔍 Buscando en {nombre_hoja}...")
            hoja = gc.open(nombre_hoja)
            
            for worksheet in hoja.worksheets():
                try:
                    datos = worksheet.get_all_records()
                    df = pd.DataFrame(datos)
                    
                    if not df.empty and 'PLACA' in df.columns:
                        # Búsqueda flexible
                        mask = df['PLACA'].astype(str).str.contains(
                            termino_busqueda, case=False, na=False
                        )
                        coincidencias = df[mask]
                        
                        for _, fila in coincidencias.iterrows():
                            resultado = {
                                'hoja': nombre_hoja,
                                'pestana': worksheet.title,
                                'data': fila.to_dict()
                            }
                            resultados.append(resultado)
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            continue
        
        progress_bar.progress((i + 1) / len(hojas_rrv))
    
    progress_bar.empty()
    status_text.empty()
    
    return resultados

def mostrar_resultado_con_pegasus(resultado, pegasus_data=None, pegasus_status=None):
    """Mostrar resultado enriquecido con datos de Pegasus"""
    
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**📋 {resultado['hoja']} - {resultado['pestana']}**")
        
        with col2:
            if pegasus_status is not None:
                if pegasus_status:
                    st.markdown('<span class="status-activo">✅ ACTIVO EN PLATAFORMA</span>', 
                              unsafe_allow_html=True)
                else:
                    st.markdown('<span class="status-inactivo">❌ NO ENCONTRADO EN PLATAFORMA</span>', 
                              unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-no-verificado">⚠️ NO VERIFICADO</span>', 
                          unsafe_allow_html=True)
        
        # Datos principales
        data = resultado['data']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**🚗 PLACA:** {data.get('PLACA', 'N/A')}")
            st.write(f"**👤 PROPIETARIO:** {data.get('PROPIETARIO', 'N/A')}")
        
        with col2:
            st.write(f"**📍 DISTRITO:** {data.get('DISTRITO', 'N/A')}")
            st.write(f"**📞 TELÉFONO:** {data.get('TELÉFONO', 'N/A')}")
        
        with col3:
            st.write(f"**🏢 EMPRESA:** {data.get('EMPRESA', 'N/A')}")
            st.write(f"**📅 FECHA:** {data.get('FECHA', 'N/A')}")
        
        # Información de Pegasus si está disponible
        if pegasus_data and pegasus_status:
            with st.expander("🔍 Información adicional de Plataforma Pegasus"):
                st.json(pegasus_data)
        
        st.markdown("---")

def exportar_a_excel_avanzado(resultados, pegasus_results=None):
    """Exportar resultados a Excel con información de Pegasus"""
    try:
        # Preparar datos para export
        datos_export = []
        
        for i, resultado in enumerate(resultados):
            fila = resultado['data'].copy()
            fila['FUENTE_HOJA'] = resultado['hoja']
            fila['FUENTE_PESTANA'] = resultado['pestana']
            
            # Agregar información de Pegasus si está disponible
            if pegasus_results and i < len(pegasus_results):
                pegasus_info = pegasus_results[i]
                fila['PEGASUS_STATUS'] = "ACTIVO" if pegasus_info['found'] else "NO ENCONTRADO"
                fila['PEGASUS_VERIFICADO'] = "SÍ"
                if pegasus_info['found'] and pegasus_info['data']:
                    fila['PEGASUS_INFO'] = str(pegasus_info['data'])
            else:
                fila['PEGASUS_STATUS'] = "NO VERIFICADO"
                fila['PEGASUS_VERIFICADO'] = "NO"
            
            datos_export.append(fila)
        
        df_export = pd.DataFrame(datos_export)
        
        # Crear archivo Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name='Resultados_RRV_Avanzado', index=False)
        
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"❌ Error exportando: {e}")
        return None

def main():
    # Header principal
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Buscador RRV Avanzado</h1>
        <p>Búsqueda integrada en Google Sheets + Plataforma Pegasus</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Configuración de Pegasus
        st.subheader("🔐 Credenciales Pegasus")
        use_pegasus = st.checkbox("Usar integración con Pegasus", value=False)
        
        pegasus_api = None
        if use_pegasus:
            username = st.text_input("Usuario Pegasus", placeholder="tu_usuario")
            password = st.text_input("Contraseña Pegasus", type="password", placeholder="tu_contraseña")
            
            if username and password:
                pegasus_api = PegasusAPI()
                pegasus_api.set_credentials(username, password)
                
                # Probar conexión
                if st.button("🔍 Probar conexión Pegasus"):
                    with st.spinner("Probando conexión..."):
                        success, message = pegasus_api.authenticate()
                        if success:
                            st.success("✅ Conexión exitosa")
                        else:
                            st.error(f"❌ {message}")
            else:
                st.info("Ingresa usuario y contraseña para habilitar Pegasus")
        
        st.markdown("---")
        
        # Información
        st.subheader("ℹ️ Información")
        st.info("**Búsqueda en:**\n- 10 Hojas RRV en Google Sheets\n- Plataforma Pegasus (opcional)")
        
        if use_pegasus and pegasus_api:
            st.success("🚀 Modo avanzado activado")
        else:
            st.warning("📊 Solo Google Sheets")
    
    # Área principal de búsqueda
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        termino_busqueda = st.text_input(
            "🔍 **Ingresa la placa a buscar:**",
            placeholder="Ej: ABC-123, ABC123, ABC",
            help="Puedes buscar placas completas o parciales"
        )
    
    with col2:
        st.write("")  # Espacio
        buscar = st.button("🚀 BUSCAR", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Búsqueda y resultados
    if buscar and termino_busqueda:
        # Conectar con Google Sheets
        gc = conectar_gspread()
        
        if gc:
            # Buscar en Google Sheets
            st.subheader("📊 Resultados de Google Sheets")
            resultados = buscar_en_hojas_rrv(gc, termino_busqueda)
            
            if resultados:
                st.success(f"✅ Se encontraron {len(resultados)} coincidencias")
                
                # Buscar en Pegasus si está habilitado
                pegasus_results = []
                if use_pegasus and pegasus_api and pegasus_api.username:
                    st.subheader("🔍 Verificación en Plataforma Pegasus")
                    
                    for resultado in resultados:
                        placa = resultado['data'].get('PLACA', '')
                        if placa:
                            with st.spinner(f"Consultando {placa} en Pegasus..."):
                                pegasus_data, pegasus_message = pegasus_api.search_vehicle(placa)
                                pegasus_found = pegasus_data is not None
                                pegasus_results.append({
                                    'found': pegasus_found,
                                    'data': pegasus_data,
                                    'message': pegasus_message
                                })
                        else:
                            pegasus_results.append({
                                'found': False,
                                'data': None,
                                'message': 'Placa no disponible'
                            })
                
                # Mostrar resultados
                st.subheader("📋 Resultados Detallados")
                
                for i, resultado in enumerate(resultados):
                    pegasus_info = pegasus_results[i] if pegasus_results else None
                    pegasus_status = pegasus_info['found'] if pegasus_info else None
                    pegasus_data = pegasus_info['data'] if pegasus_info and pegasus_info['found'] else None
                    
                    mostrar_resultado_con_pegasus(resultado, pegasus_data, pegasus_status)
                
                # Botón de exportación
                st.subheader("📥 Exportar Resultados")
                
                excel_data = exportar_a_excel_avanzado(resultados, pegasus_results if pegasus_results else None)
                
                if excel_data:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"busqueda_rrv_avanzado_{termino_busqueda}_{timestamp}.xlsx"
                    
                    st.download_button(
                        label="📥 Descargar Excel Completo",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    st.info("💡 El archivo Excel incluye toda la información encontrada + verificación Pegasus")
                    
            else:
                st.warning(f"⚠️ No se encontraron resultados para: **{termino_busqueda}**")
                st.info("💡 Intenta con:")
                st.write("- Solo números: `123`")
                st.write("- Solo letras: `ABC`") 
                st.write("- Combinación: `ABC123`")
        
        else:
            st.error("❌ No se pudo conectar con Google Sheets")
            st.info("🔧 Verifica que las credenciales estén configuradas correctamente")
    
    elif buscar and not termino_busqueda:
        st.warning("⚠️ Por favor ingresa una placa para buscar")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        🔍 <strong>Buscador RRV Avanzado</strong> | 
        📊 Google Sheets + 🚀 Plataforma Pegasus | 
        Desarrollado con ❤️ usando Streamlit
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 
