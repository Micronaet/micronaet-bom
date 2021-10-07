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
import sys
import logging
import xlsxwriter
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class ResCompany(orm.Model):
    """ Model name: Company report
    """
    _inherit = 'res.company'

    def mrp_total_report(self, cr, uid, ids, context=None):
        """ Total report
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def get_product_touched(
                self, cr, uid, empty, context=None):
            """ Get product touched in OC and MRP items
            """
            product_touched = {}
            sale_line_pool = self.pool.get('sale.order.line')
            sale_line_ids = sale_line_pool.search(cr, uid, [
                ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
                ('product_id.not_in_report', '=', False),
                # ('product_id.bom_placeholder', '=', False),
                # ('product_id.bom_alternative', '=', False),
                ], context=context)[:10]

            for line in sale_line_pool.browse(cr, uid, sale_line_ids,
                    context=context):
                product = line.product_id
                if product not in product_touched:
                    product_touched[product] = empty
            return product_touched

        def get_purchased_material(self, cr, uid, context=None):
            """ Get list of purchase materia avaiting delivery
            """
            # todo
            return []

        def generate_header(weeks):
            """ Generate header for total report
            """
            header = [
                'Livello', 'Famiglia', 'Prodotto', 'Nome', 'Mag.',
            ]
            header_comment = []
            columns = [7, 20, 20, 35, 10]
            fixed_col = len(header)
            day = datetime.now()
            # go sunday before:
            day = day - timedelta(days=day.isocalendar()[2])
            for week in range(weeks):
                isocalendar = day.isocalendar()

                from_date = str(day)[:10]
                header.append('Y%s-W%s\n%s' % (
                    isocalendar[0], isocalendar[1], from_date))
                columns.append(10)
                header_comment.append('Dalla data %s' % from_date)
                day += timedelta(days=7)
            return header, header_comment, columns, fixed_col

        # ---------------------------------------------------------------------
        # Start procedure:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        # Add status status ON
        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)

        # Read parameter for generate structure:
        company = self.browse(cr, uid, ids[0], context=context)
        total_week = company.total_report_week

        # Generate datasheet structure:
        header, header_comment, columns, fixed_col = \
            generate_header(total_week)
        total_col = fixed_col + total_week - 1

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        empty_record = [0.0 for item in range(total_week)]
        total_report = get_product_touched(
            self, cr, uid, empty_record, context=context)
        purchase_material = get_purchased_material(
            self, cr, uid, context=context)

        # ---------------------------------------------------------------------
        # Generate report
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        ws_name = 'Gestione MRP'
        excel_pool.create_worksheet(ws_name)

        # Format:
        excel_pool.set_format()
        xls_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'white': {  # normal white background
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
            },
        }

        # Column setup:
        excel_pool.column_width(ws_name, columns)
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=xls_format['header'])
        excel_pool.autofilter(ws_name, row, 0, row, fixed_col - 1)
        excel_pool.row_height(ws_name, [row], height=25)
        # Comment:
        # excel_pool.write_comment_line(
        #    ws_name, row, header_comment, col=fixed_col)

        stock_status = {}
        for product in sorted(total_report,
                              key=lambda p: (p.family_id.name, p.default_code)
                              ):
            row += 1
            available_stock = product.mx_net_mrp_qty - product.mx_mrp_b_locked
            row_data = [
                'prodotto',
                product.family_id.name,
                product.default_code,
                product.name,
                (available_stock, xls_format['white']['number']),
            ]

            excel_pool.write_xls_line(
                ws_name, row, row_data,
                default_format=xls_format['white']['text'])
            # week_data = [int(item) for item in total_report[product]]
            week_data = total_report[product]
            excel_pool.write_xls_line(
                ws_name, row, week_data,
                default_format=xls_format['white']['number'],
                col=fixed_col)

        # Restore previous state:
        user_pool.set_no_inventory_status(
            cr, uid, value=previous_status, context=context)

        return excel_pool.return_attachment(
            cr, uid, 'Total report', context=context)

    _columns = {
        'total_report_week': fields.integer(
            'Totale finestra report (settimane)', required=True),
    }

    _defaults = {
        'total_report_week': lambda *x: 30,
    }
