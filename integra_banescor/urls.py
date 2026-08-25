from django.contrib import admin
from django.urls import path
from core import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # LIMPA A PAGINA ESPECIFICA
    path('deletar-tudo/<str:tipo>/', views.deletar_tudo, name='deletar_tudo'),
    
    # 1. ROTA DA RAIZ
    path('', views.home, name='home'),
    
    path('importar/unidades/', views.importar_unidades, name='importar_unidades'),

    # 2. ROTA DO PAINEL DE CARDS
    path('base/formularios/', views.base_formularios, name='base_formularios'),
    
    # 3. ROTA DO PAINEL DE COLABORADORES
    path('importar/colaboradores/', views.importar_colaboradores, name='importar_colaboradores'),
    
    # 4. ROTA DO PAINEL DE RAMOS
    path('importar/ramos/', views.importar_ramos, name='importar_ramos'),
    

    # 5. ROTA DO PAINEL DE LISTAGENS
    path('agrupamentos/', views.lista_agrupamentos, name='lista_agrupamentos'),
    
    # 6. ROTA DO PAINEL DE UNIDADES
    path('unidades/', views.lista_unidades, name='lista_unidades'), 
    
    path('produtos/', views.lista_produtos, name='lista_produtos'),
    path('ramos/', views.lista_ramos, name='lista_ramos'),
    path('metas/', views.lista_metas, name='lista_metas'),
    
    # 6.1 AÇÕES
    path('excluir-massa/', views.excluir_em_massa, name='excluir_em_massa'),
    
    # 6.2 EXTRAS
    path('base/processamentos/', views.base_processamentos, name='base_processamentos'),
    path('base/relatorios/', views.base_relatorios, name='base_relatorios'),
    
    path('colaboradores/', views.lista_colaboradores, name='lista_colaboradores'),
    
    path('contratados/', views.lista_contratados, name='lista_contratados'),
    
    path('seguradoras/', views.lista_seguradoras, name='lista_seguradoras'),
    
    path('tipos-documentos/', views.lista_tiposdoc, name='lista_tiposdoc'),

    path('base/formularios/estados-anbima/', views.lista_estados_anbima, name='lista_estados_anbima'),
    path('base/formularios/fundos-anbima/', views.lista_fundos_anbima, name='lista_fundos_anbima'),

    path('producao/processamentos/habitacional/', views.producao_habitacional_import, name='producao_habitacional_import'),
    path('producao/processamentos/anbima/', views.producao_anbima_import, name='producao_anbima_import'),
    path('producao/processamentos/odonto/', views.producao_odonto_import, name='producao_odonto_import'),
    path('producao/processamentos/base-novo/', views.producao_base_novo_import, name='producao_base_novo_import'),

    
    path('producao/formularios/<int:agrupamento_id>/<str:fase>/', views.producao_lista_fase, name='producao_lista_fase'),
    
    # 7. ROTA DO PAINEL DE VOLTAR TELA LOGIN
    path('logout/', views.sair_do_sistema, name='logout'),
    
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    
    # 7.1 TELA LOGIN 
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
       
    # 9. ROTA DO PAINEL DE PRODUÇÃO
    path('producao/formularios/', views.producao_formularios, name='producao_formularios'),
    path('producao/formularios/painel/<int:agrupamento_id>/', views.producao_formularios_painel, name='producao_formularios_painel'),
    
    # 9.1 Esta rota abre a tela com os Cards (index)
    path('producao/vendas/', views.producao_vendas, name='producao_vendas'),
    
    path('base/formularios/tipo-pessoa/', views.tipo_pessoa_lista, name='tipo_pessoa_lista'),

    # 10.1 Base Novo (Indicação de Seguridade) - card de Produção / Vendas
    path('producao/vendas/base-novo/', views.lista_base_novo, name='lista_base_novo'),
    # Emissão: mesma base, mas só com as vendas já fechadas (Central/Agência)
    path('producao/vendas/emissao/', views.vendas_emissao, name='vendas_emissao'),
    path('producao/vendas/base-novo/gerar-protocolo/', views.gerar_protocolo_ligacao, name='gerar_protocolo_ligacao'),
    path('producao/vendas/base-novo/agora/', views.agora_servidor_ligacao, name='agora_servidor_ligacao'),
    # Trava de atendimento ("em ligação") - marcar/encerrar e listar os ativos (polling)
    path('producao/vendas/atendimento/<int:id>/iniciar/', views.marcar_atendimento, name='marcar_atendimento'),
    path('producao/vendas/atendimento/<int:id>/encerrar/', views.encerrar_atendimento, name='encerrar_atendimento'),
    path('producao/vendas/atendimentos-ativos/', views.atendimentos_ativos, name='atendimentos_ativos'),
    # alex: Gestor indica o responsável pela demanda de um registro
    path('producao/vendas/responsavel-demanda/<int:id>/', views.definir_responsavel_demanda, name='definir_responsavel_demanda'),
    # alex: indicar o responsável para vários registros de uma vez (card Novo)
    path('producao/vendas/responsavel-demanda-massa/', views.definir_responsavel_massa, name='definir_responsavel_massa'),


    # 10. Rotas para cada Card específico de vendas
    path('producao/vendas/endosso/', views.vendas_endosso, name='vendas_endosso'),
    path('producao/vendas/renovacao/', views.vendas_renovacao, name='vendas_renovacao'),

    # 10.2 Cards "Novo"/"Renovação"/"Endosso" (ainda em desenvolvimento, ligados aos poucos à respectiva "Base X")
    path('producao/vendas/novo-negocio/', views.vendas_novo_negocio, name='vendas_novo_negocio'),
    path('producao/vendas/nova-renovacao/', views.vendas_nova_renovacao, name='vendas_nova_renovacao'),
    path('producao/vendas/novo-endosso/', views.vendas_novo_endosso, name='vendas_novo_endosso'),
    
    path('producao/processamentos/', views.producao_processamentos, name='producao_processamentos'),
    path('producao/relatorios/', views.producao_relatorios, name='producao_relatorios'),

#                                               Henrique
    path('administracao/estagiarios/estagiarios', views.estagiarios, name='estagiarios'),
    path('administracao/estagiarios/lista_estagiarios', views.lista_estagiarios, name='lista_estagiarios'),
    path('administracao/estagiarios/ferias_estagiarios', views.ferias_estagiarios, name='ferias_estagiarios'),

    path('auditoria/', views.lista_auditoria, name='auditoria'),
    path('auditoria/exportacao/', views.registrar_auditoria, name='auditoria_exportacao'),

    path('producao/relatorios', views.producao_relatorios, name='producao_relatorios'),
    
    path('financeiro/processamentos', views.financeiro_processamentos, name='financeiro_processamentos'),
    path('financeiro/formularios', views.financeiro_formularios, name='financeiro_formularios'),
    path('financeiro/relatorios', views.financeiro_relatorios, name='financeiro_relatorios'),

    path('administracao/usuarios/', views.listar_usuarios, name='listar_usuarios'),
    path('administracao/usuarios/novo/', views.form_usuario, name='form_usuario_criar'),
    path('administracao/usuarios/editar/<int:id>/', views.form_usuario, name='form_usuario_editar'),
    path('administracao/usuarios/excluir/', views.excluir_usuarios, name='excluir_usuarios'),

    path('financeiro/processamentos/habitacional', views.financeiro_habitacional, name='financeiro_habitacional'),
    path('financeiro/habitacional/exportar-txt/', views.exportar_txt_habitacional, name='exportar_txt_habitacional'),
    path('financeiro/habitacional/processar/', views.processar_mensal_habitacional, name='processar_mensal_habitacional'),

    path('ping-online/', views.ping_online, name='ping_online'),
    path('desconectar_usuarios/', views.desconectar_usuarios, name='desconectar_usuarios'),
]

