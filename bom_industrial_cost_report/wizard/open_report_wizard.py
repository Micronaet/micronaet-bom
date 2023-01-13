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


class SaleOrder(orm.Model):
    """ Add Scheduled action
    """
    _inherit = 'sale.order'

    def send_margin_order_invoice_bom_report_scheduler(
            self, cr, uid, margin=30.0, context=None):
        """ Generate PDF with data and send mail
        """
        if context is None:
            context = {
                'lang': 'it_IT',
                }
        season_month = 9
        wizard_pool = self.pool.get('product.bom.report.limit.wizard')
        ctx = context.copy()
        ctx['save_mode'] = True  # generate file not print report

        # Setup wizard call:
        now = datetime.now()
        month = now.month
        if month >= season_month:
            year = now.year
        else:
            year = now.year - 1
        from_date = '%s-%02d-01' % (year, season_month)

        wizard_id = wizard_pool.create(cr, uid, {
            'from_date': from_date,
            # 'to_date': '',
            'min_margin': margin,
            'report_name': 'industrial_cost_bom_report',
        }, context=context)
        filename, mail_message = wizard_pool.action_print_invoice_cost_analysis(
            cr, uid, [wizard_id], context=ctx)

        # ---------------------------------------------------------------------
        # Report in ODT mode:
        # ---------------------------------------------------------------------
        now = now.strftime(DEFAULT_SERVER_DATETIME_FORMAT).replace(
            '-', '_').replace(':', '.')

        # Create attachment block for send after:
        xlsx_raw = open(filename, 'rb').read()
        attachments = [('Controllo margini OC e FT %s.xlsx' % now, xlsx_raw)]

        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 'bom_industrial_cost_report', 'group_margin_report')[1]
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)

        # Body message:
        body = '<b>Margini OC e FT, dettaglio:</b><br/>\n'
        for mode in mail_message:
            body += 'Analisi %s<br/>\n' % mode
            for state in mail_message[mode]:
                total = mail_message[mode][state]
                body += ' - %s: Totale <b>%s</b> su %s righe<br/>\n' % (
                    state, int(total[0]), int(total[1]),
                    )
        thread_pool.message_post(
            cr, uid, False,
            type='email',
            body=body,
            subject='Invio automatico margini su venduto/ordinato: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments,
            context=context,
            )
        return True


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
        # ---------------------------------------------------------------------
        #                          Generate data:
        # ---------------------------------------------------------------------
        new_date = str(datetime.now() - timedelta(days=7))[:19]
        # Parameters:
        if context is None:
            context = {}
        save_mode = context.get('save_mode')
        if save_mode:
            mail_message = {
                'Fatturato': {
                    'NIENTE DISTINTA': [0.0, 0.0],  # Total, lines
                    'BASSO': [0.0, 0.0],  # Total, lines
                    'NEGATIVO': [0.0, 0.0],  # Total, lines
                    'CORRETTO': [0.0, 0.0],  # Total, lines
                    },
                'Ordinato': {
                    'NIENTE DISTINTA': [0.0, 0.0],  # Total, lines
                    'BASSO': [0.0, 0.0],  # Total, lines
                    'NEGATIVO': [0.0, 0.0],  # Total, lines
                    'CORRETTO': [0.0, 0.0],  # Total, lines
                    },
                }

        # Pool used:
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('account.invoice.line')
        order_line_pool = self.pool.get('sale.order.line')
        excel_pool = self.pool.get('excel.writer')

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        # ---------------------------------------------------------------------
        # Setup domain for invoice:
        # ---------------------------------------------------------------------
        domain = []
        order_domain = [
            ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
            ('mx_closed', '=', False),
            ('order_id.mx_closed', '=', False),
            # ('forecasted_production_id', '=', False)
        ]
        from_date = wiz_proxy.from_date
        to_date = wiz_proxy.to_date
        min_margin = max(wiz_proxy.min_margin, 0.0)  # Not negative

        comment = ''
        order_comment = ''
        if from_date:
            domain.append(('invoice_id.date_invoice', '>=', from_date))
            order_domain.append(('order_id.date_order', '>=',
                                 '%s 00:00:00' % from_date))
            comment += 'FT dalla data %s' % from_date
            order_comment += 'FT Dalla data %s' % from_date
        if to_date:
            domain.append(('invoice_id.date_invoice', '<=', to_date))
            order_domain.append(('order_id.date_order', '<=',
                                 '%s 23:59:59' % to_date))
            comment += 'FT alla data %s' % to_date
            order_comment += 'FT alla data %s' % to_date

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
        ws_name = 'Fatturato'
        mode = 'Fatt.', 'Fattura'

        header = [
            'Nuovi',
            'Stagione', 'Cliente', mode[1], 'Data',
            'Prodotto', 'Nome', 'DB',
            'Quant.', 'Pr. unit', 'Pr. Netto', 'Costo DB', 'Marg. unit.',
            '% trasp', '% extra sc.',
            '%s tot.' % mode[0], 'Marg. tot', 'Marg. %',
            'No DB', 'Errore',
            'Marg. < %s%%' % min_margin,
        ]
        width = [
            5,
            8, 35, 12, 10,
            15, 30, 8,
            10, 10, 10, 10, 10,
            6, 6,
            12, 12, 10,
            5, 40, 15
        ]

        # ---------------------------------------------------------------------
        # Create WS:
        # ---------------------------------------------------------------------
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        # excel_pool.row_height(ws_name, row_list, height=10)
        # title = ['Controllo margini fatturato']

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
            'grey': {
                'text': excel_pool.get_format(key='bg_grey'),
                'number': excel_pool.get_format(key='bg_grey_number'),
            },
        }

        # ---------------------------------------------------------------------
        # Write title / header
        # ---------------------------------------------------------------------
        row = 0
        # Total line:
        excel_pool.write_xls_line(
            ws_name, row, [
                u'Analisi marginalità su fatturato '
                u'(rosso=negativo, giallo=<%s%%, bianco=corretto) -  Filtro: '
                u'%s' % (min_margin, comment),
            ], default_format=excel_format['title'])
        excel_pool.merge_cell(ws_name, [row, 0, row, 11])

        row += 1
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=excel_format['header'])
        excel_pool.freeze_panes(ws_name, 2, 6)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)

        partner_cache = {}
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
            # order = line.order_id  todo get incoterms here to test

            # Cache parameter
            if partner not in partner_cache:
                partner_cache[partner] = [
                    partner.industrial_transport_rate,
                    partner.industrial_extra_discount,
                ]
            industrial_transport_rate, industrial_extra_discount = \
                partner_cache[partner]

            # -----------------------------------------------------------------
            # Calc data used:
            # -----------------------------------------------------------------
            subtotal = line.price_subtotal
            if quantity:
                real_price = subtotal / quantity
                # A. Extra discount:
                real_price -= real_price * industrial_extra_discount / 100.0
            else:
                real_price = 0.0

            # Bom price
            bom_product = bom_data.get(code5)
            margin_rate = 0.0
            if bom_product:
                cost = bom_product.to_industrial

                # B. Extra transport cost:
                # todo manage only if incoterms:
                if industrial_transport_rate:
                    cost += cost * industrial_transport_rate / 100.0

                margin = real_price - cost
                margin_total = margin * quantity
                if subtotal:
                    margin_rate = 100.0 * margin_total / subtotal
                db = code5
                error = u''
            else:
                cost = margin = margin_total = 0.0  # no value if no cost!
                db = u''
                error = u'DB non trovata (niente margine)'

            # -----------------------------------------------------------------
            # Color setup:
            # -----------------------------------------------------------------
            if not db:
                margin_comment = 'NIENTE DISTINTA'
                color = excel_format['grey']
            elif margin_rate <= 0:
                margin_comment = 'NEGATIVO'
                color = excel_format['red']
            elif margin_rate < min_margin:
                margin_comment = 'BASSO'
                color = excel_format['yellow']
            else:
                margin_comment = 'CORRETTO'
                color = excel_format['white']

            if save_mode:
                mail_message[ws_name][margin_comment][0] += subtotal
                mail_message[ws_name][margin_comment][1] += 1

            # -----------------------------------------------------------------
            # Write data:
            # -----------------------------------------------------------------
            invoice_date = invoice.date_invoice
            data = [
                'NUOVO' if invoice_date >= new_date else '',
                line.season_period,
                u'{}'.format(partner.name),
                invoice.number,
                invoice_date,

                u'{}'.format(product.default_code),
                u'{}'.format(product.name),
                db,

                quantity,
                (line.price_unit, color['number']),
                (real_price, color['number']),
                (cost, color['number']),
                (margin, color['number']),

                (industrial_transport_rate, color['number']),
                (industrial_extra_discount, color['number']),

                (subtotal, color['number']),
                (margin_total, color['number']),
                (margin_rate, color['number']),

                u'' if db else u'X',
                error,
                margin_comment,
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
        for col in (14, 15):
            from_cell = excel_pool.rowcol_to_cell(row + 2, col)
            to_cell = excel_pool.rowcol_to_cell(1 + row + total_row, col)
            excel_pool.write_formula(
                ws_name,
                row, col, u"=SUBTOTAL(9,%s:%s)" % (from_cell, to_cell),
                excel_format['green']['number'],
                0.0,  # complete_total[position],
            )
        excel_pool.write_formula(
            ws_name,
            row, 16, u'= 100 * Q1 / P1',
            excel_format['green']['number'],
            0.0,  # complete_total[position],
        )

        # =====================================================================
        #                             SALE ORDER:
        # =====================================================================
        # Create WS:
        # ---------------------------------------------------------------------
        ws_name = 'Ordinato'
        mode = 'Ord.', 'Ordini'  # Replace header fields

        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)
        # Format yet present

        # ---------------------------------------------------------------------
        # Write title / header
        # ---------------------------------------------------------------------
        row = 0
        # Total line:
        excel_pool.write_xls_line(
            ws_name, row, [
                u'Analisi marginalità su ordinato '
                u'(rosso=negativo, giallo=<%s%%, bianco=corretto) - Filtro: '
                u'%s' % (min_margin, order_comment),
            ], default_format=excel_format['title'])
        excel_pool.merge_cell(ws_name, [row, 0, row, 11])

        row += 1
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=excel_format['header'])
        excel_pool.freeze_panes(ws_name, 2, 5)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)

        order_line_ids = order_line_pool.search(
            cr, uid, order_domain, context=context)
        for line in sorted(
                order_line_pool.browse(
                    cr, uid, order_line_ids, context=context),
                key=lambda l: (
                    l.order_id.partner_id.name,
                    l.order_id.date_order,
                )):

            # -----------------------------------------------------------------
            # Read data:
            # -----------------------------------------------------------------
            order = line.order_id
            partner = order.partner_id
            product = line.product_id
            code5 = (product.default_code or '')[:5]
            quantity = line.product_uom_qty

            # Cache parameter
            if partner not in partner_cache:
                partner_cache[partner] = [
                    partner.industrial_transport_rate,
                    partner.industrial_extra_discount,
                ]
            industrial_transport_rate, industrial_extra_discount = \
                partner_cache[partner]

            # -----------------------------------------------------------------
            # Calc data used:
            # -----------------------------------------------------------------
            subtotal = line.price_subtotal
            if quantity:
                real_price = subtotal / quantity
                # A. Extra discount:
                real_price -= real_price * industrial_extra_discount / 100.0
            else:
                real_price = 0.0

            # Bom price
            bom_product = bom_data.get(code5)
            margin_rate = 0.0
            if bom_product:
                cost = bom_product.to_industrial

                # B. Extra transport cost:
                # todo manage only if incoterms:
                if industrial_transport_rate:
                    cost += cost * industrial_transport_rate / 100.0

                margin = real_price - cost
                margin_total = margin * quantity
                if subtotal:
                    margin_rate = 100.0 * margin_total / subtotal
                db = code5
                error = u''
            else:
                cost = margin = margin_total = 0.0  # no value if no cost!
                db = u''
                error = u'DB non trovata (niente margine)'

            # -----------------------------------------------------------------
            # Color setup:
            # -----------------------------------------------------------------
            if not db:
                margin_comment = 'NIENTE DISTINTA'
                color = excel_format['grey']
            elif margin_rate <= 0:
                margin_comment = 'NEGATIVO'
                color = excel_format['red']
            elif margin_rate < min_margin:
                margin_comment = 'BASSO'
                color = excel_format['yellow']
            else:
                margin_comment = 'CORRETTO'
                color = excel_format['white']

            if save_mode:
                mail_message[ws_name][margin_comment][0] += subtotal
                mail_message[ws_name][margin_comment][1] += 1

            # -----------------------------------------------------------------
            # Write data:
            # -----------------------------------------------------------------
            date_order = (order.date_order or '')[:10]
            data = [
                'NUOVO' if date_order >= new_date else '',

                line.season_period,
                u'{}'.format(partner.name),
                order.name,
                date_order,

                u'{}'.format(product.default_code),
                u'{}'.format(product.name),
                db,

                quantity,
                (line.price_unit, color['number']),
                (real_price, color['number']),
                (cost, color['number']),
                (margin, color['number']),

                (industrial_transport_rate, color['number']),
                (industrial_extra_discount, color['number']),

                (subtotal, color['number']),
                (margin_total, color['number']),
                (margin_rate, color['number']),

                u'' if db else u'X',
                error,
                margin_comment,
            ]
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, data, default_format=color['text'])

        # ---------------------------------------------------------------------
        # Update with total:
        # ---------------------------------------------------------------------
        total_row = row - 1
        row = 0
        # todo keep updated if change columns number or position:
        for col in (15, 16):
            from_cell = excel_pool.rowcol_to_cell(row + 2, col)
            to_cell = excel_pool.rowcol_to_cell(1 + row + total_row, col)
            excel_pool.write_formula(
                ws_name,
                row, col, u"=SUBTOTAL(9,%s:%s)" % (from_cell, to_cell),
                excel_format['green']['number'],
                0.0,  # complete_total[position],
            )
        excel_pool.write_formula(
            ws_name,
            row, 16, u'= 100 * P1 / O1',
            excel_format['green']['number'],
            0.0,  # complete_total[position],
        )

        # ---------------------------------------------------------------------
        # Manage save or report mode:
        # ---------------------------------------------------------------------
        if save_mode:
            now = str(datetime.now()).replace(':', '').replace('/', '')
            excel_file = '/tmp/%s' % now
            excel_pool.save_file_as(excel_file)
            return excel_file, mail_message
        else:
            return excel_pool.return_attachment(
                cr, uid, 'Comparativo fatturato e ordinato')

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
        title = ('Confronto distinte base', )

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
        'min_margin': fields.float(
            'Margine minimo', digits=(10, 3), required=True),
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
        'min_margin': lambda *x: 30.0,
        'report_name': lambda *x: 'industrial_cost_bom_report',
    }
