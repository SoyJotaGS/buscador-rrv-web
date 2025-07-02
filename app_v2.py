import streamlit as st
import gspread
import os
from datetime import datetime
import glob
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import pandas as pd
import io
import json
import tempfile

class BuscadorPlacasWeb:
    def __init__(self):
        self.gc = None
        self.credenciales_path = None
        if 'resultados_actuales' not in st.session_state:
            st.session_state.resultados_actuales = []
        self.detectar_credenciales()
    
    def detectar_credenciales(self):
        """Detecta credenciales desde secrets o archivo local"""
        # Primero intentar desde Streamlit secrets (para producción en Streamlit Cloud)
        try:
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                # Crear archivo temporal con las credenciales
                credentials = dict(st.secrets['gcp_service_account'])
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(credentials, f)
                    self.credenciales_path = f.name
                return
        except Exception:
            pass
        
        # Fallback a archivo local (para desarrollo)
        archivos_json = glob.glob("*.json")
        if archivos_json:
            self.credenciales_path = archivos_json[0]
    
    def conectar_google_sheets(self):
        """Conecta con Google Sheets"""
        try:
            if not self.credenciales_path or not os.path.exists(self.credenciales_path):
                raise FileNotFoundError("Archivo de conexión no encontrado")
            
            self.gc = gspread.service_account(filename=self.credenciales_path)
            return True
        except Exception as e:
            st.error(f"Error de conexión: {str(e)}")
            return False
    
    def buscar_placas_en_drive(self, placa_buscar):
        """Busca una placa en todas las hojas RRV"""
        if not self.gc:
            if not self.conectar_google_sheets():
                return []
        
        try:
            with st.spinner('Buscando en Google Sheets...'):
                todas_las_hojas = self.gc.openall()
                hojas_rrv = [hoja for hoja in todas_las_hojas if "RRV" in hoja.title]
                
                if not hojas_rrv:
                    st.warning("No se encontraron hojas con 'RRV' en el nombre")
                    return []
                
                resultados = []
                progress_bar = st.progress(0)
                
                for idx, hoja in enumerate(hojas_rrv):
                    try:
                        worksheets = hoja.worksheets()
                        
                        for worksheet in worksheets:
                            try:
                                data = worksheet.get_all_values()
                                if not data or len(data) < 2:
                                    continue
                                
                                encabezados = data[0]
                                filas_datos = data[1:]
                                
                                filas_encontradas = self.buscar_placa_en_hoja(
                                    filas_datos, encabezados, placa_buscar, hoja.title, worksheet.title
                                )
                                
                                if filas_encontradas:
                                    resultados.extend(filas_encontradas)
                                    
                            except Exception as e:
                                continue
                                
                    except Exception as e:
                        continue
                    
                    progress_bar.progress((idx + 1) / len(hojas_rrv))
                
                progress_bar.empty()
                return resultados
                
        except Exception as e:
            st.error(f"Error durante la búsqueda: {str(e)}")
            return []
    
    def buscar_placa_en_hoja(self, filas_datos, encabezados, placa_buscar, nombre_spreadsheet, nombre_worksheet):
        """Busca una placa en una hoja específica"""
        resultados = []
        
        # Buscar columnas de placa
        columnas_placa = []
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if any(palabra in encabezado_lower for palabra in ['placa', 'patente', 'matricula', 'vehiculo', 'numero de vehiculo']):
                columnas_placa.append(i)
        
        if not columnas_placa:
            columnas_placa = list(range(min(3, len(encabezados))))
        
        # Buscar la placa
        for num_fila, fila in enumerate(filas_datos, start=2):
            for col_placa in columnas_placa:
                if col_placa < len(fila):
                    valor_celda = str(fila[col_placa]).strip()
                    if placa_buscar.upper() in valor_celda.upper():
                        # Encontrar columnas específicas
                        fecha_col = self.encontrar_columna_fecha(encabezados)
                        proyecto_col = self.encontrar_columna_proyecto(encabezados)
                        empresa_col = self.encontrar_columna_empresa(encabezados)
                        sistema_col = self.encontrar_columna_sistema(encabezados)
                        trabajo_col = self.encontrar_columna_trabajo(encabezados)
                        
                        resultado = {
                            'hoja': nombre_spreadsheet,
                            'pestana': nombre_worksheet,
                            'fila': num_fila,
                            'placa': valor_celda,
                            'fecha': fila[fecha_col] if fecha_col < len(fila) else "No disponible",
                            'proyecto': fila[proyecto_col] if proyecto_col < len(fila) else "No disponible",
                            'empresa': fila[empresa_col] if empresa_col < len(fila) else "No disponible",
                            'sistema': fila[sistema_col] if sistema_col < len(fila) else "No disponible",
                            'trabajo': fila[trabajo_col] if trabajo_col < len(fila) else "No disponible",
                            'datos_completos': fila,
                            'encabezados': encabezados
                        }
                        resultados.append(resultado)
                        break
        
        return resultados
    
    def encontrar_columna_fecha(self, encabezados):
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if any(palabra in encabezado_lower for palabra in ['fecha', 'date', 'dia', 'hora', 'fecha de ingreso']):
                return i
        return 1 if len(encabezados) > 1 else 0
    
    def encontrar_columna_proyecto(self, encabezados):
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if 'proyecto' in encabezado_lower:
                return i
        return 2 if len(encabezados) > 2 else 0
    
    def encontrar_columna_empresa(self, encabezados):
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if any(palabra in encabezado_lower for palabra in ['empresa', 'nombre', 'cliente']):
                return i
        return 3 if len(encabezados) > 3 else 0
    
    def encontrar_columna_sistema(self, encabezados):
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if 'sistema' in encabezado_lower:
                return i
        return 4 if len(encabezados) > 4 else 0
    
    def encontrar_columna_trabajo(self, encabezados):
        for i, encabezado in enumerate(encabezados):
            encabezado_lower = str(encabezado).lower()
            if any(palabra in encabezado_lower for palabra in ['tipo de trabajo', 'estado', 'status', 'situacion', 'condicion']):
                return i
        return 5 if len(encabezados) > 5 else 0
    
    def ordenar_resultados_cronologicamente(self, resultados):
        """Ordena los resultados por fecha de manera cronológica"""
        def parsear_fecha(fecha_str):
            """Intenta parsear diferentes formatos de fecha"""
            if not fecha_str or fecha_str == "No disponible":
                return datetime.min
            
            fecha_str = str(fecha_str).strip()
            
            # Limpiar la fecha de caracteres extra
            fecha_str = fecha_str.replace('  ', ' ').strip()
            
            # Formatos comunes de fecha (ordenados de más específico a más general)
            formatos = [
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%d/%m/%Y',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%d-%m-%Y %H:%M:%S',
                '%d-%m-%Y %H:%M',
                '%d-%m-%Y',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y %H:%M',
                '%m/%d/%Y',
                '%d/%m/%y %H:%M:%S',
                '%d/%m/%y %H:%M',
                '%d/%m/%y',
                '%d.%m.%Y %H:%M:%S',
                '%d.%m.%Y %H:%M',
                '%d.%m.%Y'
            ]
            
            for formato in formatos:
                try:
                    return datetime.strptime(fecha_str, formato)
                except ValueError:
                    continue
            
            # Si no se puede parsear, intentar con dateutil
            try:
                from dateutil import parser
                return parser.parse(fecha_str)
            except:
                pass
            
            # Si no se puede parsear, devolver fecha mínima
            return datetime.min
        
        # Ordenar por fecha (más reciente primero)
        resultados_ordenados = sorted(
            resultados, 
            key=lambda x: parsear_fecha(x['fecha']), 
            reverse=True
        )
        
        return resultados_ordenados
    
    def calcular_estadisticas_cronologicas(self, resultados):
        """Calcula estadísticas cronológicas de los resultados"""
        if not resultados or len(resultados) < 2:
            return None
        
        try:
            from dateutil import parser
            
            # Parsear fechas
            fechas_parseadas = []
            for resultado in resultados:
                if resultado['fecha'] != "No disponible":
                    try:
                        fecha = parser.parse(resultado['fecha'])
                        fechas_parseadas.append(fecha)
                    except:
                        continue
            
            if len(fechas_parseadas) < 2:
                return None
            
            # Calcular estadísticas
            fechas_parseadas.sort(reverse=True)  # Más reciente primero
            
            # Rango total
            rango_total = fechas_parseadas[0] - fechas_parseadas[-1]
            
            # Intervalos entre registros
            intervalos = []
            for i in range(len(fechas_parseadas) - 1):
                intervalo = fechas_parseadas[i] - fechas_parseadas[i + 1]
                intervalos.append(intervalo)
            
            # Estadísticas
            stats = {
                'total_dias': rango_total.days,
                'total_horas': rango_total.total_seconds() / 3600,
                'promedio_intervalo_dias': sum([i.days for i in intervalos]) / len(intervalos) if intervalos else 0,
                'promedio_intervalo_horas': sum([i.total_seconds() for i in intervalos]) / (len(intervalos) * 3600) if intervalos else 0,
                'registro_mas_reciente': fechas_parseadas[0],
                'registro_mas_antiguo': fechas_parseadas[-1],
                'total_registros_con_fecha': len(fechas_parseadas)
            }
            
            return stats
            
        except Exception as e:
            return None
    
    def crear_excel_bytes(self, resultado):
        """Crea un archivo Excel en memoria y devuelve los bytes"""
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = f"Placa {resultado['placa']}"
            
            # Estilos
            titulo_font = Font(name='Arial', size=14, bold=True, color='FFFFFF')
            subtitulo_font = Font(name='Arial', size=12, bold=True)
            normal_font = Font(name='Arial', size=10)
            
            titulo_fill = PatternFill(start_color='2196F3', end_color='2196F3', fill_type='solid')
            subtitulo_fill = PatternFill(start_color='E3F2FD', end_color='E3F2FD', fill_type='solid')
            
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Título principal
            ws['A1'] = f"INFORMACIÓN DE LA PLACA: {resultado['placa']}"
            ws['A1'].font = titulo_font
            ws['A1'].fill = titulo_fill
            ws.merge_cells('A1:C1')
            ws['A1'].alignment = Alignment(horizontal='center')
            
            # Información de ubicación
            ws['A3'] = "UBICACIÓN DEL REGISTRO"
            ws['A3'].font = subtitulo_font
            ws['A3'].fill = subtitulo_fill
            ws['A3'].border = border
            
            ws['A4'] = "Hoja:"
            ws['B4'] = resultado['hoja']
            ws['A5'] = "Pestaña:"
            ws['B5'] = resultado['pestana']
            ws['A6'] = "Fila:"
            ws['B6'] = resultado['fila']
            
            # Aplicar estilos a la información de ubicación
            for row in range(4, 7):
                ws[f'A{row}'].font = normal_font
                ws[f'A{row}'].border = border
                ws[f'B{row}'].font = normal_font
                ws[f'B{row}'].border = border
            
            # Datos completos de la fila
            ws['A8'] = "DATOS COMPLETOS DE LA FILA"
            ws['A8'].font = subtitulo_font
            ws['A8'].fill = subtitulo_fill
            ws['A8'].border = border
            ws.merge_cells('A8:C8')
            
            # Encabezados de la tabla de datos
            ws['A9'] = "Campo"
            ws['B9'] = "Valor"
            ws['A9'].font = subtitulo_font
            ws['B9'].font = subtitulo_font
            ws['A9'].fill = subtitulo_fill
            ws['B9'].fill = subtitulo_fill
            ws['A9'].border = border
            ws['B9'].border = border
            
            # Insertar todos los datos de la fila
            row_num = 10
            for encabezado, valor in zip(resultado['encabezados'], resultado['datos_completos']):
                ws[f'A{row_num}'] = encabezado
                ws[f'B{row_num}'] = valor
                ws[f'A{row_num}'].font = normal_font
                ws[f'B{row_num}'].font = normal_font
                ws[f'A{row_num}'].border = border
                ws[f'B{row_num}'].border = border
                row_num += 1
            
            # Información del archivo
            ws[f'A{row_num + 1}'] = f"Archivo generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            ws[f'A{row_num + 1}'].font = Font(name='Arial', size=9, italic=True)
            
            # Ajustar ancho de columnas
            ws.column_dimensions['A'].width = 25
            ws.column_dimensions['B'].width = 40
            ws.column_dimensions['C'].width = 15
            
            # Guardar en memoria
            output = io.BytesIO()
            wb.save(output)
            wb.close()
            
            return output.getvalue()
            
        except Exception as e:
            st.error(f"Error al crear archivo Excel: {str(e)}")
            return None

def main():
    # Configuración de la página
    st.set_page_config(
        page_title="BUSCADOR RRV",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS personalizado para mejorar el diseño
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #2196F3 0%, #1976D2 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    .search-container {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    .results-container {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header principal
    st.markdown("""
    <div class="main-header">
        <h1>🔍 BUSCADOR RRV</h1>
        <p>Sistema de búsqueda de placas en Google Sheets</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Inicializar la aplicación
    app = BuscadorPlacasWeb()
    
    # Verificar credenciales
    if not app.credenciales_path:
        st.error("❌ No se encontraron credenciales. Contacta al administrador para configurar el acceso.")
        st.info("💡 Para desarrolladores: Configura las credenciales en Streamlit Cloud Secrets o agrega un archivo JSON local.")
        return
    
    st.success("✅ Sistema conectado y listo para buscar.")
    
    # Container de búsqueda
    with st.container():
        st.markdown('<div class="search-container">', unsafe_allow_html=True)
        
        st.subheader("📋 Buscar Placa")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            placa_buscar = st.text_input(
                "Ingresa la placa a buscar:",
                placeholder="Ej: ABC-123",
                key="placa_input"
            )
        
        with col2:
            st.write("")  # Espaciado
            buscar_btn = st.button("🔍 Buscar", type="primary", use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Ejecutar búsqueda
    if buscar_btn and placa_buscar.strip():
        resultados = app.buscar_placas_en_drive(placa_buscar.strip())
        # Ordenar resultados cronológicamente (más reciente primero)
        resultados_ordenados = app.ordenar_resultados_cronologicamente(resultados)
        st.session_state.resultados_actuales = resultados_ordenados
        
        if not resultados_ordenados:
            st.warning("⚠️ No se encontró esta placa en el sistema")
        else:
            st.success(f"✅ Se encontraron {len(resultados_ordenados)} registro(s) ordenados cronológicamente")
    
    # Mostrar resultados si existen
    if st.session_state.resultados_actuales:
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        # Header de resultados
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Resultados Encontrados (Ordenados Cronológicamente)")
        
        with col2:
            st.metric("Total Registros", len(st.session_state.resultados_actuales))
        
        # Resumen cronológico
        if len(st.session_state.resultados_actuales) > 1:
            primer_registro = st.session_state.resultados_actuales[0]
            ultimo_registro = st.session_state.resultados_actuales[-1]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📅 Registro Más Reciente", primer_registro['fecha'])
            with col2:
                st.metric("📅 Registro Más Antiguo", ultimo_registro['fecha'])
            with col3:
                # Calcular diferencia de tiempo si es posible
                try:
                    fecha_reciente = datetime.strptime(primer_registro['fecha'], '%d/%m/%Y %H:%M:%S')
                    fecha_antigua = datetime.strptime(ultimo_registro['fecha'], '%d/%m/%Y %H:%M:%S')
                    diferencia = fecha_reciente - fecha_antigua
                    st.metric("⏱️ Rango Temporal", f"{diferencia.days} días")
                except:
                    st.metric("⏱️ Rango Temporal", "No calculable")
        
        # Crear DataFrame para mostrar los resultados
        df_resultados = pd.DataFrame([
            {
                'FECHA': resultado['fecha'],
                'PLACA': resultado['placa'],
                'EMPRESA': resultado['empresa'],
                'ÚLTIMO ESTADO': resultado['trabajo'],
                'SERVICIO': resultado['pestana'],
                'HOJA': resultado['hoja']
            }
            for resultado in st.session_state.resultados_actuales
        ])
        
        # Mostrar tabla
        st.dataframe(
            df_resultados,
            use_container_width=True,
            hide_index=True
        )
        
        # Panel de estadísticas cronológicas
        stats = app.calcular_estadisticas_cronologicas(st.session_state.resultados_actuales)
        if stats:
            st.subheader("📊 Estadísticas Cronológicas")
            
            # Crear métricas con diseño mejorado
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "📅 Rango Total", 
                    f"{stats['total_dias']} días",
                    help="Diferencia entre el registro más reciente y más antiguo"
                )
            
            with col2:
                st.metric(
                    "⏱️ Promedio Intervalo", 
                    f"{stats['promedio_intervalo_dias']:.1f} días",
                    help="Tiempo promedio entre registros consecutivos"
                )
            
            with col3:
                st.metric(
                    "🕒 Total Horas", 
                    f"{stats['total_horas']:.1f} horas",
                    help="Rango total en horas"
                )
            
            with col4:
                st.metric(
                    "📋 Registros con Fecha", 
                    f"{stats['total_registros_con_fecha']}/{len(st.session_state.resultados_actuales)}",
                    help="Registros que tienen fecha válida"
                )
            
            # Información adicional
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**📅 Registro más reciente:** {stats['registro_mas_reciente'].strftime('%d/%m/%Y %H:%M:%S')}")
            with col2:
                st.info(f"**📅 Registro más antiguo:** {stats['registro_mas_antiguo'].strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Línea de tiempo cronológica mejorada
        st.subheader("📅 Línea de Tiempo Cronológica")
        
        # Filtros de visualización
        col1, col2 = st.columns([2, 1])
        with col1:
            mostrar_detalles = st.checkbox("Mostrar detalles completos", value=True, help="Muestra información adicional como empresa, estado y servicio")
        with col2:
            mostrar_tiempo = st.checkbox("Mostrar intervalos de tiempo", value=True, help="Muestra el tiempo transcurrido entre registros")
        
        # CSS personalizado para la línea de tiempo
        timeline_css = """
        <style>
        .timeline-container {
            position: relative;
            margin: 30px 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .timeline-header {
            text-align: center;
            color: white;
            margin-bottom: 25px;
            font-size: 1.2em;
            font-weight: bold;
        }
        .timeline-item {
            position: relative;
            margin: 20px 0;
            padding: 15px 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border-left: 5px solid #2196F3;
            transition: all 0.3s ease;
        }
        .timeline-item:hover {
            transform: translateX(5px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }
        .timeline-item.recent {
            border-left-color: #4CAF50;
            background: linear-gradient(135deg, #f8fff9 0%, #e8f5e8 100%);
        }
        .timeline-item.old {
            border-left-color: #FF9800;
            background: linear-gradient(135deg, #fffbf8 0%, #fff3e0 100%);
        }
        .timeline-icon {
            position: absolute;
            left: -12px;
            top: 50%;
            transform: translateY(-50%);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            color: white;
            font-weight: bold;
        }
        .timeline-icon.recent {
            background: #4CAF50;
        }
        .timeline-icon.old {
            background: #FF9800;
        }
        .timeline-icon.middle {
            background: #2196F3;
        }
        .timeline-content {
            margin-left: 20px;
        }
        .timeline-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
            font-size: 1.1em;
        }
        .timeline-date {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 8px;
        }
        .timeline-details {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 8px;
        }
        .timeline-badge {
            background: #e3f2fd;
            color: #1976d2;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
        }
        .timeline-badge.empresa {
            background: #f3e5f5;
            color: #7b1fa2;
        }
        .timeline-badge.estado {
            background: #e8f5e8;
            color: #388e3c;
        }
        .timeline-badge.servicio {
            background: #fff3e0;
            color: #f57c00;
        }
        .timeline-connector {
            position: absolute;
            left: 0;
            top: 100%;
            width: 2px;
            height: 20px;
            background: #2196F3;
        }
        .timeline-connector:last-child {
            display: none;
        }
        </style>
        """
        
        # Crear línea de tiempo mejorada
        timeline_html = timeline_css + """
        <div class="timeline-container">
            <div class="timeline-header">
                🕒 Línea de Tiempo Cronológica - {total_registros} Registros Encontrados
            </div>
        """.format(total_registros=len(st.session_state.resultados_actuales))
        
        for i, resultado in enumerate(st.session_state.resultados_actuales):
            fecha_formateada = resultado['fecha'] if resultado['fecha'] != "No disponible" else "Fecha no disponible"
            
            # Determinar el tipo de registro y estilos
            if i == 0:
                item_class = "recent"
                icon_class = "recent"
                icon_text = "🟢"
                badge_text = "MÁS RECIENTE"
            elif i == len(st.session_state.resultados_actuales) - 1:
                item_class = "old"
                icon_class = "old"
                icon_text = "🟠"
                badge_text = "MÁS ANTIGUO"
            else:
                item_class = ""
                icon_class = "middle"
                icon_text = "🔵"
                badge_text = f"REGISTRO #{i+1}"
            
            # Calcular tiempo transcurrido si es posible
            tiempo_info = ""
            if mostrar_tiempo and i > 0 and resultado['fecha'] != "No disponible":
                try:
                    from dateutil import parser
                    fecha_actual = parser.parse(resultado['fecha'])
                    fecha_anterior = parser.parse(st.session_state.resultados_actuales[i-1]['fecha'])
                    diferencia = fecha_anterior - fecha_actual
                    if diferencia.days > 0:
                        tiempo_info = f"<br><small style='color: #999;'>⏱️ {diferencia.days} días después</small>"
                    elif diferencia.seconds > 0:
                        horas = diferencia.seconds // 3600
                        tiempo_info = f"<br><small style='color: #999;'>⏱️ {horas} horas después</small>"
                except:
                    pass
            
            # Generar detalles según el filtro
            detalles_html = ""
            if mostrar_detalles:
                detalles_html = f"""
                    <div class="timeline-details">
                        <span class="timeline-badge">🚗 {resultado['placa']}</span>
                        <span class="timeline-badge empresa">🏢 {resultado['empresa']}</span>
                        <span class="timeline-badge estado">📋 {resultado['trabajo']}</span>
                        <span class="timeline-badge servicio">🔧 {resultado['pestana']}</span>
                    </div>
                """
            
            timeline_html += f"""
            <div class="timeline-item {item_class}">
                <div class="timeline-icon {icon_class}">{icon_text}</div>
                <div class="timeline-content">
                    <div class="timeline-title">{badge_text}</div>
                    <div class="timeline-date">📅 {fecha_formateada}{tiempo_info}</div>
                    {detalles_html}
                </div>
            </div>
            """
            
            # Agregar conector si no es el último elemento
            if i < len(st.session_state.resultados_actuales) - 1:
                timeline_html += '<div class="timeline-connector"></div>'
        
        timeline_html += "</div>"
        st.markdown(timeline_html, unsafe_allow_html=True)
        
        # Mostrar detalles expandibles
        st.subheader("🔍 Detalles Completos (Ordenados por Fecha)")
        
        for i, resultado in enumerate(st.session_state.resultados_actuales):
            # Determinar el orden cronológico
            orden_cronologico = "🕒 Más Reciente" if i == 0 else f"📅 Registro #{i+1}"
            
            with st.expander(f"{orden_cronologico} - Placa: {resultado['placa']} ({resultado['fecha']})"):
                
                # Información básica
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📍 Ubicación del Registro**")
                    st.write(f"**Hoja:** {resultado['hoja']}")
                    st.write(f"**Pestaña:** {resultado['pestana']}")
                    st.write(f"**Fila:** {resultado['fila']}")
                
                with col2:
                    st.markdown("**📊 Información Principal**")
                    st.write(f"**Placa:** {resultado['placa']}")
                    st.write(f"**Fecha:** {resultado['fecha']}")
                    st.write(f"**Empresa:** {resultado['empresa']}")
                    st.write(f"**Estado:** {resultado['trabajo']}")
                
                # Todos los datos de la fila
                st.markdown("**📄 Datos Completos de la Fila**")
                
                # Crear DataFrame con todos los datos
                df_detalle = pd.DataFrame({
                    'Campo': resultado['encabezados'],
                    'Valor': resultado['datos_completos']
                })
                
                st.dataframe(df_detalle, use_container_width=True, hide_index=True)
                
                # Botón de descarga individual
                excel_bytes = app.crear_excel_bytes(resultado)
                if excel_bytes:
                    st.download_button(
                        label=f"📥 Descargar Excel - Placa {resultado['placa']}",
                        data=excel_bytes,
                        file_name=f"placa_{resultado['placa']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"download_{i}"
                    )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
        f"🕒 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | "
        "🔗 Ejecutándose en GitHub Codespaces"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
