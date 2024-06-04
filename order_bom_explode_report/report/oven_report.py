#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import pdb
import sys
import logging
import erppeek
import pickle
import xlsxwriter
from openerp.osv import fields, osv, expression, orm
from datetime import datetime
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    _inherit = 'mrp.production'

    def get_oven_report(self, cr, uid, context=None):
        """ Generate Oven report
        """
        if context is None:
            context = {}

        # Pool used:
        line_pool = self.pool.get('sale.order.line')
        excel_pool = self.pool.get('excel.writer')

        # ---------------------------------------------------------------------
        # XLS Log file:
        # ---------------------------------------------------------------------
        now = datetime.now()
        excel_filename = '/home/administrator/photo/log/oven/oven_%s.xlsx' % (
            str(now).replace('/', '_').replace(':', '.'),
            )

        _logger.warning('Excel: %s' % excel_filename)
        header = [
            'Riga', 'Famiglia', 'DB padre', 'Prodotto',
            ]
        header_period = {
            '09': 0, '10': 1, '11': 2, '12': 3,
            '01': 4, '02': 5, '03': 6, '04': 7, '05': 8, '06': 9,
            '07': 10, '08': 11,
            }
        fixed_col = len(header)
        empty = [0.0 for i in range(len(header_period))]
        width = [5, 15, 10, 15]
        width.extend([5 for i in range(len(header_period))])

        # Period range for documents
        now = datetime.now()
        month = now.month
        year = now.year
        if month >= 9:
            period_from = '%s-09-01' % year
            period_to = '%s-08-31' % (year + 1)
        else:
            period_from = '%s-09-01' % (year - 1)
            period_to = '%s-08-31' % year

        # Search open order:
        line_ids = line_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('cancel', 'sent', 'draft')),

            # Range period:
            ('date_deadline', '>=', period_from),
            ('date_deadline', '<=', period_to),

            # ('order_id.pricelist_order', '=', False),
            # remove no parcels product:
            # ('product_id.exclude_parcels', '=', False),

            # ('order_id.mx_closed', '=', False),  # order open
            # ('mx_closed', '=', False),  # line open

            # ('order_id.forecasted_production_id', '!=', False),
            # ('order_id.forecasted_production_id.state', 'not in',
            # ('done', 'cancel')),
            ], context=context)

        master_data = {}
        lines = len(line_ids)
        counter = 0
        pdb.set_trace()
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            counter += 1
            if not(counter % 50):
                _logger.info('Order line %s or %s' % (
                    counter, lines,
                ))

            # Readability:
            order = line.order_id
            product = line.product_id
            parent_bom = product.parent_bom_id
            deadline = line.date_deadline or ''
            deadline_month = deadline[5:7]
            deadline_ref = header_period.get(deadline_month)
            default_code = product.default_code or ''
            color = default_code[7:9]

            # todo Write log record here!
            if not parent_bom or not deadline or not default_code or not color:
                # Line not used
                continue

            family = product.family_id.name or 'NON PRESENTE'
            order_closed = order.mx_closed
            line_closed = line.mx_closed

            if color not in master_data:
                master_data[color] = {}

            if family not in master_data[color]:
                master_data[color][family] = {}

            if parent_bom not in master_data[color][family]:
                master_data[color][family][parent_bom] = {}

            if product not in master_data[color][family][parent_bom]:
                master_data[color][family][parent_bom][product] = {}
            if deadline_ref not in master_data[color][
                    family][parent_bom][product]:
                master_data[color][family][parent_bom][product][
                    deadline_ref] = {
                        'OC': 0.0,  # Order
                        'B': 0.0,  # MRP
                        'LOCK': 0.0,  # Locked
                        'D': 0.0,  # Delivered
                        # 'REMAIN': 0.0,  # Remain TODO
                    }
            data = master_data[color][family][parent_bom][product][
                deadline_ref]

            data['B'] += product.product_uom_maked_sync_qty
            data['LOCK'] += product.mx_assigned_qty
            data['D'] += product.delivered_qty

            # todo manage better line of order closed:
            if line_closed or order_closed:
                data['OC'] += product.product_uom_qty
            else:
                data['OC'] += data['D']  # Keep delivered as OC for reset

        pdb.set_trace()
        for color in master_data:   # Color loop
            ws_name = color
            excel_pool.create_worksheet(name=ws_name)
            excel_pool.column_width(ws_name, width)

            # Header
            row = 0
            excel_pool.write_xls_line(color, row, header)

            total = empty[:]
            for family in sorted(master_data[color]):
                for parent_bom in sorted(
                        master_data[color][family],
                        key=lambda p: (p.code or '')):
                    code = parent_bom.code
                    for product in sorted(
                            master_data[color][family][parent_bom],
                            key=lambda p: (p.default_code or '')):
                        for deadline_ref in master_data[color][
                                family][parent_bom][product]:
                            data = master_data[color][family][
                                parent_bom][product][deadline_ref]
                            oc = data['OC']
                            todo = oc - max(
                                data['B'] + data['LOCK'], data['D'])
                            total[deadline_ref] += todo  # remain to produce

                # Write Family line:
                record = [
                    '',  # Mode
                    family,
                    '',  # Parent BOM
                    '',  # Product
                ]
                record.extend(total)

                row += 1
                excel_pool.write_xls_line(ws_name, row, record)
            excel_pool.save_file_as(excel_filename)

        '''return excel_pool.return_attachment(
            cr, uid, 'Stampa forno',
            context=context)
            '''
        return True


