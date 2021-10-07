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
        def get_product_touched(self, cr, uid, context=None):
            """ Get product touched in OC and MRP items
            """
            # todo
            return []

        def get_purchased_material(self, cr, uid, context=None):
            """ Get list of purchase materia avaiting delivery
            """
            # todo
            return []

        def generate_header(weeks):
            """ Generate header for total report
            """
            header = [
                'Livello', 'Prodotto', 'Nome',
            ]
            columns = [7, 20, 35]
            fixed_col = len(columns)

            day = datetime.now()
            for week in range(weeks):
                isocalendar = day.isocalendar()
                header.append('Y%s-W%s' % isocalendar[:2])
                columns.append(10)
                day += timedelta(days=7)
            return header, columns, fixed_col

        # ---------------------------------------------------------------------
        # Start procedure:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        # Add status for calc. HW only (filter)?
        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)

        # Read parameter for generate structure:
        company = self.browse(cr, uid, ids[0], context=context)
        total_week = company.total_report_week

        # Generate datasheet structure:
        header, columns, fixed_col = generate_header(total_week)

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        total_report = {}

        products = get_product_touched(
            self, cr, uid, context=context)
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
            'white': {  # normal white background
                'title': excel_pool.get_format('title'),
                'header': excel_pool.get_format('header'),
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
            },
        }

        # Column setup:
        excel_pool.column_width(ws_name, columns)
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=xls_format['white']['header'])

        for product in products:
            row += 1
            row_data = []
            excel_pool.write_xls_line(
                ws_name, row, row_data,
                default_format=xls_format['white']['header'])

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
