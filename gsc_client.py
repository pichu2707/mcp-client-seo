# API client de Google Search Console

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.oauth2 import service_account
from googleapiclient.discovery import build

class GSCClient:
    """
    Cliente para la API de Google Search Console
    """

    def __init__(self, credentials_path:  Path):
        """
        Inicalizar la API de google Search Consonle
        
        Args:
            credentials_path: Path al archivo de los credenciales de Google Cloud
        """
        self.credentials_path = credentials_path
        self.credentials = self._get_credentials()
        self.service = build(
            "searchconsole", "v1", credentials=self.credentials, cache_discovery=False
        )

    def _get_credentials(self) -> service_account.Credentials:
        """
        Obtener las credenciales de Google Cloud

        Returns:
            Credentials: Credenciales de Google Cloud
        """
        return service_account.Credentials.from_service_account_file(
            str(self.credentials_path)
        )
        
    async def list_sites(self) -> Dict[str, Any]:
        """
        Listar los sitios en Google Search Console

        Returns:
            Dict[str, Any]: Diccionario con la lista de sitios
        """
        try:
            response = self.service.sites().list().execute()

            sites = response.get('siteEntry', [])
            formatted_sites = []

            for site in sites:
                site_info = {
                    'siteUrl':site.get('siteUrl', ''),
                    'permissionLevel': site.get('permissionLevel', ''),
                }
                formatted_sites.append(site_info)

            return {
                "sites": formatted_sites,
                "total_sites": len(formatted_sites)
            }
        
        except Exception as e:
            raise Exception(f"Error al listar los sitios: {str(e)}")

    async def get_search_analytics (
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: Optional[List[str]] = None,
        search_type: Optional[str] = None,
        aggregation_type: Optional[str] = None,
        row_limit: int = 1000,
        fetch_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Toma os datos de search console e retorna as métricas solicitadas.

        Args:
            site_url: URL del sitio para el que se desean obtener los datos
            start_date: Fecha de inicio para el rango de fechas
            end_date: Fecha de fin para el rango de fechas
            dimensions: Dimensiones por las que se desea segmentar la información
            search_type: Tipo de búsqueda (web, imagen, video)
            aggregation_type: Tipo de agregación (auto, byPage, byQuery)
            row_limit: Límite de filas a retornar

        Returns:
            Dict[str, Any]: Diccionario con los datos de métricas solicitadas
        """

        #Validar datos
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Las fechas deben estar en formato YYYY-MM-DD")
        
        # Soporte para paginación
        all_rows = []
        start_row = 0
        max_rows_per_request = min(row_limit, 25000)  # GSC API limita a 25,000 por request
        total_fetched = 0
        keep_fetching = True

        while keep_fetching:
            request_body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "rowLimit": max_rows_per_request,
                "startRow": start_row,
            }

            #Añadir campos opcionales si se proporcionan.
            if search_type:
                valid_types = ['web', 'image', 'video', 'discover', 'googleNews']
                if search_type not in valid_types:
                    raise ValueError(f"Tipo de búsqueda inválido {search_type}. Debe ser uno de: {', '.join(valid_types)}")
                request_body['searchType'] = search_type

            if aggregation_type:
                valid_aggregations = ['auto', 'byPage', 'byQuery',"byNewsShowcasePanel"]
                if aggregation_type not in valid_aggregations:
                    raise ValueError(f"Tipo de agregación inválido {aggregation_type}. Debe ser uno de: {', '.join(valid_types)}")
                request_body['aggregationType'] = aggregation_type

            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body,
            ).execute()

            rows = response.get('rows', [])
            all_rows.extend(rows)
            fetched = len(rows)
            total_fetched += fetched

            # Condición de parada:
            # - Si no se pide fetch_all, solo una iteración (como antes)
            # - Si se pide fetch_all, seguir hasta que la respuesta traiga menos de max_rows_per_request
            if not fetch_all or fetched < max_rows_per_request or (row_limit and total_fetched >= row_limit):
                keep_fetching = False
            else:
                start_row += fetched

        # Limitar a row_limit si es necesario
        if row_limit and len(all_rows) > row_limit:
            all_rows = all_rows[:row_limit]

        # Formatear la respuesta
        formatted_response = self._format_search_analytics({"rows": all_rows}, dimensions or [])
        return formatted_response
    
    def _format_search_analytics(
            self, response: Dict[str, Any], dimensions: List[str]
    ) -> Dict[str, Any]:
        """
        Formatea la respuesta de la API de Search Console.

        Args:
            response: Respuesta cruda de la API
            dimensions: Dimensiones por las que se desea segmentar la información

        Returns:
            Dict[str, Any]: Diccionario con los datos formateados
        """
        rows = response.get('rows', [])
        formatted_rows = []
        for row in rows:
            formatted_row = {}
            # Añadir dimensiones
            keys = row.get('keys', [])
            for i, idm in enumerate(dimensions):
                if i < len(keys):
                    formatted_row[idm] = keys[i]
            # Añadir métricas
            formatted_row['clicks'] = row.get('clicks', 0)
            formatted_row['impressions'] = row.get('impressions', 0)
            formatted_row['ctr'] = row.get('ctr', 0.0)
            formatted_row['position'] = row.get('position', 0.0)
            formatted_rows.append(formatted_row)
        return {
            "rows": formatted_rows,
            "responseAggregationType": response.get('responseAggregationType', ''),
        }
