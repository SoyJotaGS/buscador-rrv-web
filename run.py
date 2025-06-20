#!/usr/bin/env python3
"""
Script para ejecutar el Buscador RRV en GitHub Codespaces
"""
import subprocess
import sys
import os
import time
import threading

def instalar_dependencias():
    """Instala las dependencias necesarias"""
    print("🔧 Instalando dependencias...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.run([sys.executable, "-m", "pip", "install", "pyngrok"])
    print("✅ Dependencias instaladas")

def configurar_ngrok():
    """Configura ngrok para acceso público"""
    try:
        from pyngrok import ngrok
        import getpass
        
        print("🔑 Configuración de ngrok para acceso público:")
        print("1. Ve a https://ngrok.com")
        print("2. Crea una cuenta gratuita")
        print("3. Copia tu authtoken")
        print()
        
        token = getpass.getpass("Pega tu token de ngrok aquí (opcional, Enter para omitir): ")
        if token.strip():
            ngrok.set_auth_token(token.strip())
            print("✅ ngrok configurado")
            return True
        else:
            print("⚠️ ngrok no configurado - solo acceso local")
            return False
    except ImportError:
        print("❌ Error importando pyngrok")
        return False

def ejecutar_streamlit():
    """Ejecuta la aplicación Streamlit"""
    print("🚀 Iniciando Buscador RRV...")
    
    # Verificar credenciales
    import glob
    json_files = glob.glob("*.json")
    if not json_files:
        print("⚠️ No se encontraron credenciales JSON")
        print("📁 Sube tu archivo de credenciales al repositorio")
        print("💡 O configúralo manualmente después")
    
    # Ejecutar Streamlit
    subprocess.run([
        "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.headless", "true",
        "--server.enableCORS", "false"
    ])

def crear_tunel_publico():
    """Crea túnel público con ngrok"""
    try:
        from pyngrok import ngrok
        time.sleep(10)  # Esperar que Streamlit inicie
        
        public_url = ngrok.connect(8501)
        print(f"\n🌐 URL PÚBLICA: {public_url}")
        print("📋 Comparte esta URL con tu equipo")
        
        # Mantener el túnel activo
        try:
            while True:
                time.sleep(60)
                print(f"✅ Aplicación activa - {time.strftime('%H:%M:%S')}")
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo aplicación...")
            ngrok.kill()
            
    except Exception as e:
        print(f"⚠️ No se pudo crear túnel público: {e}")
        print("💡 La aplicación sigue disponible localmente en el puerto 8501")

def main():
    print("🔍 BUSCADOR RRV - GitHub Codespaces")
    print("="*50)
    
    # Instalar dependencias
    instalar_dependencias()
    
    # Configurar ngrok
    ngrok_configurado = configurar_ngrok()
    
    print("\n🚀 Iniciando aplicación...")
    
    if ngrok_configurado:
        # Ejecutar Streamlit en hilo separado
        streamlit_thread = threading.Thread(target=ejecutar_streamlit)
        streamlit_thread.daemon = True
        streamlit_thread.start()
        
        # Crear túnel público
        crear_tunel_publico()
    else:
        # Solo ejecutar Streamlit
        print("📱 Aplicación disponible solo localmente")
        print("🔗 URL local: http://localhost:8501")
        ejecutar_streamlit()

if __name__ == "__main__":
    main()
