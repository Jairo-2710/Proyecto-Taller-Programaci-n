class ReglaNegocioError(Exception):
    """Se viola una regla de negocio (por defecto responde 409 Conflict)."""

    def __init__(self, mensaje: str, status_code: int = 409, info: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code
        self.info = info
