from django import forms
from .models import Unidade, Produto, MetaMensal, Agrupamento, Ramo, Colaborador, Contratado, Seguradora, TipoDocumento, Cliente, Apolice, Indicacao


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'


# --- 2. AGRUPAMENTO (NOVO) ---
class AgrupamentoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Agrupamento
        fields = [
            'agrupamento',
            'inativo',
            'ordem_apresentacao',
            'observacoes'
        ]
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    # NOVA TRAVA INTELIGENTE CONTRA DUPLICIDADE
    def clean_agrupamento(self):
        nome = self.cleaned_data.get('agrupamento')
        # Verifica se já existe outro igual (ignorando maiúsculas e minúsculas)
        if Agrupamento.objects.filter(agrupamento__iexact=nome).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Já existe um Agrupamento com este nome.")
        return nome

# --- UNIDADES (Antiga Agência) ---
class UnidadeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Unidade
        fields = [
            'superintendencia',
            'cid_unidade',
            'unidade_original',
            'unidade',
            'grupo',
            'matricula_gg',
            'matricula_superintendente',
            'inativada',
            'inatualizavel',
            'observacoes'
        ]
        labels = {
            'superintendencia': 'Superintendência',
            'cid_unidade': 'CID da Unidade',
            'unidade_original': 'Unidade original',
            'unidade': 'Unidade',
            'grupo': 'Grupo',
            'matricula_gg': 'Matrícula do Gerente da agência',
            'matricula_superintendente': 'Matrícula do superintendente regional',
            'inativada': 'Inativada',
            'inatualizavel': 'Não atualizar automaticamente',
            'observacoes': 'Observações'
        }
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_cid_unidade(self):
        cid = self.cleaned_data.get('cid_unidade')
        if cid:
            # Formata para ter 4 dígitos, completando com zeros à esquerda
            return str(cid).strip().zfill(4)
        return cid
        
# --- 4. PRODUTO ---
class ProdutoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'agrupamento', 
            'produto', 
            'inativo',
            'divulgacao_ativa', 
            'prioridade_divulgacao', 
            'mes_producao_em_aberto', 
            'mes_folha_pagamento_em_aberto',
            'observacoes'
        ]
        labels = {
            'inativo': 'Inativo',
            'divulgacao_ativa': 'Divulgação Ativa',
            'mes_producao_em_aberto': 'Mês Produção em Aberto',
            'mes_folha_pagamento_em_aberto': 'Mês Folha Pgto em Aberto',
        }
        widgets = {
            'mes_producao_em_aberto': forms.DateInput(attrs={'type': 'date'}),
            'mes_folha_pagamento_em_aberto': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

# --- 5. RAMO ---
class RamoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Ramo
        fields = [
            'produto',
            'cod_grupo',
            'grupo',
            'cod_ramo',
            'ramo',
            'cod_ppo_volume',
            'cod_ppo_rateio',
            'verba_repasse_folha',
            'verba_estorno_folha',
            'grupo_e_ramo',
            'inativo',
            'observacoes'
        ]
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 3}),
            'grupo_e_ramo': forms.TextInput(attrs={'readonly': 'readonly', 'placeholder': 'Gerado automaticamente ao salvar'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'produto' in self.fields:
            self.fields['produto'].queryset = Produto.objects.filter(inativo=False).order_by('produto')

    def clean_cod_ramo(self):
        cod = self.cleaned_data.get('cod_ramo')
        if cod is not None:
            if Ramo.objects.filter(cod_ramo=cod).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este Cód. Ramo já está cadastrado no sistema.")
        return cod

    def clean_ramo(self):
        nome = self.cleaned_data.get('ramo')
        if nome:
            if Ramo.objects.filter(ramo__iexact=nome).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este Nome de Ramo já está cadastrado.")
        return nome

# --- 6. META MENSAL ---
class MetaMensalForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = MetaMensal
        fields = '__all__'
        widgets = {
            'mes_referencia': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }
        

class ColaboradorForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = '__all__'
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 3}), 
        }

class ContratadoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Contratado
        fields = [
            'tipo_pessoa', 'cpf_cnpj', 'contratado', 'matricula', 'numero_dependente',
            'celular', 'telefone', 'email', 'banco', 'unidade', 'conta_corrente',
            'celebrado_em', 'observacoes'
        ]
        widgets = {
            'celebrado_em': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.TextInput(attrs={'placeholder': 'Máximo de 50 caracteres...'}),
            'cpf_cnpj': forms.TextInput(attrs={'placeholder': 'Apenas números...'}),
        }

    def clean_cpf_cnpj(self):
        doc = self.cleaned_data.get('cpf_cnpj')
        if doc:
            if Contratado.objects.filter(cpf_cnpj=doc).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este CPF/CNPJ já está cadastrado para outro Contratado.")
        return doc

class SeguradoraForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Seguradora
        fields = ['cod_seguradora', 'seguradora', 'cnpj', 'observacoes']
        widgets = {
            'observacoes': forms.TextInput(attrs={'placeholder': 'Máximo de 80 caracteres...'}),
        }

    def clean_cod_seguradora(self):
        cod = self.cleaned_data.get('cod_seguradora')
        if cod:
            if Seguradora.objects.filter(cod_seguradora__iexact=cod).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este Cód. Seguradora já está cadastrado.")
        return cod

    def clean_seguradora(self):
        nome = self.cleaned_data.get('seguradora')
        if nome:
            if Seguradora.objects.filter(seguradora__iexact=nome).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Esta Seguradora já está cadastrada.")
        return nome

class TipoDocumentoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = ['tipo_documento', 'observacoes']
        widgets = {
            #só 50 caracteres, uma linha de texto simples é melhor
            'observacoes': forms.TextInput(attrs={'placeholder': 'Máximo de 50 caracteres...'}),
        }
    # TRAVA  CONTRA DUPLICIDADE
    def clean_tipo_documento(self):
        nome = self.cleaned_data.get('tipo_documento')
        if nome:
            if TipoDocumento.objects.filter(tipo_documento__iexact=nome).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este Tipo de Documento já está cadastrado no sistema.")
        return nome

class ClienteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'tipo_pessoa', 
            'cpf_cnpj', 
            'nome', 
            'nome_social', 
            'celular', 
            'telefone', 
            'email', 
            'observacoes'
        ]
        widgets = {
            'observacoes': forms.TextInput(attrs={'placeholder': 'Máximo de 80 caracteres...'}),
            'cpf_cnpj': forms.TextInput(attrs={'placeholder': 'Apenas números...'}),
        }

    # Evita CPFs/CNPJs duplicados no cadastro manual
    def clean_cpf_cnpj(self):
        doc = self.cleaned_data.get('cpf_cnpj')
        if doc:
            if Cliente.objects.filter(cpf_cnpj=doc).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Este CPF/CNPJ já está cadastrado no sistema.")
        return doc     
    
class ApoliceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Apolice
        # excluir esses dois porque o sistema vai preencher automaticamente por trás dos panos
        exclude = ['categoria', 'tipo_negocio']
        widgets = {
            'dt_venc': forms.DateInput(attrs={'type': 'date'}),
        }
        
        

# --- BASE NOVO (Indicação de Seguridade) ---
class IndicacaoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Indicacao
        fields = [
            'carimbo_data_hora',
            'email',
            'email_indicador_outro',
            'matricula_indicador',
            'nome_indicador',
            'cid_agencia',
            'telefone_indicador',
            'enviar_orcamento_para',
            'origem_informacao',
            'nome_cliente',
            'telefone_cliente',
            'cpf_cliente',
            'email_cliente',
            'produto',
            'dados_veiculo',
            'possui_seguro',
            'seguradora',
            'ramo',
            'tipo_documento',
            'numero_contrato',
            'numero_endosso',
            'observacoes',
        ]
        widgets = {
            # alex: "Data/hora do cadastro" é gerada automaticamente ao criar um novo
            # registro e fica INATIVA (readonly). Continua sendo enviada no salvamento.
            'carimbo_data_hora': forms.DateTimeInput(attrs={
                'type': 'datetime-local', 'readonly': 'readonly', 'tabindex': '-1',
                'style': 'pointer-events:none; background-color:#f3f4f6;',
            }),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, ficha_somente_leitura=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seguradora'].queryset = Seguradora.objects.all().order_by('seguradora')
        self.fields['ramo'].queryset = Ramo.objects.all().order_by('grupo_e_ramo')
        self.fields['ramo'].label_from_instance = lambda obj: obj.grupo_e_ramo or f"{obj.grupo} - {obj.ramo}"
        self.fields['tipo_documento'].queryset = TipoDocumento.objects.all().order_by('tipo_documento')
        for campo in ('seguradora', 'ramo', 'tipo_documento'):
            self.fields[campo].empty_label = '-- Selecione --'

        if ficha_somente_leitura:
            for nome, campo in self.fields.items():
                if nome != 'observacoes':
                    campo.disabled = True
        else:
            # Nomes válidos (do formulário):
            #   'ramo' ,
            
            # obrigatorio
            CAMPOS_OBRIGATORIOS = [
                'ramo',           # ramo = (Grupo/Ramo), 'seguradora', 'tipo_documento'
                'nome_cliente',   # Nome (Dados do Cliente)
                'telefone_cliente',
              
                'cpf_cliente',    # CPF (Dados do Cliente)
            #   'numero_contrato', 'numero_endosso', 'possui_seguro' (Renovação),
            #   'carimbo_data_hora', 'nome_cliente', 'cpf_cliente',
            #   'telefone_cliente', 'email_cliente', 'produto', 'dados_veiculo',
            #   'matricula_indicador', 'nome_indicador', 'cid_agencia',
            #   'telefone_indicador', 'email', 'enviar_orcamento_para',
            #   'origem_informacao', 'observacoes'
                
                # adicione aqui os outros campos que quiser obrigar, ex.:
                # 'seguradora',
            ]
            for nome in CAMPOS_OBRIGATORIOS:
                if nome in self.fields:
                    self.fields[nome].required = True

    def clean(self):
        cleaned_data = super().clean()
        chave = Indicacao.montar_chave_unica(
            cleaned_data.get('seguradora').id if cleaned_data.get('seguradora') else None,
            cleaned_data.get('ramo').id if cleaned_data.get('ramo') else None,
            cleaned_data.get('tipo_documento').id if cleaned_data.get('tipo_documento') else None,
            cleaned_data.get('numero_contrato'),
            cleaned_data.get('numero_endosso'),
        )
        # só bloqueia duplicidade quando a chave tem algo além dos separadores
        if chave.strip('&') and Indicacao.objects.filter(chave_unica=chave).exclude(id=self.instance.id).exists():
            raise forms.ValidationError(
                "Já existe uma indicação cadastrada com essa Seguradora, Ramo, Tipo de Documento, "
                "Número do Contrato e Endosso. Verifique se não é uma ligação duplicada."
            )
        return cleaned_data


"""                             HENRIQUE                                                                    """

def criar_campo_permissao(label):
    return forms.IntegerField(label=label,min_value=0,max_value=3,required=False,initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'max': '3'}))

class NovoUsuarioForm(BootstrapMixin, forms.Form):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super().__init__(*args, **kwargs)
                          
    matricula = forms.CharField(
        label="Matrícula do Colaborador", 
        max_length=50,
        widget=forms.TextInput(attrs={
            'id': 'input-matricula',
            'autocomplete': 'off',
            'placeholder': 'Buscar...'
        })
    )
    login = forms.CharField(label="Usuário", max_length=150)
    
    password = forms.CharField(
        label="Senha", 
        widget=forms.PasswordInput, 
        required=False
    )
    
    confirmar_senha = forms.CharField(
        label="Confirmar Senha", 
        widget=forms.PasswordInput, 
        required=False
    )
    
    is_active = forms.BooleanField(
        label="Usuário ativo", 
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # --- BASE ---
    base_form_unidade = criar_campo_permissao("↳ Form - Unidade")
    base_form_colaboradores = criar_campo_permissao("↳ Form - Colaboradores")
    base_form_contratados = criar_campo_permissao("↳ Form - Contratados")
    base_form_seguradoras = criar_campo_permissao("↳ Form - Seguradoras")
    base_form_tiposdocumento = criar_campo_permissao("↳ Form - Tipos Documento")
    base_form_ramos = criar_campo_permissao("↳ Form - Ramos")
    base_form_produtos = criar_campo_permissao("↳ Form - Produtos")
    base_form_agrupamentos = criar_campo_permissao("↳ Form - Agrupamentos")
    base_form_metas = criar_campo_permissao("↳ Form - Metas")
    base_form_tipopessoa = criar_campo_permissao("↳ Form - Tipo Pessoa")
    base_form_clientes = criar_campo_permissao("↳ Form - Clientes")

    base_proc_unidade = criar_campo_permissao("↳ Proc - Unidade")
    base_proc_colaboradores = criar_campo_permissao("↳ Proc - Colaboradores")
    base_proc_ramos = criar_campo_permissao("↳ Proc - Ramos")

    base_rel = criar_campo_permissao("↳ Relatórios Base")

    # --- PRODUÇÃO  henrique ---
    prod_vendas_novo = criar_campo_permissao("↳ Vendas - Novo")
    prod_vendas_renovacao = criar_campo_permissao("↳ Vendas - Renovação")
    prod_vendas_endosso = criar_campo_permissao("↳ Vendas - Endosso")
    prod_vendas_basenovo = criar_campo_permissao("↳ Vendas - Base Novo")
    prod_vendas_baserenovacao = criar_campo_permissao("↳ Vendas - Base Renovação")
    prod_vendas_baseendosso = criar_campo_permissao("↳ Vendas - Base Endosso")
    prod_vendas_emissao = criar_campo_permissao("↳ Vendas - Emissao")

    prod_form_vida = criar_campo_permissao("↳ Form - Vida")
    prod_form_bap = criar_campo_permissao("↳ Form - BAP")
    prod_form_prestamista = criar_campo_permissao("↳ Form - Prestamista")
    prod_form_patrimonialedemais = criar_campo_permissao("↳ Form - Patrimonial e Demais")
    prod_form_consorcio = criar_campo_permissao("↳ Form - Consórcio")
    prod_form_odonto = criar_campo_permissao("↳ Form - Odonto")
    prod_form_previdencia = criar_campo_permissao("↳ Form - Previdência")
    prod_form_banescap = criar_campo_permissao("↳ Form - Banescap")
    prod_form_saude = criar_campo_permissao("↳ Form - Saúde")
    prod_form_habitacional = criar_campo_permissao("↳ Form - Habitacional")

    prod_proc_vida = criar_campo_permissao("↳ Proc - Vida")
    prod_proc_bap = criar_campo_permissao("↳ Proc - BAP")
    prod_proc_prestamista = criar_campo_permissao("↳ Proc - Prestamista")
    prod_proc_patrimonialedemais = criar_campo_permissao("↳ Proc - Patrimonial e Demais")
    prod_proc_consorcio = criar_campo_permissao("↳ Proc - Consórcio")
    prod_proc_odonto = criar_campo_permissao("↳ Proc - Odonto")
    prod_proc_previdencia = criar_campo_permissao("↳ Proc - Previdência")
    prod_proc_banescap = criar_campo_permissao("↳ Proc - Banescap")
    prod_proc_saude = criar_campo_permissao("↳ Proc - Saúde")
    prod_proc_habitacional = criar_campo_permissao("↳ Proc - Habitacional")
    prod_proc_basenovo = criar_campo_permissao("↳ Proc - Base Novo")

    prod_rel = criar_campo_permissao("↳ Relatórios Prod")

    # --- FINANCEIRO ---
    fin_form = criar_campo_permissao("↳ Form - Financeiro")
    fin_proc_habitacional = criar_campo_permissao("↳ Proc - Habitacional")
    fin_rel = criar_campo_permissao("↳ Relatórios Fin")

    # --- ADMINISTRAÇÃO ---
    admin_usuario = criar_campo_permissao("↳ Admin - Usuário")
    admin_listaestagiarios = criar_campo_permissao("↳ Admin - Lista Estagiários")
    admin_feriasestagiarios = criar_campo_permissao("↳ Admin - Férias Estagiários")

    # --- AUDITORIA ---
    aud = criar_campo_permissao("Acessar Aba Auditoria")

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("password")
        confirmar = cleaned_data.get("confirmar_senha")

        if senha and senha != confirmar:
            self.add_error('confirmar_senha', "As senhas não coincidem. Tente novamente.")
            
        # Como usamos required=False nos campos numéricos, garantimos que campos vazios se tornem 0
        for campo in cleaned_data:
            if campo not in ['matricula', 'login', 'password', 'confirmar_senha', 'is_active']:
                if cleaned_data.get(campo) is None:
                    cleaned_data[campo] = 0

        return cleaned_data

