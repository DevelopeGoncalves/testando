import logging

from .models import AuditoriaExportacao

logger = logging.getLogger(__name__)


def registrar_auditoria_backend(usuario, acao, detalhe):
    try:
        AuditoriaExportacao.objects.create(
            usuario=usuario,
            acao=acao,
            detalhe=detalhe
        )

    except Exception as e:
        # Tipo console.error()
        logger.error(f"Falha ao registrar auditoria no backend: {e}")
