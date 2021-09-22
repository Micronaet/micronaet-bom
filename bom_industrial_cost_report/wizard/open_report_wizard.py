#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################


import os
import pdb
import sys
import logging
import openerp
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class ProductBomReportLimitWizard(orm.TransientModel):
    """ Wizard for open report with limited price date
    """
    _name = 'product.bom.report.limit.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_print_extra_period(self, cr, uid, ids, context=None):
        """ Compare price with extra period
        """
        product_pool = self.pool.get('product.product')
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        #                          Generate data:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        master_data = {}
        from_date = '1975-01-01'
        references = ['']
        for reference in wiz_proxy.extra_period.split(';'):
            reference = reference.strip()
            to_date = '%s-%s-%s' % (
                reference[-4:],
                reference[3:5],
                reference[:2],
            )
            references.append(to_date)
        references.sort()
        _logger.warning('Multi report for date: %s' % (references, ))

        # First reference normal report!
        for reference in references:
            pdb.set_trace()
            if reference:
                datas = {
                    'wizard': True,
                    'from_date': from_date,
                    'to_date': reference,
                }
            else:
                datas = {
                    'wizard': True,
                }
            records = product_pool.report_get_objects_bom_industrial_cost(
                    cr, uid, datas=datas, context=context)

            for record in records:
                # Explode record:
                (min_price, max_price, error, components, extra1, extra2,
                 index, total, product, parameter, total_text,
                 pipe_total_weight, simulated_price) = record

                # Write all price present (False = reference for 100%)
                # todo manage error field?
                if product not in master_data:
                    master_data[product] = ({}, simulated_price)
                master_data[product][0][reference] = max_price  # Save this

        # ---------------------------------------------------------------------
        #                          Excel export:
        # ---------------------------------------------------------------------
        ws_name = 'Distinte'
        header = [
            'Codice',
            'Descrizione',
            'Prezzo riferimento',

            'Prezzo simulato',
            'Variaz. %',
        ]
        width = [
            20, 40, 15,
        ]
        for reference in references[1:]:
            header.append('Al %s' % reference)
            header.append('Diff. %')
            width.append(15)
            width.append(10)

        # ---------------------------------------------------------------------
        # Create WS:
        # ---------------------------------------------------------------------
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        # excel_pool.row_height(ws_name, row_list, height=10)
        title = ('Confronto distinte base',)

        # ---------------------------------------------------------------------
        # Generate format used:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        f_title = excel_pool.get_format(key='title')
        f_header = excel_pool.get_format(key='header')
        f_text = excel_pool.get_format(key='text')
        f_number = excel_pool.get_format(key='number')

        # ---------------------------------------------------------------------
        # Write title / header
        # ---------------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, [title], default_format=f_title)

        row += 1
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=f_header)

        # ---------------------------------------------------------------------
        # Product selection:
        # ---------------------------------------------------------------------
        for product in sorted(master_data, key=lambda x: x.default_code):
            row += 1
            record, simulated_price = master_data[product]
            default_code = product.default_code or ''
            current_price = record[0]['']
            line = [
                default_code or '',
                u'%s' % product.name,
                (current_price, f_number),
                (simulated_price, f_number),
            ]

            # Append other record data
            for reference in references:
                line.append(record.get(reference, 0.0))
                # Calc rate difference
                line.append('')  # todo calc rate
            excel_pool.write_xls_line(
                ws_name, row, line, default_format=f_text)
        return excel_pool.return_attachment(cr, uid, 'Distinte base')

    def action_print(self, cr, uid, ids, context=None):
        """ Event for print report
        """
        pdb.set_trace()
        if context is None:
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        datas = {
            'wizard': True,
            'from_date': wiz_proxy.from_date or False,
            'to_date': wiz_proxy.to_date or False,
            }

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report',
            'datas': datas,
            }

    _columns = {
        'from_date': fields.date('From date'),
        'to_date': fields.date('To date'),
        'extra_period': fields.char(
            'Date valutazione',
            help='Periodi extra l\'attuale, es. per avere gli ultrimi 3 anni:'
                 '01/09/2020;01/09/2019;01/09/2018'),
        }
