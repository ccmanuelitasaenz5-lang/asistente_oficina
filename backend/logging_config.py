import re
import logging

class RedactarSecretosFilter(logging.Filter):
    """Filtra y enmascara tokens, claves de API y secretos que puedan colarse en los logs."""
    _PATRONES = [
        (re.compile(r'(token=)[^&\s]+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(api_key=)[^&\s]+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(bearer\s+)[a-zA-Z0-9_\-\.]{10,}', re.IGNORECASE), r'\1[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for patron, reemplazo in self._PATRONES:
                record.msg = patron.sub(reemplazo, record.msg)
        return True

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    filtro_seguro = RedactarSecretosFilter()
    logging.getLogger().addFilter(filtro_seguro)
    logging.getLogger("uvicorn.access").addFilter(filtro_seguro)

    # Ajustar niveles de librerías ruidosas si es necesario
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
