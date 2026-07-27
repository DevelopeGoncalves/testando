import django.db.models.deletion
from django.db import migrations, models


def migrar_ramo_e_tipo_documento(apps, schema_editor):
    RegistroProducao = apps.get_model('core', 'RegistroProducao')
    Ramo = apps.get_model('core', 'Ramo')
    TipoDocumento = apps.get_model('core', 'TipoDocumento')

    for reg in RegistroProducao.objects.all():
        texto_ramo = (reg.grupo_ramo_txt or '').strip()
        if texto_ramo:
            ramo_obj = Ramo.objects.filter(grupo_e_ramo__iexact=texto_ramo).first()
            reg.grupo_ramo_new_id = ramo_obj.id if ramo_obj else None

        texto_doc = (reg.tipo_documento_txt or '').strip()
        if texto_doc:
            doc_obj = TipoDocumento.objects.filter(tipo_documento__iexact=texto_doc).first()
            reg.tipo_documento_new_id = doc_obj.id if doc_obj else None

        reg.save(update_fields=['grupo_ramo_new', 'tipo_documento_new'])


def reverter_ramo_e_tipo_documento(apps, schema_editor):
    RegistroProducao = apps.get_model('core', 'RegistroProducao')

    for reg in RegistroProducao.objects.all():
        reg.grupo_ramo_txt = reg.grupo_ramo_new.grupo_e_ramo if reg.grupo_ramo_new_id else ''
        reg.tipo_documento_txt = reg.tipo_documento_new.tipo_documento if reg.tipo_documento_new_id else ''
        reg.save(update_fields=['grupo_ramo_txt', 'tipo_documento_txt'])


def montar_chave(seguradora_id, grupo_ramo_id, tipo_documento_id, documento, endosso):
    partes = [
        str(seguradora_id or ''),
        str(grupo_ramo_id or ''),
        str(tipo_documento_id or ''),
        (documento or '').strip().upper(),
        (endosso or '').strip().upper(),
    ]
    return '&'.join(partes)


def preencher_chave_unica(apps, schema_editor):
    RegistroProducao = apps.get_model('core', 'RegistroProducao')

    for reg in RegistroProducao.objects.all():
        reg.chave_unica = montar_chave(
            reg.seguradora_id, reg.grupo_ramo_id, reg.tipo_documento_id, reg.documento, reg.endosso
        )
        reg.save(update_fields=['chave_unica'])


def limpar_chave_unica(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_colaborador_data_fim_emprego_and_more'),
    ]

    operations = [
        # 1. Renomeia os campos de texto atuais para nomes temporários
        migrations.RenameField(
            model_name='registroproducao',
            old_name='grupo_ramo',
            new_name='grupo_ramo_txt',
        ),
        migrations.RenameField(
            model_name='registroproducao',
            old_name='tipo_documento',
            new_name='tipo_documento_txt',
        ),
        # 2. Cria os novos campos como ForeignKey de verdade
        migrations.AddField(
            model_name='registroproducao',
            name='grupo_ramo_new',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                to='core.ramo', verbose_name='Grupo/Ramo',
            ),
        ),
        migrations.AddField(
            model_name='registroproducao',
            name='tipo_documento_new',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                to='core.tipodocumento', verbose_name='Tipo documento',
            ),
        ),
        # 3. Migra os dados existentes (texto -> FK) casando pelo valor exibido na base
        migrations.RunPython(migrar_ramo_e_tipo_documento, reverter_ramo_e_tipo_documento),
        # 4. Remove os campos de texto temporários
        migrations.RemoveField(
            model_name='registroproducao',
            name='grupo_ramo_txt',
        ),
        migrations.RemoveField(
            model_name='registroproducao',
            name='tipo_documento_txt',
        ),
        # 5. Renomeia os novos campos FK para os nomes definitivos
        migrations.RenameField(
            model_name='registroproducao',
            old_name='grupo_ramo_new',
            new_name='grupo_ramo',
        ),
        migrations.RenameField(
            model_name='registroproducao',
            old_name='tipo_documento_new',
            new_name='tipo_documento',
        ),
        # 6. Adiciona a chave única e preenche os registros existentes
        migrations.AddField(
            model_name='registroproducao',
            name='chave_unica',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name='Chave única'),
        ),
        migrations.RunPython(preencher_chave_unica, limpar_chave_unica),
    ]
