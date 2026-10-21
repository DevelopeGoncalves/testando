# Cadastro padrão das tabelas "Status das emissões" e "Retorno ao cliente das emissões"
# (Base > Formulários). É o que existia fixo no código antes dessas tabelas:
#
#   Status               Retorno ao cliente
#   Aguardando emissão   (sem a pergunta)
#   Pendência            (sem a pergunta)
#   Recusada             Não / Sim
#   Emitida              Não / Apólice/endosso enviada ao cliente
#   Cancelado            Não / Sim
#
# Depois de criado, o usuário edita pelos cards (nomes, inativo, observações, novos retornos).
# A "regra" de cada status é uma chave interna (não aparece na tela) que liga o status às
# regras do sistema e continua valendo mesmo se o nome do status for trocado.
from .models import AcompanhamentoEmissao, RetornoClienteEmissao, StatusEmissao

STATUS_PADRAO = [
    ('Aguardando emissão', StatusEmissao.REGRA_AGUARDANDO),
    ('Pendência', StatusEmissao.REGRA_PENDENCIA),
    ('Recusada', StatusEmissao.REGRA_RECUSADA),
    ('Emitida', StatusEmissao.REGRA_EMITIDA),
    ('Cancelado', StatusEmissao.REGRA_CANCELADO),
]

# regra -> [retorno que NÃO avisou o cliente, retorno que avisou o cliente]
RETORNOS_PADRAO = {
    StatusEmissao.REGRA_RECUSADA: ['Não', 'Sim'],
    StatusEmissao.REGRA_EMITIDA: ['Não', 'Apólice/endosso enviada ao cliente'],
    StatusEmissao.REGRA_CANCELADO: ['Não', 'Sim'],
}


def garantir_padroes_emissao():
    """Cria o que faltar do cadastro padrão. Seguro rodar várias vezes: não duplica, não mexe
    em nome/inativo/observação que o usuário já tenha mudado, e só cria os retornos padrão de
    um status que ainda não tem nenhum retorno."""
    criados = 0
    for nome, regra in STATUS_PADRAO:
        status = StatusEmissao.objects.filter(regra=regra).first()
        if not status:
            status = StatusEmissao.objects.create(status=nome, regra=regra)
            criados += 1
        retornos = RETORNOS_PADRAO.get(regra)
        if retornos and not status.retornos.exists():
            RetornoClienteEmissao.objects.bulk_create(
                [RetornoClienteEmissao(status=status, retorno=texto) for texto in retornos]
            )
            criados += len(retornos)
    return criados


def vincular_acompanhamentos_antigos(simular=False):
    """Liga os acompanhamentos antigos (só tinham o nome do status e o sim/não) aos cadastros
    novos. Devolve (vinculados, sem_correspondencia)."""
    garantir_padroes_emissao()
    status_por_regra = {s.regra: s for s in StatusEmissao.objects.exclude(regra='')}
    retornos = {}
    for regra, (nao, sim) in RETORNOS_PADRAO.items():
        st = status_por_regra.get(regra)
        if st:
            retornos[regra] = (
                st.retornos.filter(retorno=nao).first(),
                st.retornos.filter(retorno=sim).first(),
            )

    vinculados = sem_correspondencia = 0
    for a in AcompanhamentoEmissao.objects.filter(status_ref__isnull=True).iterator():
        regra = AcompanhamentoEmissao.REGRA_POR_NOME_ANTIGO.get(a.status)
        status = status_por_regra.get(regra)
        if not status:
            sem_correspondencia += 1
            continue
        retorno = None
        if regra in retornos:
            nao, sim = retornos[regra]
            retorno = sim if a.apolice_enviada else nao
        vinculados += 1
        if not simular:
            a.status_ref = status
            a.retorno_ref = retorno
            a.save(update_fields=['status_ref', 'retorno_ref'])
    return vinculados, sem_correspondencia
