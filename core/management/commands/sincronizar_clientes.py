# Comando de manutencao (roda uma vez, depois so quando precisar):
#
#   python manage.py sincronizar_clientes
#
# Arruma o que ficou de tras nas importacoes antigas:
# 1) Registo de producao com CPF/CNPJ mas sem cadastro no card Clientes -> cria
#    o cliente e guarda o ID em `cliente_cadastro`.
# 2) Registo que ja tem o CPF/CNPJ de um cliente cadastrado -> liga no ID e
#    passa a espelhar os dados do cadastro (o card Clientes e a base).
#
# Use --simular para so ver o relatorio, sem gravar nada.

from django.core.management.base import BaseCommand

from core.clientes_sync import (
    dados_do_cliente,
    propagar_para_registros,
    sincronizar_cliente,
    somente_digitos,
)
from core.models import Cliente, RegistroProducao


class Command(BaseCommand):
    help = 'Liga os registos de producao ao cadastro do card Clientes pelo CPF/CNPJ.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simular',
            action='store_true',
            help='So mostra o que seria feito, sem gravar no banco.',
        )

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']

        sem_vinculo = RegistroProducao.objects.filter(cliente_cadastro__isnull=True)
        criados = 0
        ligados = 0
        sem_documento = 0

        for registro in sem_vinculo.iterator():
            if not somente_digitos(registro.cpf_cnpj):
                sem_documento += 1
                continue

            if simular:
                ligados += 1
                continue

            existia = Cliente.objects.filter(
                cpf_cnpj=somente_digitos(registro.cpf_cnpj)[:14]
            ).exists()

            cliente = sincronizar_cliente(
                cpf_cnpj=registro.cpf_cnpj,
                nome=registro.cliente or registro.segurado,
                nome_social=registro.nome_social,
                celular=registro.celular,
                telefone=registro.telefone,
                email=registro.email,
                tipo_pessoa=registro.tipo_pessoa,
            )
            if not cliente:
                sem_documento += 1
                continue

            registro.cliente_cadastro = cliente
            for campo, valor in dados_do_cliente(cliente).items():
                setattr(registro, campo, valor)
            registro.save()

            ligados += 1
            if not existia:
                criados += 1

        # Passa em todos os cadastros para deixar os registos iguais a base
        espelhados = 0
        if not simular:
            for cliente in Cliente.objects.iterator():
                espelhados += propagar_para_registros(cliente)

        self.stdout.write(self.style.SUCCESS(
            f'Registos ligados ao cadastro: {ligados}\n'
            f'Clientes novos criados: {criados}\n'
            f'Registos espelhados a partir do card Clientes: {espelhados}\n'
            f'Registos sem CPF/CNPJ (nao da para identificar): {sem_documento}'
        ))
        if simular:
            self.stdout.write(self.style.WARNING('Modo simulacao: nada foi gravado.'))
