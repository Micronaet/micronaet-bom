# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import sys
import logging
import openerp
import xlsxwriter
import xlrd
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

class ProductInvoicedExtractXLSWizard(orm.TransientModel):
    """ Wizard for extracting invoiced wizard
    """
    _name = 'product.invoiced.extract.xls.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def get_product_cost(self, product):
        """ Extract cost from product
        """
        cost = 0.0
        date = False

        # Cases iron:
        if product.is_pipe:
            cost = product.weight * product.pipe_material_id.last_price
            date = '/'

        # Normal case (cost check):
        else:
            for supplier in product.seller_ids:
                for price in supplier.pricelist_ids:
                    if not price.is_active:
                        continue
                    if date == False or price.date_quotation > date:
                        date = price.date_quotation
                        cost = price.price
        return cost, date

    def action_extract(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {}

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        WS_name = _('Distinte base')

        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('account.invoice.line')

        # Read parameter from wizard:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        from_date = wiz_browse.from_date
        to_date = wiz_browse.to_date

        # ---------------------------------------------------------------------
        # Load list of product in invoice period
        # ---------------------------------------------------------------------
        line_ids = line_pool.search(cr, uid, [
            ('invoice_id.date_invoice', '>=', from_date),
            ('invoice_id.date_invoice', '<=', to_date),

            ('invoice_id.state', 'not in', ('cancel', 'draft',)),
            ], context=context)

        _logger.info('Load product list [Tot. lines: %s]' % len(line_ids))
        product_db = {}
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            product = line.product_id
            if product in product_db:
                continue # yet present

            product_db[product] = sorted(
                product.dynamic_bom_line_ids,
                key=lambda x: x.product_id.default_code,
                )

        # ---------------------------------------------------------------------
        # Setup Excel file:
        # ---------------------------------------------------------------------
        # Create worksheet:
        excel_pool.create_worksheet(WS_name)

        # Load format:
        excel_pool.set_format()
        format_title = excel_pool.get_format('title')
        format_header = excel_pool.get_format('header')
        format_text = excel_pool.get_format('text')
        format_center = excel_pool.get_format('text_center')
        format_number = excel_pool.get_format('number')
        format_number_red = excel_pool.get_format('number_red')
        format_number_green = excel_pool.get_format('number_green')

        excel_pool.column_width(WS_name, [20, 50, 10, 4, 130])

        # Title:
        row = 0
        excel_pool.row_height(WS_name, row, 40)
        excel_pool.write_xls_line(WS_name, row, ['''
            Elenco prodotti risultanti dalle vendite del periodo con 
            valorizzazione del costo da distinta base [%s - %s]''' % (
                excel_pool.format_date(from_date),
                excel_pool.format_date(to_date),
                ),
            ], default_format=format_title)

        row += 2
        excel_pool.write_xls_line(WS_name, row, [
            'Codice',
            'Nome',
            'Costo',
            'Tipo',
            'Dettaglio distinta',
            ], default_format=format_header)

        # ---------------------------------------------------------------------
        # Sort element and create files:
        # ---------------------------------------------------------------------
        cost_db = {} # database for not recalc cost of product
        for product in sorted(product_db, key=lambda x: (
                1 if product_db[x] else 2, # before BOM element after no BOM
                x.default_code, # Code sort
                )):

            row += 1

            # Read fields:
            default_code = product.default_code
            name = product.name or ''
            bom = u''
            total = 0.0
            if product_db[product]:
                mode = 'PF'
                for l1 in product_db[product]:
                    p1 = l1.product_id
                    hw_bom = p1.half_bom_ids
                    if p1 not in cost_db:
                        cost_db[p1], date1 = self.get_product_cost(p1)
                    cost1 = cost_db[p1]

                    # TODO used cost db
                    if hw_bom:
                        bom += u'SL %s:\n' % p1.default_code

                        for l2 in hw_bom:
                            p2 = l2.product_id
                            if p2 not in cost_db:
                                cost_db[p2], date2 = self.get_product_cost(p2)
                            cost2 = cost_db[p2]
                            subtotal = l2.product_qty * cost2
                            bom += u'    %s >> %s x %s€ (Data: %s) = %s€\n' % (
                                p2.default_code,
                                l2.product_qty,
                                cost2,
                                date2,
                                subtotal,
                                )
                            total += subtotal
                    else:
                        subtotal = l1.product_qty * cost1
                        bom += u'%s >> %s x %s€ (Data: %s) = %s€\n' % (
                            p1.default_code,
                            l1.product_qty,
                            cost1,
                            date1,
                            subtotal,
                            )
                        total += subtotal
            else:
                if product.half_bom_ids:
                    mode = 'SL'
                else:
                    mode = 'MP'

            excel_pool.write_xls_line(WS_name, row, [
                product.default_code or '',
                product.name or '',
                (total, format_number),
                (mode, format_center),
                bom,
                ], default_format=format_text)

        return excel_pool.return_attachment(cr, uid, WS_name,
            name_of_file='DB_prodotti_venduti.xlsx', version='8.0', php=True,
            context=context)

    _columns = {
        'from_date': fields.date('From date >=', required=True),
        'to_date': fields.date('To date <', required=True),
        }
