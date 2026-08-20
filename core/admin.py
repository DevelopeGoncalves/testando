from django.contrib import admin
from .models import Agrupamento, Produto, Unidade, Ramo, MetaMensal, MotivoNaoVenda, EstadoAnbima, FundoAnbima
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import PerfilUsuario


@admin.register(Agrupamento)
class AgrupamentoAdmin(admin.ModelAdmin):
    # Atualizado com as colunas reais do banco de dados
    list_display = ('agrupamento', 'inativo', 'ordem_apresentacao')
    list_filter = ('inativo',)
    search_fields = ('agrupamento',)

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'agrupamento', 'divulgacao_ativa')
    list_filter = ('agrupamento', 'divulgacao_ativa')
    search_fields = ('produto',)

@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ('cid_unidade', 'unidade', 'superintendencia', 'grupo', 'inativada')
    list_filter = ('superintendencia', 'grupo', 'inativada')
    search_fields = ('cid_unidade', 'unidade')

@admin.register(Ramo)
class RamoAdmin(admin.ModelAdmin):
    list_display = ('cod_ramo', 'ramo', 'grupo', 'produto', 'inativo') 
    list_filter = ('produto', 'inativo')
    search_fields = ('ramo', 'grupo')

@admin.register(EstadoAnbima)
class EstadoAnbimaAdmin(admin.ModelAdmin):
    list_display = ('uf', 'estado', 'uf_estado', 'ordem_apresentacao')
    search_fields = ('uf', 'estado')

@admin.register(FundoAnbima)
class FundoAnbimaAdmin(admin.ModelAdmin):
    list_display = ('nome_fundo', 'cnpj_fundo', 'codigo_anbima', 'ordem_apresentacao')
    search_fields = ('nome_fundo', 'cnpj_fundo', 'codigo_anbima')

@admin.register(MotivoNaoVenda)
class MotivoNaoVendaAdmin(admin.ModelAdmin):
    list_display = ('motivo',)
    search_fields = ('motivo',)

@admin.register(MetaMensal)
class MetaMensalAdmin(admin.ModelAdmin):

    list_display = ('mes_referencia', 'unidade', 'produto', 'meta', 'percentual_fechado')
    list_filter = ('mes_referencia', 'produto')

    date_hierarchy = 'mes_referencia' 
    search_fields = ('unidade__unidade', 'produto__produto')
    
    # --- GERENCIAMENTO DE USUÁRIOS E ACESSOS ---
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Nível de Acesso e Permissões (Marque o que o usuário pode ver)'

class CustomUserAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline, )

# Substitui a tela padrão do Django pela nossa tela turbinada
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

"""                             HENRIQUE                                                                    """