# Implementación del Servidor del CMP de Google Search Console

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import Server, NotificationOptions
import mcp.server.stdio

from config import Config
from gsc_client import GSCClient

class GSCMCPServer:
    """
    Servidor del CMP de Google Search Console
    """

    def __init__(self, config: Config):
        """
        Inicializa el servidor del CMP de Google Search Console
        Args:
            config (Config): La configuración del servidor.
        """
        self.config = config
        self.gsc_client = GSCClient(config.google_credentials)
        self.server = Server(config.server_port)

        #Inicializando el GSC client si las credenciales son válidas
        if self.config.google_credentials:
            self.gsc_client = GSCClient(self.config.google_credentials)

        #Configurar controladores
        self._setup_handlers()

    def _setup_handlers(self):
        """
        Configura los controladores para el servidor.
        """
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            tools = [
                types.Tool(
                    name="list_sites",
                    description="Lista los sitios en Google Search Console",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    },
                ),
                types.Tool(
                    name="search_analytics",
                    description="Realiza una búsqueda en Google Search Console",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "siteUrl": {
                                "type": "string",
                                "description": "La URL del sitio a buscar"
                            },
                            "startDate": {
                                "type": "string",
                                "description": "La fecha de inicio de la búsqueda"
                            },
                            "endDate": {
                                "type": "string",
                                "description": "La fecha de fin de la búsqueda"
                            },
                            "dimensions": {
                                "type": "string",
                                "description": "Las dimensiones de la búsqueda"
                            },
                            "type": {
                                "type": "string",
                                "description": "El tipo de búsqueda"
                            },
                            "aggregationType": {
                                "type": "string",
                                "description": "El tipo de agregación ( auto, byPage, byProperty, byNewShowcasePanel)"
                            },
                            "rowLimit": {
                                "type": "integer",
                                "description": "El límite de filas a retornar (por defecto: 1000)"
                            },
                        },
                    },
                ),
            ]
            return tools

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            if not self.gsc_client:
                raise RuntimeError("GSC client no inicializado")
            if name == "list_sites":
                try:
                    result = await self.gsc_client.list_sites()
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2)
                        )
                    ]
                except Exception as e:
                    raise RuntimeError(f"Error al llamar a list_sites: {e}")
            elif name == "search_analytics":
                try:
                    if not arguments:
                        raise ValueError("No se proporcionaron argumentos para search_analytics")
                    site_url = arguments.get("siteUrl")
                    start_date = arguments.get("startDate")
                    end_date = arguments.get("endDate")
                    if not site_url or not start_date or not end_date:
                        raise ValueError("siteUrl, startDate y endDate son obligatorios")
                    dimensions_str = arguments.get("dimensions", "")
                    dimensions = [dim.strip() for dim in dimensions_str.split(",")] if dimensions_str else None
                    search_type = arguments.get("type")
                    aggregation_type = arguments.get("aggregationType")
                    row_limit = arguments.get("rowLimit", 1000)
                    result = await self.gsc_client.search_analytics(
                        site_url=site_url,
                        start_date=start_date,
                        end_date=end_date,
                        dimensions=dimensions,
                        type=search_type,
                        aggregation_type=aggregation_type,
                        row_limit=row_limit
                    )
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2)
                        )
                    ]
                except Exception as e:
                    raise RuntimeError(f"Error al llamar a search_analytics: {e}")
            else:
                raise ValueError(f"Herramienta desconocida: {name}")


    async def run(self):
        """
        Ejecuta el servidor del MCP
        """
        if not self.gsc_client:
            print("Error, Google Search Console Credentials no han sido encontradas.", file=sys.stderr)
            return
        # Prueba el cliente GSC para asegurarte de que funciona correctamente.
        try:
            _ = self.gsc_client.service
            print("Google Search Console inicializado", file=sys.stderr)
        except Exception as e:
            print(f"Error al inicializar Google Search Console: {e}", file=sys.stderr)
            return
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="google-search-console", 
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )