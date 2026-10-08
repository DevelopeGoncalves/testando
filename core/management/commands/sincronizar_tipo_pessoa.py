# Comando de manutencao (roda uma vez, depois pode apagar este arquivo):
#
#   python manage.py sincronizar_tipo_pessoa
#
# Arruma os registos de Vendas (Novo/Renovacao/Endosso) e os Clientes que ja
# tem CPF/CNPJ preenchido mas ficaram com o campo "Tipo de Pessoa" vazio -
# isso aconteceu porque esse campo foi adicionado DEPOIS desses registos
# existirem. Sem o Tipo de Pessoa preenchido, o campo aparece como "--
# Selecione --" na tela, e por ser obrigatorio trava a edicao.
#
# O tipo e descoberto pelo TAMANHO do numero que ja esta gravado (mesma
# regra que o sistema usava antes de ter o campo Tipo de Pessoa: ate 11
# digitos = CPF/Pessoa Fisica, mais que isso = CNPJ/Pessoa Juridica) - o
# numero em si NAO e alterado, so o Tipo de Pessoa e preenchido.
#
# Use --simular para so ver o relatorio, sem gravar nada.

from django.core.management.base import BaseCommand, CommandError

from core.models import Cliente, Indicacao, IndicacaoEndosso, IndicacaoRenovacao, TipoPessoa
from core.odonto import _sem_acento
from core.validadores import somente_digitos


class Command(BaseCommand):
    help = (
        'Preenche o Tipo de Pessoa (Fisica/Juridica) dos Clientes e registos de Vendas '
        'antigos que ja tem CPF/CNPJ mas ficaram sem o Tipo de Pessoa selecionado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--simular',
            action='store_true',
            help='So mostra o que seria feito, sem gravar no banco.',
        )

    def _localizar_tipos_pessoa(self):
        """Acha as linhas "Pessoa Fisica" e "Pessoa Juridica" em Base > Formularios >
        Tipos de pessoa (por texto, sem acento/maiuscula, pra nao depender de ID)."""
        fisica = juridica = None
        for tp in TipoPessoa.objects.all():
            texto = _sem_acento(tp.tipo_pessoa or '')
            if 'JURID' in texto:
                juridica = tp
            elif 'FISIC' in texto:
                fisica = tp
        if not fisica or not juridica:
            raise CommandError(
                'Nao encontrei "Pessoa Fisica" e/ou "Pessoa Juridica" em Base > '
                'Formularios > Tipos de pessoa. Confira se essas duas linhas existem '
                '(o nome pode ter outra grafia) antes de rodar o comando de novo.'
            )
        return fisica, juridica

    def _tipo_pelo_documento(self, valor, fisica, juridica):
        digitos = somente_digitos(valor)
        if not digitos:
            return None
        return fisica if len(digitos) <= 11 else juridica

    def _sincronizar_modelo(self, model, campo_documento, fisica, juridica, simular):
        pendentes = model.objects.filter(tipo_pessoa__isnull=True)

        atualizados = 0
        sem_documento = 0
        for registro in pendentes.iterator():
            tipo = self._tipo_pelo_documento(getattr(registro, campo_documento), fisica, juridica)
            if not tipo:
                sem_documento += 1
                continue
            atualizados += 1
            if not simular:
                registro.tipo_pessoa = tipo
                registro.save(update_fields=['tipo_pessoa'])

        return atualizados, sem_documento

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']
        fisica, juridica = self._localizar_tipos_pessoa()

        alvos = [
            (Cliente, 'cpf_cnpj', 'Clientes'),
            (Indicacao, 'cpf_cliente', 'Vendas > Novo'),
            (IndicacaoRenovacao, 'cpf_cliente', 'Vendas > Renovação'),
            (IndicacaoEndosso, 'cpf_cliente', 'Vendas > Endosso'),
        ]

        linhas = []
        total_atualizados = 0
        for model, campo, rotulo in alvos:
            atualizados, sem_documento = self._sincronizar_modelo(model, campo, fisica, juridica, simular)
            total_atualizados += atualizados
            linhas.append(f'{rotulo}: {atualizados} preenchido(s), {sem_documento} sem CPF/CNPJ pra identificar')

        self.stdout.write(self.style.SUCCESS(
            'Tipo de Pessoa "' + fisica.tipo_pessoa + '" (Física) e "' + juridica.tipo_pessoa + '" (Jurídica) localizados.\n'
            + '\n'.join(linhas)
            + f'\n\nTotal preenchido: {total_atualizados}'
        ))
        if simular:
            self.stdout.write(self.style.WARNING('Modo simulação: nada foi gravado. Rode sem --simular pra gravar de verdade.'))
