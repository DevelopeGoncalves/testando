from core.views import registrar_auditoria_backend

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from django.db.models.signals import post_save
from decimal import Decimal
from .models import Cliente, RegistroProducao, FinanceiroHabitacional
from .clientes_sync import propagar_para_registros

@receiver(user_logged_in)
def funcao_ao_logar(request, user, **kwargs):
    registrar_auditoria_backend(usuario=request.user, acao="Entrou", detalhe="Integra Banescor")

@receiver(user_logged_out)
def funcao_ao_deslogar(request, user, **kwargs):
    registrar_auditoria_backend(usuario=request.user, acao="Saiu", detalhe="Integra Banescor")

# O card Clientes e a base do cadastro: alterou ali (nome, e-mail, celular,
# telefone, nome social, CPF/CNPJ), a mudanca desce na hora para os registos
# de producao do Odonto e do Habitacional ligados aquele cliente.
@receiver(post_save, sender=Cliente)
def espelhar_cliente_nos_registros(sender, instance, **kwargs):
    propagar_para_registros(instance)


@receiver(post_save, sender=RegistroProducao)
def criar_financeiro_habitacional(sender, instance, created, **kwargs):
    if instance.fase == 'EMITIDOS' and instance.chave_unica:
        if instance.agrupamento and 'habitacional' in instance.agrupamento.agrupamento.lower():
            
            FinanceiroHabitacional.objects.get_or_create(
                registro_producao=instance,
                defaults={
                    'matricula_colaborador': instance.colaborador,
                    'valor': Decimal('100.00'),
                    'data_processamento': None
                }
            )