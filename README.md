# MCP Cliente – Conexión con Google Search Console  

Este proyecto implementa una **herramienta MCP (Model Context Protocol) a nivel de cliente**, pensada para integrarse con modelos de lenguaje (LLMs) como **Anthropic**, **OpenAI** o cualquier otro proveedor que se necesite.  

El objetivo inicial es:  

- Conectarse a **Google Search Console (GSC)**.  
- Extraer la información relevante de los proyectos.  
- Mostrar informes y datos directamente desde la **terminal**.  
- Servir como base para futuros desarrollos donde la información se procese con IA.  

---

## 🚀 Características principales  

- Cliente MCP en **Python**.  
- Integración inicial con **GSC API**.  
- Salida de datos en consola (ejemplo: impresiones, clics, CTR, posición media).  
- Compatible con **Anthropic** y extensible a **OpenAI** u otros LLMs.  
- Gestionado con **uv** para entornos y dependencias.  

---

## 📦 Instalación  

1. Clona este repositorio:  
```bash
git clone https://github.com/pichu2707/mcp-cliente.git
cd mcp-cliente
```
2. Crear entorno virtual
```bash
uv init
```

3. Instalar librerías necesarias
```bash 
uv pip install -r requirements.txt 
```


## Inicio del programa
Para tener una respuesta directa de una web sería de las siguiente manera:
```bash
python main.py --site "https://tusitio.com" --start 2025-01-01 --end 2025-01-31
```

Para poder abrir el chat en el terminal con el LLM se arranca de la siguiente manera
```bash
python anthropic_bridge.py
```