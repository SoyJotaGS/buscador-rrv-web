# 🔍 BUSCADOR RRV - Aplicación Web

Esta es la versión web del Buscador RRV que te permite buscar placas en Google Sheets desde cualquier navegador web.

## 📋 Características

- ✅ Interfaz web moderna y responsive
- ✅ Búsqueda en tiempo real en Google Sheets
- ✅ Visualización de resultados en tabla interactiva
- ✅ Exportación a Excel con un clic
- ✅ Detalles completos de cada registro
- ✅ Acceso desde cualquier dispositivo con navegador

## 🚀 Instalación y Configuración

### 1. Requisitos Previos
- Python 3.8 o superior
- Archivo de credenciales de Google Sheets (archivo .json)

### 2. Instalación

```bash
# Clonar o descargar los archivos
# Navegar al directorio del proyecto
cd RRV

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración de Credenciales

Asegúrate de que tu archivo de credenciales JSON esté en el mismo directorio que `app.py`.

## 🖥️ Ejecución

### Servidor Local (Recomendado)

```bash
# Ejecutar la aplicación
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

### Opciones de Configuración

```bash
# Ejecutar en un puerto específico
streamlit run app.py --server.port 8080

# Ejecutar para acceso externo (red local)
streamlit run app.py --server.address 0.0.0.0

# Ejecutar sin abrir navegador automáticamente
streamlit run app.py --server.headless true
```

## 🌐 Acceso desde Otros Dispositivos

### En Red Local
1. Ejecuta con `--server.address 0.0.0.0`
2. Obtén tu IP local: `ipconfig` (Windows) o `ifconfig` (Mac/Linux)
3. Accede desde otros dispositivos: `http://TU_IP:8501`

### Ejemplo:
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Luego accede desde: `http://192.168.1.100:8501` (usa tu IP real)

## 📱 Uso de la Aplicación

1. **Buscar Placa**: Ingresa la placa en el campo de búsqueda
2. **Ver Resultados**: Los resultados aparecerán en una tabla
3. **Ver Detalles**: Haz clic en "Detalles Completos" para expandir información
4. **Exportar**: Usa los botones de descarga para obtener archivos Excel

## 🔧 Solución de Problemas

### Error de Conexión a Google Sheets
- Verifica que el archivo JSON esté en el directorio correcto
- Asegúrate de que las credenciales tengan los permisos necesarios

### Puerto Ocupado
```bash
# Si el puerto 8501 está ocupado, usa otro
streamlit run app.py --server.port 8502
```

### Acceso Negado desde Red Externa
```bash
# Para acceso desde internet (NO recomendado para producción)
streamlit run app.py --server.address 0.0.0.0 --server.enableCORS false
```

## 📋 Comandos Útiles

```bash
# Ver todas las opciones de configuración
streamlit config show

# Limpiar caché de Streamlit
streamlit cache clear

# Ver información del sistema
streamlit --version
```

## 🔒 Seguridad

- ⚠️ No expongas la aplicación directamente a internet sin autenticación
- 🔐 Mantén seguro tu archivo de credenciales JSON
- 🛡️ Para uso en producción, considera usar un servidor web reverse proxy

## 📞 Soporte

Si encuentras algún problema:
1. Verifica que todas las dependencias están instaladas
2. Revisa que el archivo de credenciales está presente
3. Consulta los logs en la terminal donde ejecutaste la aplicación

---
**¡Disfruta usando el Buscador RRV en la web! 🎉** 