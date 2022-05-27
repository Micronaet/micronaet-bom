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
    def action_print_invoice_cost_analysis(self, cr, uid, ids, context=None):
        """ Compare price with extra period
        """
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('account.invoice.line')
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        #                          Generate data:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        # ---------------------------------------------------------------------
        # Setup domain for invoice:
        # ---------------------------------------------------------------------
        domain = []
        from_date = wiz_proxy.from_date
        to_date = wiz_proxy.to_date
        if from_date:
            domain.append(('invoice_id.date_invoice', '>=', from_date))
        if to_date:
            domain.append(('invoice_id.date_invoice', '<=', to_date))

        # ---------------------------------------------------------------------
        # Load DB template
        # ---------------------------------------------------------------------
        product_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True),
        ], context=context)
        bom_data = {}
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            code5 = (product.default_code or '')[:5]
            if not code5:
                _logger.error('Prodotto senza codice: %s' % product.name)
                continue
            bom_data[code5] = product

        # ---------------------------------------------------------------------
        #                          Excel export:
        # ---------------------------------------------------------------------
        ws_name = 'Distinte'

        header = [
            'Stagione', 'Cliente', 'Fattura', 'Data',
            'Prodotto', 'Nome', 'DB',
            'Quant.', 'Pr. unit', 'Pr. Netto', 'Costo DB', 'Marg. unit.',
            'Fatt. tot.', 'Marg. tot',
            'No DB', 'Errore',
        ]
        width = [
            8, 35, 12, 10,
            15, 30, 8,
            10, 10, 10, 10, 10,
            12, 12,
            5, 40,
        ]

        # ---------------------------------------------------------------------
        # Create WS:
        # ---------------------------------------------------------------------
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        # excel_pool.row_height(ws_name, row_list, height=10)
        title = ['Controllo margini fatturato']

        # ---------------------------------------------------------------------
        # Generate format used:
        # ---------------------------------------------------------------------
        excel_pool.set_format(number_format='#,##0.#0')
        excel_format = {
            'title': excel_pool.get_format(key='title'),
            'header': excel_pool.get_format(key='header'),
            'white': {
                'text': excel_pool.get_format(key='text'),
                'number': excel_pool.get_format(key='number'),
            },
            'yellow': {
                'text': excel_pool.get_format(key='bg_yellow'),
                'number': excel_pool.get_format(key='bg_yellow_number'),
            },
            'red': {
                'text': excel_pool.get_format(key='bg_red'),
                'number': excel_pool.get_format(key='bg_red_number'),
            },
            'green': {
                'text': excel_pool.get_format(key='bg_green'),
                'number': excel_pool.get_format(key='bg_green_number'),
            },
        }

        # ---------------------------------------------------------------------
        # Write title / header
        # ---------------------------------------------------------------------
        row = 0
        # Total line

        row += 1
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=excel_format['header'])
        excel_pool.freeze_panes(ws_name, 2, 5)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)

        line_ids = line_pool.search(cr, uid, domain, context=context)
        for line in sorted(
                line_pool.browse(cr, uid, line_ids, context=context),
                key=lambda l: (
                    l.invoice_id.partner_id.name,
                    l.invoice_id.date_invoice,
                )):

            # -----------------------------------------------------------------
            # Read data:
            # -----------------------------------------------------------------
            invoice = line.invoice_id
            partner = invoice.partner_id
            product = line.product_id
            code5 = (product.default_code or '')[:5]
            quantity = line.quantity

            # -----------------------------------------------------------------
            # Calc data used:
            # -----------------------------------------------------------------
            subtotal = line.price_subtotal
            if quantity:
                real_price = subtotal / quantity
            else:
                real_price = 0.0

            # Bom price
            bom_product = bom_data.get(code5)
            if bom_product:
                cost = bom_product.to_industrial
                margin = real_price - cost
                margin_total = margin * quantity
                db = code5
                error = ''
            else:
                cost = margin = margin_total = 0.0  # no value if no cost!
                db = ''
                error = 'DB non trovata (niente margine)'

            # -----------------------------------------------------------------
            # Color setup:
            # -----------------------------------------------------------------
            if real_price < 0:
                color = excel_format['red']
            elif not margin:
                color = excel_format['yellow']
            else:
                color = excel_format['white']

            # -----------------------------------------------------------------
            # Write data:
            # -----------------------------------------------------------------
            data = [
                line.season_period,
                partner.name,
                invoice.number,
                invoice.date_invoice,

                product.default_code,
                product.name,
                db,

                quantity,
                (line.price_unit, color['number']),
                (real_price, color['number']),
                (cost, color['number']),
                (margin, color['number']),

                (subtotal, color['number']),
                (margin_total, color['number']),

                '' if db else 'X',
                error,
            ]
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, data, default_format=color['text'])

        # ---------------------------------------------------------------------
        # Update with total:
        # ---------------------------------------------------------------------
        total_row = row - 1
        row = 0
        # todo keep updated if change columns:
        for col in (12, 13):
            # col = 12  # subtotal
            from_cell = excel_pool.rowcol_to_cell(row + 2, col)
            to_cell = excel_pool.rowcol_to_cell(row + total_row, col)
            formula = u"=SUBTOTAL(9,%s:%s)" % (from_cell, to_cell)
            excel_pool.write_formula(
                ws_name,
                row, col, formula,
                excel_format['white']['number'],
                0.0,  # complete_total[position],
            )

        return excel_pool.return_attachment(cr, uid, 'Comparativo fatturato')

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
            15, 10,
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
            prices, simulated_price = master_data[product]
            default_code = product.default_code or ''
            current_price = prices['']
            if current_price:
                simulated_rate = \
                    (simulated_price - current_price) / current_price * 100.0
            else:
                simulated_rate = '/'
            line = [
                default_code or '',
                u'%s' % product.name,
                (current_price, f_number),
                (simulated_price, f_number),
                (simulated_rate, f_number),
            ]

            # Append other record data
            for reference in references[1:]:
                this_price = prices.get(reference, 0.0)
                line.append(this_price)
                if current_price:
                    this_rate = \
                        (this_price - current_price) / current_price * 100.0
                else:
                    this_rate = 0.0
                # Calc rate difference
                line.append(this_rate)
            excel_pool.write_xls_line(
                ws_name, row, line, default_format=f_text)
        return excel_pool.return_attachment(cr, uid, 'Distinte base')

    def action_print(self, cr, uid, ids, context=None):
        """ Event for print report
        """
        if context is None:
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        from_date = wiz_proxy.from_date or False
        to_date = wiz_proxy.to_date or False
        report_name = wiz_proxy.report_name
        if not to_date or not from_date:
            raise osv.except_osv(
                _('Errore report'),
                _('Il range di date è obbligatorio'),
                )
        datas = {
            'wizard': True,
            'from_date': from_date,
            'to_date': to_date,
            }

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            }

    _columns = {
        'from_date': fields.date('From date'),
        'to_date': fields.date('To date'),
        'report_name': fields.selection([
            ('industrial_cost_bom_report', 'Con costi'),
            ('industrial_cost_bom_no_price_report', 'Senza costi'),
        ], 'Tipo report', required=True),
        'extra_period': fields.char(
            'Date valutazione',
            help='Periodi extra l\'attuale, es. per avere gli ultrimi 3 anni:'
                 '01/09/2020;01/09/2019;01/09/2018'),
        }

    _defaults = {
        'report_name': lambda *x: 'industrial_cost_bom_report',
    }
