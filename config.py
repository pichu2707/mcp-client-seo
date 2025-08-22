#Configuración de los MCP de Google Search Console

import os
import logging

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from pydantic import BaseModel, Field 

logger = logging.getLogger(__name__)
load_dotenv(override=True)

class Config(BaseModel):
    """
    Configuración de los MCP de Google Search Console
    """
    google_credentials_path: Optional[str] = Field(
        default=None,
        description="Ruta al archivo de credenciales de Google,"
        "Se utilizará la variable de entorno GOOGLE_APPLICATION_CREDENTIALS",
    )

    server_port: int = Field(
        default=8080,
        description="Puerto en el que se ejecutará el servidor MCP (por defecto: 8080)",
    )

    @property
    def google_credentials(self) -> Optional[Path]:
        """
        Devuelve la ruta al archivo de credenciales de Google.
        Si no se ha proporcionado, se utiliza la variable de entorno GOOGLE_APPLICATION_CREDENTIALS.
        """
        if self.google_credentials_path:
            creds_path = Path(self.google_credentials_path)
            if not creds_path.exists():
                logger.error(f"El archivo de credenciales no existe: {creds_path}")
                return None
            return creds_path
        
        env_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if env_creds:
            env_creds_path = Path(env_creds)
            if not env_creds_path.exists():
                logger.error(f"El archivo de credenciales no existe: {env_creds_path}")
                return None
            return env_creds_path

        logger.error("No se ha proporcionado ninguna ruta de credenciales.")
        return None
        