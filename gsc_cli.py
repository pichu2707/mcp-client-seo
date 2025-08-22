#!/usr/bin/env python3
"""
CLI para Google Search Console usando GSCClient
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

from config import Config
from gsc_client import GSCClient

load_dotenv(override=True)

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

def get_config():
    config = Config()
    creds = config.google_credentials
    if not creds:
        print("No se encontró el archivo de credenciales de Google.", file=sys.stderr)
        sys.exit(1)
    return creds

async def cmd_list_sites(args):
    creds = get_config()
    client = GSCClient(creds)
    result = await client.list_sites()
    print_json(result)

async def cmd_search_analytics(args):
    creds = get_config()
    client = GSCClient(creds)
    dimensions = [d.strip() for d in (args.dimensions or '').split(',') if d.strip()]
    result = await client.get_search_analytics(
        site_url=args.site_url,
        start_date=args.start_date,
        end_date=args.end_date,
        dimensions=dimensions or None,
        search_type=args.type,
        aggregation_type=args.aggregation_type,
        row_limit=args.row_limit,
    )
    print_json(result)

def main():
    parser = argparse.ArgumentParser(description="CLI para Google Search Console (MCP)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-sites
    parser_ls = subparsers.add_parser("list-sites", help="Lista los sitios en Google Search Console")
    parser_ls.set_defaults(func=cmd_list_sites)

    # search-analytics
    parser_sa = subparsers.add_parser("search-analytics", help="Consulta Search Analytics")
    parser_sa.add_argument("--site-url", required=True, help="URL del sitio a consultar")
    parser_sa.add_argument("--start-date", required=True, help="Fecha de inicio (YYYY-MM-DD)")
    parser_sa.add_argument("--end-date", required=True, help="Fecha de fin (YYYY-MM-DD)")
    parser_sa.add_argument("--dimensions", help="Dimensiones separadas por coma (ej: query,page)")
    parser_sa.add_argument("--type", help="Tipo de búsqueda (web, image, video, discover, googleNews)")
    parser_sa.add_argument("--aggregation-type", help="Tipo de agregación (auto, byPage, byQuery, byNewsShowcasePanel)")
    parser_sa.add_argument("--row-limit", type=int, default=1000, help="Límite de filas (default: 1000)")
    parser_sa.set_defaults(func=cmd_search_analytics)

    args = parser.parse_args()
    asyncio.run(args.func(args))

if __name__ == "__main__":
    main()
