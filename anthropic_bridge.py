#!/usr/bin/env python3
"""
Puente entre Anthropic (Claude) y Google Search Console CLI
"""
import os
import subprocess
import json
import sys
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic

load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("No se encontró ANTHROPIC_API_KEY en el entorno.", file=sys.stderr)
    sys.exit(1)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Instrucción para el LLM: sugiere comandos CLI si es necesario
def build_system_prompt():
    return (
        "Eres un asistente experto en Google Search Console. "
        "Cuando el usuario pida datos, responde SOLO con el comando CLI exacto que debe ejecutarse, usando la siguiente sintaxis:\n"
        "Para listar sitios:\n"
        "list-sites\n"
        "Para analytics:\n"
        "search-analytics --site-url <URL de la propiedad seleccionada por el usuario> --start-date 2025-02-01 --end-date 2025-08-22 --dimensions query,page --type web\n"
        "Nunca uses 'https://tusitio.com/' ni ningún dominio genérico. Siempre usa la propiedad seleccionada por el usuario.\n"
        "No compares ni mezcles propiedades, solo responde sobre la propiedad seleccionada.\n"
        "Siempre usa los argumentos exactos: --site-url, --start-date, --end-date, --dimensions, --type, --aggregation-type, --row-limit.\n"
        "No uses --site ni --date-range. Si no tienes fechas, usa los últimos 6 meses calculando las fechas en formato YYYY-MM-DD.\n"
        "No expliques, solo responde con el comando CLI exacto."
    )

def call_cli(command: str) -> str:
    """Ejecuta el comando CLI y devuelve la salida."""
    # Limpiar comillas dobles innecesarias en los argumentos
    cleaned_command = command.replace('"', '')
    # Detectar si falta --site-url o si el valor es solo un nombre de dominio
    if 'search-analytics' in cleaned_command:
        # Obtener lista de sitios del usuario
        sites = get_user_sites()
        # Buscar --site-url o --site-url= en el comando
        m = re.search(r'--site-url[ =]([^ ]+)', cleaned_command)
        site_val = None
        if m:
            site_val = m.group(1)
            # Si solo es un nombre (sin punto), buscar coincidencia
            if '.' not in site_val:
                matches = [s for s in sites if site_val in s]
                if len(matches) == 1:
                    cleaned_command = cleaned_command.replace(site_val, matches[0])
                    site_val = matches[0]
                elif len(matches) > 1:
                    return f"Se encontraron varias propiedades que coinciden con '{site_val}':\n" + '\n'.join(matches) + "\nPor favor, especifica cuál quieres usar."
                else:
                    return f"No se encontró ninguna propiedad que coincida con '{site_val}'."
            else:
                # Si el dominio sugerido no está entre las propiedades, preguntar
                if site_val not in sites:
                    props = '\n'.join(f"{i+1}. {s}" for i, s in enumerate(sites))
                    print(f"\nEl dominio sugerido ('{site_val}') no está entre tus propiedades. ¿Sobre cuál quieres consultar?\n{props}")
                    while True:
                        sel = input("Elige el número de la propiedad: ").strip()
                        if sel.isdigit() and 1 <= int(sel) <= len(sites):
                            site_val = sites[int(sel)-1]
                            # Reemplazar el site-url en el comando
                            cleaned_command = re.sub(r'--site-url[ =][^ ]+', f'--site-url {site_val}', cleaned_command)
                            break
                        else:
                            print("Por favor, elige un número válido.")
        else:
            # Si no hay --site-url, preguntar al usuario por la propiedad
            if not sites:
                return "No tienes sitios registrados en Search Console."
            # Preguntar al usuario por la propiedad
            props = '\n'.join(f"{i+1}. {s}" for i, s in enumerate(sites))
            print(f"\nTienes varias propiedades en Search Console. ¿Sobre cuál quieres consultar?\n{props}")
            while True:
                sel = input("Elige el número de la propiedad: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(sites):
                    site_val = sites[int(sel)-1]
                    cleaned_command += f" --site-url {site_val}"
                    break
                else:
                    print("Por favor, elige un número válido.")

        # Detectar si la consulta es para una página específica
        if re.search(r'(página|ruta|url)', command, re.IGNORECASE):
            # Intentar extraer la URL de la página
            page_match = re.search(r'(https?://[\w\.-/]+)', command)
            if page_match:
                page_url = page_match.group(1)
                # Añadir filtro de página si no está ya en dimensiones
                if '--dimensions' not in cleaned_command:
                    cleaned_command += ' --dimensions page'
                # Añadir filtro de query para la página (esto requeriría modificar gsc_cli.py si se quiere filtrar por página)
                # Por ahora solo añade la dimensión
            else:
                print("No se detectó la URL de la página. La consulta se hará sobre todo el dominio.")

        # --- Manejo de fechas naturales y rangos ---
        # SIEMPRE ignorar fechas sugeridas por Claude y calcularlas automáticamente
        meses_match = re.search(r'ultim[oa]s? (\d+) mes', command, re.IGNORECASE)
        rango_match = re.search(r'de ([a-zA-Z]+) (\d{4}) a ([a-zA-Z]+) (\d{4})', command, re.IGNORECASE)
        fechas = None
        if meses_match:
            months = int(meses_match.group(1))
            end_date = (datetime.today() - timedelta(days=2)).date()
            start_date = (end_date - timedelta(days=months*30))
            fechas = (start_date, end_date)
        elif rango_match:
            meses = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
            mes_ini = meses.get(rango_match.group(1).lower(), 1)
            anio_ini = int(rango_match.group(2))
            mes_fin = meses.get(rango_match.group(3).lower(), 12)
            anio_fin = int(rango_match.group(4))
            start_date = datetime(anio_ini, mes_ini, 1).date()
            if mes_fin == 12:
                end_date = datetime(anio_fin, 12, 31).date()
            else:
                end_date = (datetime(anio_fin, mes_fin+1, 1) - timedelta(days=1)).date()
            # Ajustar end_date si es mayor que hoy-2
            max_end = (datetime.today() - timedelta(days=2)).date()
            if end_date > max_end:
                end_date = max_end
            fechas = (start_date, end_date)
        else:
            # Si no hay fechas, usar últimos 6 meses por defecto y delay de 2 días
            end_date = (datetime.today() - timedelta(days=2)).date()
            start_date = (end_date - timedelta(days=6*30))
            fechas = (start_date, end_date)
        # Eliminar cualquier --start-date y --end-date del comando original
        cleaned_command = re.sub(r'--start-date[ =][^ ]+', '', cleaned_command)
        cleaned_command = re.sub(r'--end-date[ =][^ ]+', '', cleaned_command)
        # Añadir fechas calculadas
        cleaned_command += f' --start-date {fechas[0].isoformat()} --end-date {fechas[1].isoformat()}'
    args = [sys.executable, "gsc_cli.py"] + cleaned_command.strip().split()
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error ejecutando el comando: {e.stderr}"

# Obtener lista de sitios del usuario usando el CLI
def get_user_sites():
    args = [sys.executable, "gsc_cli.py", "list-sites"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return [s['siteUrl'] for s in data.get('sites', [])]
    except Exception:
        return []


def main():
    print("¡Bienvenido! Escribe tu pregunta sobre Google Search Console (o 'salir' para terminar):")
    print("Puedes cambiar el modo de respuesta escribiendo: /modo texto, /modo json o /modo ambos\n")
    modo = "texto"  # Por defecto
    propiedad_actual = None
    ultimo_json = None
    ultima_pregunta = None
    ultimo_rango = None  # (start_date, end_date)
    sites = get_user_sites()
    while True:
        try:
            # Leer bytes y decodificar explícitamente para evitar UnicodeDecodeError
            print("Usuario: ", end="", flush=True)
            user_input = sys.stdin.buffer.readline().decode("utf-8", errors="replace").strip()
        except Exception as e:
            print(f"\n[Error de entrada: {e}]")
            continue
        # Si el usuario menciona explícitamente un dominio, actualizar propiedad_actual
        propiedad_cambiada = False
        for s in sites:
            dominio_simple = s.replace('https://','').replace('http://','').replace('/','')
            if dominio_simple in user_input or s in user_input or (s.startswith('sc-domain:') and s.replace('sc-domain:','') in user_input):
                if propiedad_actual != s:
                    propiedad_actual = s
                    propiedad_cambiada = True
                    ultimo_json = None
                    ultimo_rango = None
                    print(f"\nUsando la propiedad: {propiedad_actual}")
                break
        if user_input.lower() in ("salir", "exit", "quit"): break
        if user_input.lower().startswith("/modo"):
            nuevo_modo = user_input.lower().replace("/modo", "").strip()
            if nuevo_modo in ("texto", "json", "ambos"):
                modo = nuevo_modo
                propiedad_actual = None
                print(f"Modo de respuesta cambiado a: {modo}\n")
            else:
                print("Modos válidos: texto, json, ambos\n")
            continue

        # 1. Pedir a Claude el comando CLI adecuado, pasando contexto de propiedad si existe
        contexto = ""
        if propiedad_actual:
            contexto += f"La propiedad seleccionada es: {propiedad_actual}. "
        else:
            # Si no hay propiedad seleccionada, pedir al usuario que elija una vez
            print("\nPropiedades disponibles:")
            for idx, site in enumerate(sites):
                print(f"  {idx+1}. {site}")
            while True:
                seleccion = input("Selecciona el número de la propiedad a consultar o escribe el dominio: ").strip()
                if seleccion.isdigit() and 1 <= int(seleccion) <= len(sites):
                    propiedad_actual = sites[int(seleccion)-1]
                    print(f"\nUsando la propiedad: {propiedad_actual}")
                    break
                elif any(seleccion in s for s in sites):
                    propiedad_actual = next(s for s in sites if seleccion in s)
                    print(f"\nUsando la propiedad: {propiedad_actual}")
                    break
                else:
                    print("Dominio no válido. Intenta de nuevo.")
            contexto += f"La propiedad seleccionada es: {propiedad_actual}. "
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            temperature=0,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": contexto + user_input}]
        )
        content = response.content[0].text.strip()

        # 2. Detectar si la pregunta pide un rango de fechas diferente
        def extraer_rango(pregunta):
            meses_match = re.search(r'ultim[oa]s? (\d+) mes', pregunta, re.IGNORECASE)
            rango_match = re.search(r'de ([a-zA-Z]+) (\d{4}) a ([a-zA-Z]+) (\d{4})', pregunta, re.IGNORECASE)
            if meses_match:
                months = int(meses_match.group(1))
                end_date = (datetime.today() - timedelta(days=2)).date()
                start_date = (end_date - timedelta(days=months*30))
                return (start_date.isoformat(), end_date.isoformat())
            elif rango_match:
                meses = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
                mes_ini = meses.get(rango_match.group(1).lower(), 1)
                anio_ini = int(rango_match.group(2))
                mes_fin = meses.get(rango_match.group(3).lower(), 12)
                anio_fin = int(rango_match.group(4))
                start_date = datetime(anio_ini, mes_ini, 1).date()
                if mes_fin == 12:
                    end_date = datetime(anio_fin, 12, 31).date()
                else:
                    end_date = (datetime(anio_fin, mes_fin+1, 1) - timedelta(days=1)).date()
                max_end = (datetime.today() - timedelta(days=2)).date()
                if end_date > max_end:
                    end_date = max_end
                return (start_date.isoformat(), end_date.isoformat())
            return None

        nuevo_rango = extraer_rango(user_input)

        # 3. Si la respuesta es un comando CLI válido, ejecutarlo
        if content.startswith("list-sites") or content.startswith("search-analytics"):
            # Si el usuario menciona un dominio válido, forzar siempre la consulta CLI
            ejecutar = True
            if propiedad_cambiada:
                ejecutar = True
            elif nuevo_rango:
                if ultimo_rango != nuevo_rango:
                    ejecutar = True
                else:
                    ejecutar = False if ultimo_json else True
            if ejecutar:
                output = call_cli(content)
                # Si se seleccionó una propiedad, recordarla
                m = re.search(r'--site-url[ =]([^ ]+)', content)
                if m:
                    propiedad_actual = m.group(1)
                # Guardar el último JSON si es válido
                try:
                    parsed = json.loads(output)
                    ultimo_json = output
                except Exception:
                    ultimo_json = None
                ultimo_rango = nuevo_rango
            # Por defecto, solo mostrar la explicación de Claude
            if modo == "json":
                print(f"\nRespuesta CLI (JSON):\n{ultimo_json}")
            else:
                # Filtrar el JSON para mostrar solo los 10 primeros resultados relevantes por defecto
                resumen = ""
                def limpiar_keys_recursivo(obj):
                    if isinstance(obj, dict):
                        return {k: limpiar_keys_recursivo(v) for k, v in obj.items() if k != 'keys'}
                    elif isinstance(obj, list):
                        return [limpiar_keys_recursivo(x) for x in obj]
                    else:
                        return obj
                try:
                    parsed = json.loads(ultimo_json) if ultimo_json else {}
                    # Asegurarse de que 'rows' es una lista de diccionarios planos
                    if isinstance(parsed, dict) and 'rows' in parsed and isinstance(parsed['rows'], list):
                        filas_limpias = [limpiar_keys_recursivo(f) for f in parsed['rows']]
                        total = len(filas_limpias)
                        top = filas_limpias[:10]
                        resumen_dict = dict(parsed)
                        resumen_dict['rows'] = top
                        resumen = json.dumps(resumen_dict, ensure_ascii=False, indent=2)
                        if total > 10:
                            print(f"\nSe han encontrado {total} resultados. Mostrando los 10 primeros.")
                            ver_mas = input("¿Quieres ver todos los resultados? (s/n): ").strip().lower()
                            if ver_mas == 's':
                                resumen_dict['rows'] = filas_limpias
                                resumen = json.dumps(resumen_dict, ensure_ascii=False, indent=2)
                    else:
                        resumen = ultimo_json if ultimo_json and len(ultimo_json) < 6000 else (ultimo_json[:6000] + "... (truncado)" if ultimo_json else "")
                except Exception:
                    resumen = ultimo_json if ultimo_json and len(ultimo_json) < 6000 else (ultimo_json[:6000] + "... (truncado)" if ultimo_json else "")
                explicacion = ""
                try:
                    # Si la pregunta es de seguimiento, pasar el último JSON y la última pregunta
                    if ultima_pregunta and ultimo_json:
                        prompt_explica = (
                            f"Pregunta anterior: {ultima_pregunta}\n"
                            f"Respuesta anterior (JSON): {resumen}\n"
                            f"Nueva pregunta: {user_input}\n"
                            "Responde SOLO sobre la propiedad seleccionada. Explica en español de forma clara y útil, resalta insights, tendencias, posibles canibalizaciones y responde a la intención del usuario. Si no hay datos, indícalo de forma amable."
                        )
                    else:
                        prompt_explica = (
                            "Eres un experto en Google Search Console. Explica en español de forma clara y útil el siguiente resultado JSON de una consulta, "
                            "resalta insights, tendencias, posibles canibalizaciones y responde a la intención del usuario. Si no hay datos, indícalo de forma amable.\n\n" + resumen
                        )
                    r2 = client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=300,
                        temperature=0,
                        system="",
                        messages=[{"role": "user", "content": prompt_explica}]
                    )
                    explicacion = r2.content[0].text.strip()
                except Exception as e:
                    explicacion = f"No se pudo obtener explicación: {e}"
                if modo == "ambos":
                    print(f"\nRespuesta CLI (JSON):\n{ultimo_json}\n\nExplicación de Claude:\n{explicacion}")
                else:
                    print(f"\n{explicacion}")
            ultima_pregunta = user_input
        else:
            # Si la pregunta es de seguimiento y hay contexto, pasar el último JSON
            if ultimo_json:
                prompt_explica = (
                    f"Pregunta anterior: {ultima_pregunta}\n"
                    f"Respuesta anterior (JSON): {ultimo_json}\n"
                    f"Nueva pregunta: {user_input}\n"
                    "Responde SOLO sobre la propiedad seleccionada. Explica en español de forma clara y útil, resalta insights, tendencias, posibles canibalizaciones y responde a la intención del usuario. Si no hay datos, indícalo de forma amable."
                )
                r2 = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=300,
                    temperature=0,
                    system="",
                    messages=[{"role": "user", "content": prompt_explica}]
                )
                explicacion = r2.content[0].text.strip()
                print(f"\n{explicacion}")
            else:
                print(f"\nClaude responde:\n{content}")

if __name__ == "__main__":
    main()
