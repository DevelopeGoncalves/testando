# Testes da regra "card Clientes e a base" (ver core/clientes_sync.py):
#   python manage.py test core.tests_clientes_sync

from django.test import TestCase

from .clientes_sync import sincronizar_cliente
from .models import Cliente, RegistroProducao, TipoPessoa


class SincronizacaoClienteTests(TestCase):
    def setUp(self):
        TipoPessoa.objects.create(tipo_pessoa='Pessoa Física')
        TipoPessoa.objects.create(tipo_pessoa='Pessoa Jurídica')

    def _importar(self, **campos):
        """Simula uma linha de planilha chegando na importacao."""
        dados = {
            'cpf_cnpj': '12345678901',
            'nome': 'MARIA SILVA',
            'email': 'maria@antigo.com',
            'celular': '27999990000',
        }
        dados.update(campos)
        return sincronizar_cliente(**dados)

    def test_reimportacao_atualiza_o_cadastro_em_vez_de_duplicar(self):
        cliente = self._importar()
        mesmo = self._importar(nome='MARIA SILVA SANTOS', email='maria@novo.com')

        self.assertEqual(cliente.id, mesmo.id)
        self.assertEqual(Cliente.objects.count(), 1)

        cliente.refresh_from_db()
        self.assertEqual(cliente.nome, 'MARIA SILVA SANTOS')
        self.assertEqual(cliente.email, 'maria@novo.com')

    def test_documento_formatado_e_o_mesmo_cliente(self):
        antigo = Cliente.objects.create(cpf_cnpj='123.456.789-01', nome='MARIA')
        cliente = self._importar()

        self.assertEqual(antigo.id, cliente.id)
        self.assertEqual(Cliente.objects.count(), 1)
        # o cadastro antigo fica normalizado com so numeros
        self.assertEqual(cliente.cpf_cnpj, '12345678901')

    def test_alteracao_no_card_clientes_desce_para_o_registo(self):
        cliente = self._importar()
        registro = RegistroProducao.objects.create(
            cliente_cadastro=cliente, cpf_cnpj='12345678901',
            cliente='MARIA SILVA', email='maria@antigo.com',
        )

        cliente.nome = 'MARIA SILVA SANTOS'
        cliente.email = 'maria@novo.com'
        cliente.save()

        registro.refresh_from_db()
        self.assertEqual(registro.cliente, 'MARIA SILVA SANTOS')
        self.assertEqual(registro.email, 'maria@novo.com')

    def test_registo_antigo_sem_vinculo_e_adotado_pelo_cpf(self):
        registro = RegistroProducao.objects.create(
            cpf_cnpj='12345678901', cliente='MARIA', email='maria@antigo.com',
        )
        cliente = self._importar(email='maria@novo.com')

        registro.refresh_from_db()
        self.assertEqual(registro.cliente_cadastro_id, cliente.id)
        self.assertEqual(registro.email, 'maria@novo.com')

    def test_linha_sem_cpf_nao_cria_cliente(self):
        self.assertIsNone(self._importar(cpf_cnpj=''))
        self.assertEqual(Cliente.objects.count(), 0)

    def test_tipo_pessoa_vem_do_tamanho_do_documento(self):
        pf = self._importar()
        pj = self._importar(cpf_cnpj='12345678000199', nome='EMPRESA LTDA')

        self.assertEqual(pf.tipo_pessoa.tipo_pessoa, 'Pessoa Física')
        self.assertEqual(pj.tipo_pessoa.tipo_pessoa, 'Pessoa Jurídica')
