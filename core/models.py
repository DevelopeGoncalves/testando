from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

class Colaborador(models.Model):
    # Ligação com a tabela de Agências
    unidade = models.ForeignKey('Unidade', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Unidade (CID)")
    
    matricula = models.CharField("Matrícula", max_length=50, blank=True, null=True)
    colaborador = models.CharField("Nome do Colaborador", max_length=150)
    nome_social = models.CharField("Nome Social", max_length=150, blank=True, null=True)
    cpf = models.CharField("CPF", max_length=20, blank=True, null=True)

    funcao = models.IntegerField("Função", blank=True, null=True)
    
    suspenso = models.BooleanField("Suspenso", default=False)
    impedido = models.BooleanField("Impedido", default=False)
    inativo = models.BooleanField("Inativo", default=False)
    
    observacoes = models.TextField("Observações", blank=True, null=True) 
    
    # O auto_now=True faz o Django atualizar essa data/hora sozinho sempre que salvar
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    # NOVOS CAMPOS PARA ESTAGIÁRIOS
    data_inicio_emprego = models.DateField("Data de Início no Emprego", blank=True, null=True)
    data_fim_emprego = models.DateField("Data de fim no Emprego", blank=True, null=True)

    def __str__(self):
        # Mostra o nome social se tiver, senão mostra o nome de registro
        return self.nome_social if self.nome_social else self.colaborador

    # alex: "matrícula - nome" para o campo de responsável (pesquisa por matrícula ou nome)
    @property
    def matricula_nome(self):
        nome = self.nome_social or self.colaborador
        return f"{self.matricula} - {nome}" if self.matricula else nome

class Contratado(models.Model):
    TIPO_PESSOA_CHOICES = [
        ('F', 'Física'),
        ('J', 'Jurídica'),
    ]
    # Tamanho 1, Obrigatório (sem blank/null)
    tipo_pessoa = models.CharField("Tipo de Pessoa", max_length=1, choices=TIPO_PESSOA_CHOICES)
    
    cpf_cnpj = models.CharField("CPF / CNPJ", max_length=14, unique=True)
    contratado = models.CharField("Contratado", max_length=60)
    matricula = models.CharField("Matrícula", max_length=9, blank=True, null=True)
    numero_dependente = models.IntegerField("Nº Dependentes", blank=True, null=True)
    celular = models.CharField("Celular", max_length=11, blank=True, null=True)
    telefone = models.CharField("Telefone", max_length=10, blank=True, null=True)
    email = models.EmailField("Email", max_length=80, blank=True, null=True)
    
    # Dados Bancários
    banco = models.CharField("Banco", max_length=4, blank=True, null=True)
    unidade = models.CharField("Agência", max_length=4, blank=True, null=True)
    conta_corrente = models.CharField("Conta Corrente", max_length=20, blank=True, null=True)
    
    # Data
    celebrado_em = models.DateField("Celebrado em", blank=True, null=True)
    
    # Observações (Tamanho 50)
    observacoes = models.CharField("Observações", max_length=50, blank=True, null=True)

    def __str__(self): 
        return self.contratado

class Seguradora(models.Model):
    cod_seguradora = models.CharField("Cód. Seguradora", max_length=4, unique=True, null=True)
    seguradora = models.CharField("Seguradora", max_length=50, null=True)
    cnpj = models.CharField("CNPJ", max_length=14, blank=True)
    observacoes = models.CharField("Observações", max_length=80, blank=True, null=True)

    def __str__(self):
        return f"{self.cod_seguradora} - {self.seguradora}"

class TipoDocumento(models.Model):
    tipo_documento = models.CharField("Tipo de Documento", max_length=12, unique=True, null=True)
    observacoes = models.CharField("Observações", max_length=50, blank=True, null=True)

    def __str__(self): 
        return self.tipo_documento
    
class TipoPessoa(models.Model):
    #  Aqui O Django vai usar apenas o ID numérico automático, troquei o numeor por letra 
    tipo_pessoa = models.CharField("Tipo de Pessoa", max_length=50)
    observacoes = models.CharField("Observações", max_length=100, blank=True, null=True)

    def __str__(self):
        return self.tipo_pessoa

# Classe Cliente vai ser utilizando a chave estrangeira do card vulgo (tabela) TipoPessoa
class Cliente(models.Model):
    tipo_pessoa = models.ForeignKey('TipoPessoa', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo de Pessoa")
    cpf_cnpj = models.CharField("CPF / CNPJ", max_length=14, blank=True, unique=True, null=True)
    nome = models.CharField("Nome", max_length=60, null=True)
    nome_social = models.CharField("Nome Social", max_length=60, blank=True)
    celular = models.CharField("Celular", max_length=11, blank=True, null=True)
    telefone = models.CharField("Telefone", max_length=10, blank=True)
    email = models.EmailField("Email", max_length=80, blank=True)
    observacoes = models.CharField("Observações", max_length=80, blank=True, null=True)

    def __str__(self): 
        return self.nome

# TABELAS DE HIERARQUIA E AGRUPAMENTO

class Agrupamento(models.Model):
    agrupamento = models.CharField("Agrupamento", max_length=150, unique=True)
    inativo = models.BooleanField("Inativo", default=False)
    ordem_apresentacao = models.IntegerField("Ordem de Apresentação", blank=True, null=True)
    observacoes = models.TextField("Observações", blank=True, null=True)

    def __str__(self):
        return self.agrupamento

class Produto(models.Model):
    agrupamento = models.ForeignKey('Agrupamento', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Agrupamento")
    produto = models.CharField("Produto", max_length=150, unique=True)
    inativo = models.BooleanField("inativo", default=False)
    divulgacao_ativa = models.BooleanField("Divulgação Ativa", default=False)
    prioridade_divulgacao = models.IntegerField("Prioridade de Divulgação", blank=True, null=True)
    
    mes_producao_em_aberto = models.DateField("Mês Production em Aberto", blank=True, null=True)
    mes_folha_pagamento_em_aberto = models.DateField("Mês Folha Pgto em Aberto", blank=True, null=True)
    
    observacoes = models.TextField("Observações", blank=True, null=True)

    def __str__(self):
        return self.produto

class EstadoAnbima(models.Model):
    uf = models.CharField("UF", max_length=2)
    estado = models.CharField("Estado", max_length=50)
    uf_estado = models.CharField("UF - Estado", max_length=60, blank=True)
    ordem_apresentacao = models.IntegerField("Ordem de Apresentação", default=0)

    def save(self, *args, **kwargs):
        self.uf = (self.uf or '').strip().upper()
        # padroniza o Estado: 1ª letra maiúscula e o resto minúsculo
        # (ex.: "SÃO PAULO" ou "são paulo" -> "São paulo")
        self.estado = (self.estado or '').strip().capitalize()
        self.uf_estado = f"{self.uf} - {self.estado}".strip(' -')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.uf_estado

    class Meta:
        verbose_name = "Estado (ANBIMA)"
        verbose_name_plural = "Estados (ANBIMA)"
        ordering = ['ordem_apresentacao', 'uf']

class FundoAnbima(models.Model):
    cnpj_fundo = models.CharField("CNPJ Fundo", max_length=20, blank=True, null=True)
    nome_fundo = models.CharField("Nome do Fundo", max_length=150, unique=True)
    codigo_anbima = models.CharField("Código ANBIMA", max_length=20, blank=True, null=True)
    ordem_apresentacao = models.IntegerField("Ordem de Apresentação", default=0)

    def __str__(self):
        return self.nome_fundo

    class Meta:
        verbose_name = "Fundo (ANBIMA)"
        verbose_name_plural = "Valores por Fundos (ANBIMA)"
        ordering = ['ordem_apresentacao', 'nome_fundo']

class Unidade(models.Model):
    superintendencia = models.CharField("Superintendência", max_length=150, null=True, blank=True)
    cid_unidade = models.CharField("CID Unidade", max_length=4, unique=True)
    unidade_original = models.CharField("Nome original da unidade", max_length=50, null=True, blank=True)
    unidade = models.CharField("Unidade", max_length=50)
    grupo = models.CharField("Grupo", max_length=3, null=True, blank=True)
    matricula_gg = models.IntegerField("Matrícula Gerente Geral do mês anterior ao da folha", null=True, blank=True)
    matricula_superintendente = models.CharField("Matrícula do Superintendente", max_length=50, null=True, blank=True)
    inativada = models.BooleanField("Inativada", default=False)
    inatualizavel = models.BooleanField("Não atualizar automaticamente", default=False)
    observacoes = models.CharField("Observações", max_length=50, blank=True, null=True)
    atualizada_em = models.DateTimeField("Atualizada em", null=True, blank=True)


    def __str__(self):
        return f"{self.cid_unidade} - {self.unidade}"

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        ordering = ['cid_unidade']

class Ramo(models.Model):
    produto = models.ForeignKey('Produto', on_delete=models.CASCADE, verbose_name="Produto", null=True, blank=True)
    cod_grupo = models.IntegerField("Cód. Grupo SUSEP", blank=True, null=True)
    grupo = models.CharField("Grupo SUSEP", max_length=150, blank=True, null=True)
    cod_ramo = models.IntegerField("Cód. Ramo", unique=True, null=True) 
    ramo = models.CharField("Ramo", max_length=150, unique=True, null=True)
    
    cod_ppo_volume = models.CharField("Cód. PPO Vol.", max_length=150, blank=True, null=True)
    cod_ppo_rateio = models.CharField("Cód. PPO Rat.", max_length=150, blank=True, null=True)
    verba_repasse_folha = models.CharField("Verba Repasse", max_length=150, blank=True, null=True)
    verba_estorno_folha = models.CharField("Verba Estorno", max_length=150, blank=True, null=True)
    
    grupo_e_ramo = models.CharField("Grupo e Ramo", max_length=150, blank=True, unique=True, null=True)
    inativo = models.BooleanField("Inativo", default=False)
    observacoes = models.TextField("Observações", blank=True, null=True)

    def save(self, *args, **kwargs):
        cod_str = str(self.cod_ramo) if self.cod_ramo else ""
        grupo_str = str(self.grupo) if self.grupo else ""
        ramo_str = str(self.ramo) if self.ramo else ""
        partes = [p for p in [cod_str, grupo_str, ramo_str] if p]
        self.grupo_e_ramo = " | ".join(partes)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.grupo_e_ramo if self.grupo_e_ramo else f"{self.cod_ramo} - {self.ramo}"

class MetaMensal(models.Model):
    mes_referencia = models.DateField("Mês/Ano de Referência")
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE, verbose_name="Unidade", null=True, blank=True)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, verbose_name="Produto")
    meta = models.DecimalField("Valor da Meta", max_digits=15, decimal_places=2)
    percentual_fechado = models.DecimalField("% Fechado", max_digits=5, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField("Observações", blank=True, null=True)

    def __str__(self):
        return f"Meta: {self.unidade} - {self.produto}"

    class Meta:
        verbose_name = "Meta Mensal"
        verbose_name_plural = "Metas Mensais"

class Apolice(models.Model):
    TIPO_CATEGORIA = [
        ('BANSEG', 'Banseg'),
        ('OUTRAS', 'Outras Cias'),
    ]
    TIPO_NEGOCIO = [
        ('NOVO', 'Negócio Novo'),
        ('RENOVACAO', 'Renovação'),
        ('ENDOSSO', 'Endosso'),
    ]
    
    categoria = models.CharField("Categoria", max_length=15, choices=TIPO_CATEGORIA, default='BANSEG')
    tipo_negocio = models.CharField("Tipo de Negócio", max_length=15, choices=TIPO_NEGOCIO, default='NOVO')
    agrupamento = models.ForeignKey('Agrupamento', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Agrupamento")

    seg = models.ForeignKey('Seguradora', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Seguradora", related_name='apolices_origem')
    ramo = models.ForeignKey('Ramo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ramo")
    tipo_documento = models.ForeignKey('TipoDocumento', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo de Documento")

    mod = models.CharField("Mod", max_length=20, blank=True, null=True)
    contrato = models.CharField("Contrato/Documento", max_length=50, blank=True, null=True)
    item = models.IntegerField("Item", blank=True, null=True)
    dt_venc = models.DateField("Dt Venc. / Fim Vigência", blank=True, null=True)
    
    nome = models.CharField("Nome", max_length=150)
    sexo = models.CharField("Sexo", max_length=1, blank=True, null=True)
    cid = models.CharField("Unidade/CID", max_length=20, blank=True, null=True)
    telefone = models.CharField("Telefone", max_length=20, blank=True, null=True)
    tipo_pessoa = models.CharField("Tipo Pessoa", max_length=1, blank=True, null=True)
    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=18, blank=True, null=True)
    
    ordem = models.CharField("Ordem", max_length=20, blank=True, null=True)
    usuario = models.CharField("Usuário", max_length=50, blank=True, null=True)
    premio_liquido = models.DecimalField("Prêmio Líquido", max_digits=15, decimal_places=2, null=True, blank=True)
    seguradora_destino = models.ForeignKey('Seguradora', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Seguradora Destino", related_name='apolices_destino')

    def __str__(self):
        return f"{self.contrato} - {self.nome}"

class MotivoNaoVenda(models.Model):
    motivo = models.CharField("Motivo Não Venda", max_length=100, unique=True, null=True)

    def __str__(self):
        return self.motivo

    class Meta:
        verbose_name = "Motivo Não Venda"
        verbose_name_plural = "Motivos Não Venda"
        ordering = ['motivo']

class Indicacao(models.Model):
    ENVIAR_ORCAMENTO = [
        ('Cliente', 'Cliente'),
        ('Indicador', 'Indicador'),
    ]

    ORIGEM_INFORMACAO = [
        ('WhatsApp', 'WhatsApp'),
        ('Planilha da internet', 'Planilha da internet'),
        ('Telefone', 'Telefone'),
        ('E-mail', 'E-mail'),
    ]

    carimbo_data_hora = models.DateTimeField("Carimbo de data/hora", null=True, blank=True)
    email = models.EmailField("Endereço de e-mail", blank=True, null=True)
    email_indicador_outro = models.EmailField("E-mail do indicador (se não for você)", blank=True, null=True)
    matricula_indicador = models.CharField("Matrícula do indicador", max_length=20, blank=True, null=True)
    nome_indicador = models.CharField("Nome completo do indicador", max_length=150, blank=True, null=True)
    cid_agencia = models.CharField("CID da agência", max_length=10, blank=True, null=True)
    telefone_indicador = models.CharField("Telefone ou celular do indicador", max_length=20, blank=True, null=True)
    enviar_orcamento_para = models.CharField("Enviar orçamento para", max_length=15, choices=ENVIAR_ORCAMENTO, blank=True, null=True)
    origem_informacao = models.CharField("Origem da informação", max_length=30, choices=ORIGEM_INFORMACAO, blank=True, null=True)

    nome_cliente = models.CharField("Nome completo do cliente", max_length=150, blank=True, null=True)
    telefone_cliente = models.CharField("Telefone ou celular do cliente", max_length=20, blank=True, null=True)
    cpf_cliente = models.CharField("CPF do cliente", max_length=18, blank=True, null=True)
    email_cliente = models.EmailField("E-mail do cliente", blank=True, null=True)
    produto = models.CharField("Produto", max_length=100, blank=True, null=True)
    dados_veiculo = models.CharField("Dados do veículo (modelo, ano e placa)", max_length=200, blank=True, null=True)
    possui_seguro = models.CharField("Cliente já possui seguro?", max_length=10, blank=True, null=True)
    observacoes = models.TextField("Observações", blank=True, null=True)

    # --- Vínculo com a apólice (mesmos cadastros usados em Produção) ---
    #seguradora = models.ForeignKey('Seguradora', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Seguradora")
    ramo = models.ForeignKey('Ramo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Grupo/Ramo")
    #tipo_documento = models.ForeignKey('TipoDocumento', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo de Documento")
    #numero_contrato = models.CharField("Número do contrato/apólice", max_length=50, blank=True, null=True)
    #numero_endosso = models.CharField("Número do endosso", max_length=50, blank=True, null=True)
    ## chave para nao duplicar a mesma apólice/endosso (mesmo padrão do RegistroProducao)
    # COMENTADO POR HENRIQUE A PEDIDO DE ADRIEL
    #chave_unica = models.CharField("Chave única", max_length=255, null=True, blank=True, db_index=True)

    # nao pode abrir outra ligacao enquanto estiver uma aberta 
    atendimento_por = models.CharField("Em atendimento por", max_length=150, blank=True, null=True)
    atendimento_em = models.DateTimeField("Em atendimento desde", blank=True, null=True)

    # indicacao de uma ligacao somente que e o usuario nivel permitido
    responsavel_demanda = models.ForeignKey('Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='demandas_responsavel', verbose_name="Responsável pela demanda")

    # COMENTADO POR HENRIQUE A PEDIDO DE ADRIEL
    #@staticmethod
    #def montar_chave_unica(seguradora_id, ramo_id, tipo_documento_id, numero_contrato, numero_endosso):
    #    partes = [
    #        str(seguradora_id or ''),
    #        str(ramo_id or ''),
    #        str(tipo_documento_id or ''),
    #        (numero_contrato or '').strip().upper(),
    #        (numero_endosso or '').strip().upper(),
    #    ]
    #    return '&'.join(partes)

    def save(self, *args, **kwargs):
    # COMENTADO POR HENRIQUE A PEDIDO DE ADRIEL
    #    self.chave_unica = Indicacao.montar_chave_unica(
    #        self.seguradora_id, self.ramo_id, self.tipo_documento_id, self.numero_contrato, self.numero_endosso
    #    )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome_cliente} - {self.produto}"

    class Meta:
        verbose_name = "Indicação (Base Novo)"
        verbose_name_plural = "Indicações (Base Novo)"
        ordering = ['-id']


class IndicacaoExcluida(models.Model):
    carimbo_data_hora = models.DateTimeField("Carimbo de data/hora")
    email = models.EmailField("Endereço de e-mail", blank=True, default='')
    excluido_em = models.DateTimeField("Excluído em", auto_now_add=True)
    excluido_por = models.CharField("Excluído por", max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.carimbo_data_hora} - {self.email}"

    class Meta:
        verbose_name = "Indicação Excluída"
        verbose_name_plural = "Indicações Excluídas"
        unique_together = [('carimbo_data_hora', 'email')]


# ligações novas abertas ao mesmo tempo veriam o mesmo "próximo" número.
class SequenciaProtocolo(models.Model):
    prefixo = models.CharField("Prefixo (ano+mês)", max_length=6, unique=True)
    ultimo_numero = models.PositiveIntegerField("Último número usado", default=0)

    def __str__(self):
        return f"{self.prefixo} -> {self.ultimo_numero}"

    class Meta:
        verbose_name = "Sequência de Protocolo"
        verbose_name_plural = "Sequências de Protocolo"


# base novo funcao da ligação
class LigacaoIndicacao(models.Model):
    STATUS_LIGACAO = [
        ('Atendida', 'Atendida'),
        ('Não atendida', 'Não atendida'),
        ('Caixa postal', 'Caixa postal'),
        ('Reagendar', 'Reagendar'),
    ]

    MOTIVO_NAO_VENDA = [
        ('Condições comerciais (preço)', 'Condições comerciais (preço)'),
        ('Condições financeiras', 'Condições financeiras'),
        ('Condições técnicas', 'Condições técnicas'),
        ('Desistiu', 'Desistiu'),
        ('Efetivou com o corretor atual', 'Efetivou com o corretor atual'),
        ('Falta de retorno do cliente/indicador', 'Falta de retorno do cliente/indicador'),
        ('Mal atendimento Seguradora', 'Mal atendimento Seguradora'),
        ('Operação Empréstimo', 'Operação Empréstimo'),
        ('Venda do bem', 'Venda do bem'),
    ]

    indicacao = models.ForeignKey(Indicacao, on_delete=models.CASCADE, related_name='ligacoes')
    protocolo = models.CharField("Protocolo", max_length=20, unique=True, blank=True, null=True)
    data_ligacao = models.DateTimeField("Data/Hora da ligação", null=True, blank=True)
    status = models.CharField("Status da ligação", max_length=20, choices=STATUS_LIGACAO, blank=True, null=True)
    proximo_contato = models.DateTimeField("Próximo contato", null=True, blank=True)
    observacoes = models.TextField("Observações da ligação", blank=True, null=True)

    ramal = models.CharField("Ramal", max_length=10, blank=True, null=True)
    venda_central = models.BooleanField("Venda Central", default=False)
    # Só é preenchido quando a ligação é marcada como "Vendas Central" (regra na view/ficha)
    premio_total = models.DecimalField("Prêmio Total", max_digits=15, decimal_places=2, null=True, blank=True)
    agn = models.BooleanField("Agn", default=False)
    # Lista fixa no Python (igual "Origem da informação"), não depende de tabela/seed no banco.
    motivo_nao_venda = models.CharField("Motivo Não Venda", max_length=50, choices=MOTIVO_NAO_VENDA, blank=True, null=True)
    # Seguradora escolhida no momento da ligação (usada principalmente quando a venda é
    # fechada, para a Emissão). Relacionamento com a tabela de Seguradoras.
    seguradora = models.ForeignKey('Seguradora', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Seguradora")
    # Comissão em % (0 a 65). Preenchida na ligação, junto da venda/seguradora.
    comissao = models.DecimalField("Comissão (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    cadastrado_por = models.CharField("Cadastrado/tratado por", max_length=150, blank=True, null=True)


    @staticmethod
    def gerar_proximo_protocolo():
        prefixo = timezone.now().strftime('%Y%m')
        with transaction.atomic():
            SequenciaProtocolo.objects.get_or_create(prefixo=prefixo)
            SequenciaProtocolo.objects.filter(prefixo=prefixo).update(ultimo_numero=F('ultimo_numero') + 1)
            numero = SequenciaProtocolo.objects.values_list('ultimo_numero', flat=True).get(prefixo=prefixo)
        return f"{prefixo}{numero}"

    def __str__(self):
        return f"Ligação #{self.id} - {self.indicacao_id}"

    class Meta:
        verbose_name = "Ligação (Base Novo)"
        verbose_name_plural = "Ligações (Base Novo)"
        ordering = ['-data_ligacao', '-id']

class PerfilUsuario(models.Model):

    # Relacionamentos
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    colaborador = models.ForeignKey('Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_vinculados')

    # Outros
    cid_coordenadoria = models.CharField('CID Coordenadoria', max_length=100, blank=True, null=True)

    # PERMISSÕES BASE henrique 
    base_form_unidade = models.IntegerField('Base_Form_Unidade', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_colaboradores = models.IntegerField('Base_Form_Colaboradores', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_contratados = models.IntegerField('Base_Form_Contratados', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_seguradoras = models.IntegerField('Base_Form_Seguradoras', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_tiposdocumento = models.IntegerField('Base_Form_TiposDocumento', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_ramos = models.IntegerField('Base_Form_Ramos', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_produtos = models.IntegerField('Base_Form_Produtos', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_agrupamentos = models.IntegerField('Base_Form_Agrupamentos', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_metas = models.IntegerField('Base_Form_Metas', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_tipopessoa = models.IntegerField('Base_Form_TipoPessoa', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_clientes = models.IntegerField('Base_Form_Clientes', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_estados_anbima = models.IntegerField('Base_Form_EstadosAnbima', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_form_fundos_anbima = models.IntegerField('Base_Form_FundosAnbima', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    base_proc_unidade = models.IntegerField('Base_Proc_Unidade', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_proc_colaboradores = models.IntegerField('Base_Proc_Colaboradores', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    base_proc_ramos = models.IntegerField('Base_Proc_Ramos', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    base_rel = models.IntegerField('Base_Rel', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    # PERMISSÕES PRODUÇÃO
    prod_vendas_novo = models.IntegerField('Prod_Vendas_Novo', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_renovacao = models.IntegerField('Prod_Vendas_Renovacao', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_endosso = models.IntegerField('Prod_Vendas_Endosso', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_basenovo = models.IntegerField('Prod_Vendas_BaseNovo', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_baserenovacao = models.IntegerField('Prod_Vendas_BaseRenovacao', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_baseendosso = models.IntegerField('Prod_Vendas_BaseEndosso', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_vendas_emissao = models.IntegerField('Prod_Vendas_Emissao', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    prod_form_vida = models.IntegerField('Prod_Form_Vida', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_bap = models.IntegerField('Prod_Form_BAP', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_prestamista = models.IntegerField('Prod_Form_Prestamista', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_patrimonialedemais = models.IntegerField('Prod_Form_PatrimonialEDemais', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_consorcio = models.IntegerField('Prod_Form_Consorcio', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_odonto = models.IntegerField('Prod_Form_Odonto', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_previdencia = models.IntegerField('Prod_Form_Previdencia', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_banescap = models.IntegerField('Prod_Form_Banescap', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_saude = models.IntegerField('Prod_Form_Saude', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_form_habitacional = models.IntegerField('Prod_Form_Habitacional', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    prod_proc_vida = models.IntegerField('Prod_Proc_Vida', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_bap = models.IntegerField('Prod_Proc_BAP', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_prestamista = models.IntegerField('Prod_Proc_Prestamista', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_patrimonialedemais = models.IntegerField('Prod_Proc_PatrimonialEDemais', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_consorcio = models.IntegerField('Prod_Proc_Consorcio', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_odonto = models.IntegerField('Prod_Proc_Odonto', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_previdencia = models.IntegerField('Prod_Proc_Previdencia', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_banescap = models.IntegerField('Prod_Proc_Banescap', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_saude = models.IntegerField('Prod_Proc_Saude', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_habitacional = models.IntegerField('Prod_Proc_Habitacional', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_basenovo = models.IntegerField('Prod_Proc_Basenovo', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    prod_proc_anbima = models.IntegerField('Prod_Proc_Anbima', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    prod_rel = models.IntegerField('Prod_Rel', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    # PERMISSÕES FINANCEIRO
    fin_form = models.IntegerField('Fin_Form', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    fin_proc_habitacional = models.IntegerField('Fin_Proc_Habitacional', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    fin_rel = models.IntegerField('Fin_Rel', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    # PERMISSÕES ADMINISTRAÇÃO E AUDITORIA
    admin_usuario = models.IntegerField('Admin_Usuario', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    admin_listaestagiarios = models.IntegerField('Admin_ListaEstagiarios', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    admin_feriasestagiarios = models.IntegerField('Admin_FeriasEstagiarios', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    
    aud = models.IntegerField('Aud', default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])

    def __str__(self):
        return f"{self.usuario.username}"

class RegistroProducao(models.Model):
    # --- Controles de Sistema ---
    agrupamento = models.ForeignKey('Agrupamento', on_delete=models.CASCADE, null=True, blank=True)
    fase = models.CharField('Fase', max_length=50, default='IMPORTADOS')
    usuario_cadastro = models.CharField('Usuário Cadastro', max_length=150, null=True, blank=True)
    
    # RELACIONAMENTOS PRINCIPAIS
    seguradora = models.ForeignKey('Seguradora', on_delete=models.SET_NULL, null=True, blank=True)
    unidade = models.ForeignKey('Unidade', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Unidade (CID)")
    
    # --- Identificação do Produto / Negócio ---
    mes_producao = models.CharField('Mês da produção', max_length=50, null=True, blank=True)
    grupo_ramo = models.ForeignKey('Ramo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Grupo/Ramo')
    tipo_documento = models.ForeignKey('TipoDocumento', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Tipo documento')
    documento = models.CharField('Documento', max_length=100, null=True, blank=True)
    endosso = models.CharField('Endosso', max_length=8, null=False, blank=True)
    motivo_endosso = models.CharField('Motivo do endosso', max_length=200, null=True, blank=True)
    # chave para nao duplicar 
    chave_unica = models.CharField('Chave única', max_length=255, null=True, blank=True, db_index=True)
    
    # --- Dados do Cliente ---
    tipo_pessoa = models.CharField('Tipo de pessoa', max_length=50, null=True, blank=True)
    cpf_cnpj = models.CharField('CPF / CNPJ', max_length=50, null=True, blank=True)
    cliente = models.CharField('Cliente', max_length=200, null=True, blank=True)
    nome_social = models.CharField('Nome social', max_length=200, null=True, blank=True)
    celular = models.CharField('Celular', max_length=50, null=True, blank=True)
    telefone = models.CharField('Telefone', max_length=50, null=True, blank=True)
    email = models.CharField('E-mail', max_length=150, null=True, blank=True)
    
    # --- Dados da Agência (Preenchidos na hora da importação) ---
    grupo = models.CharField('Grupo', max_length=100, null=True, blank=True)
    superintendencia = models.CharField('Superintendência', max_length=100, null=True, blank=True)
    nome_unidade = models.CharField('Nome da Unidade', max_length=100, null=True, blank=True)
    gerente_agencia = models.CharField('Matrícula do Gerente', max_length=150, null=True, blank=True)
    superintendente = models.CharField('Matrícula do Superintendente', max_length=150, null=True, blank=True)
    colaborador = models.CharField('Matrícula do Colaborador', max_length=150, null=True, blank=True)
    nome_colaborador = models.CharField('Nome do Colaborador', max_length=150, null=True, blank=True)
    
    # --- Vigência e Valores ---
    qtd_parcelas = models.IntegerField('Qtd. parcelas', null=True, blank=True)
    inicio_vigencia = models.DateField('Início de vigência', null=True, blank=True)
    fim_vigencia = models.DateField('Fim de vigência', null=True, blank=True)
    
    premio_bruto = models.FloatField('Prêmio bruto', null=True, blank=True)
    premio_liquido = models.FloatField('Prêmio Líquido', null=True, blank=True)
    perc_comissao = models.FloatField('% de comissão', null=True, blank=True)
    
    # --- Campos Auxiliares ---
    realizado = models.CharField('Realizado', max_length=100, null=True, blank=True)
    renovacao_propria = models.BooleanField('Renovação Própria', default=False, null=True, blank=True)
    observacoes = models.TextField('Observações', null=True, blank=True)
    
    # --- Campos de legados (do seu outro importador no views.py) ---
    agencia = models.CharField(max_length=100, null=True, blank=True)
    contrato = models.CharField(max_length=100, null=True, blank=True)
    segurado = models.CharField(max_length=200, null=True, blank=True)
    vlr_seguro = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = 'Registro de Produção'
        verbose_name_plural = 'Registros de Produção'


    # ajuda a buscar rapido a coluna , nao duplicar 
    @staticmethod
    def montar_chave_unica(seguradora_id, grupo_ramo_id, tipo_documento_id, documento, endosso):
        partes = [
            str(seguradora_id or ''),
            str(grupo_ramo_id or ''),
            str(tipo_documento_id or ''),
            (documento or '').strip().upper(),
            (endosso or '').strip().upper(),
        ]
        return '&'.join(partes)
    # salva o nao duplicar 
    def save(self, *args, **kwargs):
        self.chave_unica = RegistroProducao.montar_chave_unica(
            self.seguradora_id, self.grupo_ramo_id, self.tipo_documento_id, self.documento, self.endosso
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente or 'Sem Cliente'} - {self.documento or 'S/ Doc'}"
    
class EndossoAdicional(models.Model):
    registro_pai = models.ForeignKey(RegistroProducao, on_delete=models.CASCADE, related_name='endossos_extras')
    mes_producao = models.CharField('Mês da produção', max_length=20, null=True, blank=True)
    endosso = models.CharField('Endosso', max_length=8, null=False, blank=True)
    motivo_endosso = models.CharField('Motivo do endosso', max_length=150, null=True, blank=True)
    inicio_vigencia = models.DateField('Início de vigência', null=True, blank=True)
    fim_vigencia = models.DateField('Fim de vigência', null=True, blank=True)
    qtd_parcelas = models.IntegerField('Quantidade de parcelas', null=True, blank=True)
    renovacao_propria = models.BooleanField('Renovação Própria', default=False, null=True, blank=True)
    premio_bruto = models.DecimalField('Prêmio bruto', max_digits=15, decimal_places=2, null=True, blank=True)
    premio_liquido = models.DecimalField('Prêmio líquido', max_digits=15, decimal_places=2, null=True, blank=True)
    perc_comissao = models.DecimalField('% de comissão', max_digits=5, decimal_places=2, null=True, blank=True)
    realizado = models.CharField('Realizado', max_length=100, null=True, blank=True)
    unidade = models.CharField('Unidade', max_length=100, null=True, blank=True)
    superintendencia = models.CharField('Superintendência', max_length=100, null=True, blank=True)
    nome_unidade = models.CharField('Nome da Unidade', max_length=100, null=True, blank=True)
    grupo = models.CharField('Grupo', max_length=100, null=True, blank=True)
    colaborador = models.CharField('Colaborador', max_length=150, null=True , blank=True)
    nome_colaborador = models.CharField('Nome do Colaborador', max_length=150, null=True, blank=True)
    gerente_agencia = models.CharField('Gerente da agência', max_length=150, null=True, blank=True)
    superintendente = models.CharField('Superintendente', max_length=150, null=True, blank=True)
    data_cadastro = models.DateTimeField('Adicionado em', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['registro_pai', 'endosso'],
                name='unique_registro_pai_endosso'
            )
        ]

    def __str__(self):
        return f"Endosso Extra: {self.endosso} (Ref: {self.registro_pai.cliente})"

class CompatibilidadeSeguradora(models.Model):
    nome_planilha = models.CharField(max_length=150, unique=True)
    seguradora_base = models.ForeignKey('Seguradora', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.nome_planilha} -> {self.seguradora_base.seguradora}"
    
    def _str_(self):
        return f"{self.nome_planilha2} -> {self.seguradora_base.seguradora2}"
    
'''vou parametrizar a coluna que adriel pediu ligacao com a views'''
class ParametrizacaoHabitacional(models.Model):
    campo_sistema = models.CharField(max_length=100, unique=True)
    coluna_excel = models.CharField(max_length=150, blank=True, null=True)
    valor_fixo = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return self.campo_sistema

class ParametrizacaoBaseNovo(models.Model):
    campo_sistema = models.CharField(max_length=100, unique=True)
    coluna_excel = models.CharField(max_length=150, blank=True, null=True)
    valor_fixo = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return self.campo_sistema


"""                             HENRIQUE                                                                    """
from datetime import timedelta
from django.core.exceptions import ValidationError

class FeriasEstagiario(models.Model):
    colaborador = models.ForeignKey(
        'Colaborador', 
        on_delete=models.CASCADE, 
        related_name='historico_ferias',
        verbose_name="Estagiário"
    )

    inicio_ferias = models.DateField("Início das Férias")
    quantidade_dias = models.IntegerField("Quantidade de Dias")
    fim_ferias = models.DateField("Fim das Férias", blank=True, null=True)

    def clean(self):
        if self.quantidade_dias < 7:
            raise ValidationError('A quantidade mínima de dias de férias é de 7 dias.')

    def save(self, *args, **kwargs):
        self.full_clean()
        self.fim_ferias = self.inicio_ferias + timedelta(days=self.quantidade_dias - 1)
        super().save(*args, **kwargs)

    def __str__(self):
        nome_exibicao = self.colaborador.nome_social if self.colaborador.nome_social else self.colaborador.colaborador
        return f"Férias: {nome_exibicao} | {self.inicio_ferias} a {self.fim_ferias}"
    


class AuditoriaExportacao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    acao = models.CharField(max_length=255)
    detalhe = models.CharField(max_length=255)
    
    data_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} exportou {self.nome_arquivo} em {self.data_hora}"

class FinanceiroHabitacional(models.Model):

    registro_producao = models.ForeignKey('RegistroProducao', on_delete=models.CASCADE, verbose_name="Registro de Produção (Endosso)",related_name="financeiro_habitacional")
    matricula_colaborador = models.CharField("Matrícula do Colaborador", max_length=150, null=True, blank=True)
    data_processamento = models.CharField("Mês/Ano de Processamento", max_length=7, null=True, blank=True)
    valor = models.DecimalField("Valor", max_digits=15, decimal_places=2, default=100.00)

    def __str__(self):
        return f"{self.registro_producao.chave_unica} - {self.data_processamento or 'Não Processado'}"
