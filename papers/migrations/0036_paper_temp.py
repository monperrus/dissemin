# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-07-13 06:41
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from bulk_update.helper import bulk_update
from django.utils.timezone import utc

def move_datestamps(apps, schema_editor):
    Paper = apps.get_model('papers', 'Paper')
    
    deftime = datetime.time(0,0,0,0,tzinfo=utc)
    batch = []
    bs = 10000
    lastpk = 0
    found = True
    while found:
        print lastpk
        found = False
        qs = Paper.objects.all().order_by('pk').filter(pk__gt=lastpk)[:bs]
        for p in qs:
            found = True
            p.temp = datetime.datetime.combine(p.last_modified, deftime)
            lastpk = p.pk
            batch.append(p)
        bulk_update(batch, update_fields=['temp'])
        batch = []
    
    bulk_update(batch, update_fields=['temp'])


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0035_index_doi'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='temp',
            field=models.DateTimeField(auto_now=True, default=datetime.datetime(2016, 7, 13, 6, 41, 37, 900483, tzinfo=utc)),
            preserve_default=False,
        ),
        migrations.RunPython(move_datestamps, atomic=False),
    ]
