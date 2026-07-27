from core.views import registrar_auditoria_backend

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

@receiver(user_logged_in)
def funcao_ao_logar(request, user, **kwargs):
    registrar_auditoria_backend(usuario=request.user,acao="Entrou", detalhe="Integra Banescor")

@receiver(user_logged_out)
def funcao_ao_deslogar(request, user, **kwargs):
    registrar_auditoria_backend(usuario=request.user,acao="Saiu", detalhe="Integra Banescor")