# -*- encoding: utf-8 -*-
from __future__ import unicode_literals

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True)
def authorlink(author):
    if author.researcher_id:
        return mark_safe('<a href="'+author.researcher.url+'">'+escape(unicode(author.name))+'</a>')
    else:
        return mark_safe(escape(unicode(author.name)))


@register.filter(is_safe=True)
def publication(publi):
    result = ''
    if publi.publisher_id:
        if publi.publisher.canonical_url:
            result += '<a href="'+publi.publisher.canonical_url + \
                '">'+escape(publi.publisher.name)+'</a>, '
        else:
            result += escape(publi.publisher.name)+', '
    if publi.pubtype == 'book-chapter' and publi.journal and publi.container and publi.container != unicode(publi.journal):
        result += escape(unicode(publi.container))+', '
    if publi.journal:
        result += '<emph>'+escape(unicode(publi.journal.title))+'</emph>'
    else:
        result = escape(unicode(publi.journal_title))
    if publi.issue or publi.volume or publi.pages or publi.pubdate:
        result += ', '
    if publi.issue:
        result += '<strong>'+escape(unicode(publi.issue))+'</strong>'
    if publi.volume:
        result += '('+escape(unicode(publi.volume))+')'
    if (publi.issue or publi.volume) and publi.pubdate:
        result += ', '
    if publi.pubdate:
        result += escape(unicode(str(publi.pubdate.year)))
    return mark_safe(result)
