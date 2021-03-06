# -*- encoding: utf-8 -*-

# Dissemin: open access policy enforcement tool
# Copyright (C) 2014 Antonin Delpeuch
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

from __future__ import unicode_literals

from statistics.models import COMBINED_STATUS_CHOICES
from statistics.models import PDF_STATUS_CHOICES

from django import forms
from django.utils.translation import ugettext_lazy as _
from haystack import inputs
from haystack.forms import SearchForm
from papers.baremodels import PAPER_TYPE_CHOICES
from papers.models import Department
from papers.models import Paper
from papers.models import Researcher
from papers.name import has_only_initials
from papers.utils import remove_diacritics
from papers.utils import validate_orcid
from publishers.models import OA_STATUS_CHOICES_WITHOUT_HELPTEXT


class OrcidField(forms.CharField):

    def to_python(self, val):
        if not val:
            return
        cleaned_val = validate_orcid(val)
        if cleaned_val is None:
            raise forms.ValidationError(
                _('Invalid ORCID identifier.'), code='invalid')
        return cleaned_val


class ResearcherDepartmentForm(forms.Form):
    value = forms.ModelChoiceField(
        label=_('Department'), queryset=Department.objects.all())
    pk = forms.ModelChoiceField(label=_(
        'Researcher'), queryset=Researcher.objects.all(), widget=forms.HiddenInput())
    name = forms.CharField(widget=forms.HiddenInput(), initial='department_id')


class AddUnaffiliatedResearcherForm(forms.Form):
    first = forms.CharField(label=_('First name'),
                            max_length=256, min_length=2, required=False)
    last = forms.CharField(label=_('Last name'),
                           max_length=256, min_length=2, required=False)
    force = forms.CharField(max_length=32, required=False)

    def clean_first(self):
        first = self.cleaned_data.get('first')
        if first and has_only_initials(first):
            raise forms.ValidationError(
                _('Please spell out at least one name.'), code='initials')
        return first

    def clean(self):
        cleaned_data = super(AddUnaffiliatedResearcherForm, self).clean()
        if not cleaned_data.get('first') or not cleaned_data.get('last'):
            if not cleaned_data.get('last'):
                self.add_error('last',
                               forms.ValidationError(_('A last name is required.'), code='required'))
            else:
                self.add_error('first',
                               forms.ValidationError(_('A first name is required.'), code='required'))
        return cleaned_data


class Sloppy(inputs.Exact):

    def prepare(self, query_obj):
        exact = super(Sloppy, self).prepare(query_obj)
        return "%s~%d" % (exact, self.kwargs['slop'])


def aggregate_combined_status(queryset):
    return queryset.aggregations({
        "status": {"terms": {"field": "combined_status"}},
    })


class PaperForm(SearchForm):
    SORT_CHOICES = [
        ('', _('publication date')),
        ('text', _('title')),
    ]
    ORDER_CHOICES = [
        ('', _('decreasing')),
        ('inc', _('increasing')),
    ]
    status = forms.MultipleChoiceField(
        choices=COMBINED_STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False)
    DATE_FORMATS = ['%Y', '%Y-%m', '%Y-%m-%d']
    pub_after = forms.DateField(input_formats=DATE_FORMATS, required=False)
    pub_before = forms.DateField(input_formats=DATE_FORMATS, required=False)
    doctypes = forms.MultipleChoiceField(
        choices=PAPER_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False)
    authors = forms.CharField(max_length=200, required=False)
    sort_by = forms.ChoiceField(choices=SORT_CHOICES, required=False)
    reverse_order = forms.ChoiceField(choices=ORDER_CHOICES, required=False)

    # Superuser only
    visible = forms.ChoiceField(
        choices=[
            ('any', _('Any')),
            ('', _('Visible')),
            ('invisible', _('Invisible')),
        ],
        initial='',
        required=False)
    availability = forms.ChoiceField(
        choices=[('', _('Any'))]+PDF_STATUS_CHOICES,
        required=False)
    oa_status = forms.MultipleChoiceField(
        choices=OA_STATUS_CHOICES_WITHOUT_HELPTEXT,
        widget=forms.CheckboxSelectMultiple,
        required=False)

    def on_statuses(self):
        if self.is_valid():
            return self.cleaned_data['status']
        else:
            return []

    def search(self):
        self.queryset = self.searchqueryset.models(Paper)

        q = remove_diacritics(self.cleaned_data['q'])
        if q:
            self.queryset = self.queryset.auto_query(q)

        visible = self.cleaned_data['visible']
        if visible == '':
            self.filter(visible=True)
        elif visible == 'invisible':
            self.filter(visible=False)

        self.form_filter('availability', 'availability')
        self.form_filter('oa_status__in', 'oa_status')
        self.form_filter('pubdate__gte', 'pub_after')
        self.form_filter('pubdate__lte', 'pub_before')
        self.form_filter('doctype__in', 'doctypes')

        # Filter by authors.
        # authors field: a comma separated list of full/last names.
        # Items with no whitespace of prefixed with 'last:' are considered as
        # last names; others are full names.
        for name in self.cleaned_data['authors'].split(','):
            name = name.strip()

            if name.startswith('last:'):
                is_lastname = True
                name = name[5:].strip()
            else:
                is_lastname = ' ' not in name

            if not name:
                continue

            if is_lastname:
                self.filter(authors_last=remove_diacritics(name))
            else:
                self.filter(authors_full=Sloppy(name, slop=1))

        self.queryset = aggregate_combined_status(self.queryset)

        status = self.cleaned_data['status']
        if status:
            self.queryset = self.queryset.post_filter(
                combined_status__in=status)

        # Default ordering by decreasing publication date
        order = self.cleaned_data['sort_by'] or 'pubdate'
        reverse_order = not self.cleaned_data['reverse_order']
        if reverse_order:
            order = '-' + order
        self.queryset = self.queryset.order_by(order).load_all()

        return self.queryset

    def form_filter(self, field, criterion):
        value = self.cleaned_data[criterion]
        if value:
            self.filter(**{field: value})

    def filter(self, **kwargs):
        self.queryset = self.queryset.filter(**kwargs)

    def no_query_found(self):
        return self.searchqueryset.all()
