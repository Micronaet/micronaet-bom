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

    def get_oven_report_all(self, cr, uid, context=None):
        """ Generate Oven report all lines
        """
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_print_all'] = True
        return self.get_oven_report(cr, uid, context=ctx)

    def get_oven_report(self, cr, uid, context=None):
        """ Generate Oven report
        """
        if context is None:
            context = {}

        # Pool used:
        line_pool = self.pool.get('sale.order.line')
        preload_pool = self.pool.get('mrp.production.oven.selected')

        # Parameters:
        print_all = context.get('force_print_all')
        excluded_code = {
            2: (
                'TL', 'TS', 'MT', 'MS', 'PO'),
            3: (
                'CUS', 'SET', 'CIN', 'BRA',
                '230', '935',  # Wood
                ),
        }

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

        # ---------------------------------------------------------------------
        # Preload Oven Jobs (cover order need!):
        # ---------------------------------------------------------------------
        preload_ids = preload_pool.search(cr, uid, [
            ('job_id.created_at', '>=', '%s 00:00:00' % period_from),
            ('job_id.created_at', '<=', '%s 23:59:59' % period_to),
            ('job_id.state', '!=', 'ERROR'),
            ], context=context)

        oven_stock = {}
        _logger.info('Loading %s Job done' % len(preload_ids))
        for job_line in preload_pool.browse(
                cr, uid, preload_ids, context=context):
            state = job_line.job_id.state
            key = job_line.color_code, job_line.bom_id
            if key not in oven_stock:
                oven_stock[key] = [
                    0.0,  # COMPLETED, DRAFT, RUNNING >> All!
                    0.0,  # Pending
                    0.0,  # Not used (only for log)
                    ]
            total = job_line.total
            if state != 'COMPLETED':  # Pending
                oven_stock[key][1] += total
            # Same:
            oven_stock[key][0] += total  # Done (used)
            oven_stock[key][2] += total  # Done (not used)

        # path = '/home/administrator/photo/log/oven'
        path = os.path.expanduser('~/NAS/industria40/Report/Oven')
        now_text = str(now).replace('/', '_').replace(':', '.')

        # ---------------------------------------------------------------------
        #                          XLS Data file:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')  # New report
        excel_filename = os.path.join(
            path, '0.MRP_Oven_%s%s.xlsx' % ('all_' if all else '', now_text))

        _logger.warning('Excel: %s' % excel_filename)
        header = [
            'BOM ID', 'Famiglia', 'DB padre',
            'Dispo netta', 'Pend.',  # Dai Job (dispo netta, da fare)
            '09', '', '10', '', '11', '', '12', '', '01', '', '02', '',
            '03', '', '04', '', '05', '', '06', '', '07', '', '08', '',
            ]
        header_period = {
            '09': 0, '10': 1, '11': 2, '12': 3,
            '01': 4, '02': 5, '03': 6, '04': 7, '05': 8, '06': 9,
            '07': 10, '08': 11,
            }
        fixed_col = len(header)
        dynamic_col = len(header_period)

        empty = [0.0 for i in range(dynamic_col)]

        width = [
            5, 15, 10,
            8, 8,
            ]
        # Double extend for month + input cell:
        width.extend([7 for i in 2 * range(dynamic_col)])

        # Search open order:
        line_ids = line_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('cancel', 'sent', 'draft')),

            # Range period:
            ('date_deadline', '>=', period_from),
            ('date_deadline', '<=', period_to),

            # todo filter removing closed for speed up calc?
            # now it's only for log purposes
            # ('order_id.mx_closed', '=', False),  # order open
            # ('mx_closed', '=', False),  # line open

            # ('order_id.pricelist_order', '=', False),
            # remove no parcels product:
            # ('product_id.exclude_parcels', '=', False),


            # ('order_id.forecasted_production_id', '!=', False),
            # ('order_id.forecasted_production_id.state', 'not in',
            # ('done', 'cancel')),
            ], order='date_deadline', context=context)

        oven_report = {}
        log_report = []
        lines = len(line_ids)  # OC lines

        # Order by Deadline (if empty use last date?):
        counter = 0
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            counter += 1
            if not(counter % 50):
                _logger.info('Order line %s or %s' % (
                    counter, lines,
                ))

            # -----------------------------------------------------------------
            #                           Readability:
            # -----------------------------------------------------------------
            order = line.order_id
            product = line.product_id
            parent_bom = product.parent_bom_id
            deadline = line.date_deadline or ''
            deadline_month = deadline[5:7]
            deadline_ref = header_period.get(deadline_month)
            default_code = product.default_code or ''
            color = default_code[6:8].strip()
            family = product.family_id.name or 'NON PRESENTE'
            order_closed = order.mx_closed
            line_closed = line.mx_closed

            # -----------------------------------------------------------------
            # Log record
            # -----------------------------------------------------------------
            log_record = [
                # Fixed:
                color,
                family,
                parent_bom.code or '',
                default_code,
                order.name,
                deadline_month,

                # Only for used line:
                '',  # 6. OC
                '',  # 7. MRP
                '',  # 8. Locked
                '',  # 9. Delivered
                '',  # 10. TODO
                '',  # 11. Used stock

                '',  # 12. Forced closed manually
                '',  # 13. Used in report
                '',  # 14. Comment
                ]

            # -----------------------------------------------------------------
            # Remove not needed data:
            # -----------------------------------------------------------------
            # 1. Excluded code:
            code2 = default_code[:2]
            code3 = default_code[:3]
            if code2 in excluded_code[2] or code3 in excluded_code[3]:
                log_record[14] = 'Codice escluso'
                log_report.append(log_record)
                continue

            # 2. No color:
            if not color:
                log_record[14] = 'Senza colore (no forno)'
                log_report.append(log_record)
                continue

            # 3. Mandatory data not present or not deadline filtered as present
            if not parent_bom or not default_code or not color:
                # Line not used
                log_record[14] = 'Riga non di MRP (colore, BOM, codice)'
                log_report.append(log_record)
                continue

            # -----------------------------------------------------------------
            #                          COLLECT DATA:
            # -----------------------------------------------------------------
            if color not in oven_report:
                oven_report[color] = {}

            # Key for record organization:
            key = family, parent_bom
            if key not in oven_report[color]:
                oven_report[color][key] = {}

            if deadline_ref not in oven_report[color][key]:
                # Total record data:
                oven_report[color][key][deadline_ref] = 0.0

            # -----------------------------------------------------------------
            # A. Read data from line:
            # -----------------------------------------------------------------
            oc_qty = line.product_uom_qty
            mrp_qty = line.product_uom_maked_sync_qty
            lock_qty = line.mx_assigned_qty
            out_qty = line.delivered_qty

            # Used after for total operation
            original = {
                'oc': oc_qty,
                'mrp': mrp_qty,
                'assigned': lock_qty,
                'delivered': out_qty,
            }

            # -----------------------------------------------------------------
            # B. Pre clean phase 1
            # -----------------------------------------------------------------
            # Check oven stock if covered B qty and clean all real data!
            oven_key = color, parent_bom  # Key
            if oven_key not in oven_stock:
                # Use an empty record to remove much IF clause!:
                oven_stock[oven_key] = [0.0, 0.0, 0.0]

            # Read if there's oven movement
            oven_qty = oven_stock[oven_key][0]

            # Available for cover OC qty (DONE and PENDING!)
            if mrp_qty > 0:
                # New stock available for cover:
                oven_stock[oven_key][0] -= mrp_qty  # could be negative!
                oven_qty = oven_stock[oven_key][0]  # Read again after update

                # Clean OC line procedure:
                oc_qty = max(0.0, oc_qty - mrp_qty)
                mrp_qty = 0.0
                out_qty = max(0.0, out_qty - mrp_qty)

            # -----------------------------------------------------------------
            # C. Clean Oven data with pre cleaned changing:
            # -----------------------------------------------------------------
            need_qty = oc_qty - max(lock_qty, out_qty)

            # Have q. need to cover:
            if need_qty > 0:
                if oven_qty > need_qty:  # 1. All covered
                    report_qty = 0.0  # All need covered
                    oven_used_qty = need_qty  # Used need qty from stock
                elif oven_qty > 0.0:  # 2. Partially covered (stock present):
                    report_qty = need_qty - oven_qty  # Use remain
                    oven_used_qty = oven_qty  # used all remain
                else:  # Oven is <= 0
                    report_qty = need_qty  # 3. All in oven report
                    oven_used_qty = 0.0  # Not used stock
            else:  # No need for this line so no report and no oven used:
                report_qty = oven_used_qty = 0.0

            # Lines marked as closed:
            if line_closed or order_closed:
                # Forced line (closed without totally delivered):
                if oc_qty != out_qty:
                    log_record[12] = 'X'  # Forced closed manually
                    oven_used_qty = 0.0  # Not used stock for this line

                log_record[13] = ''  # Used in total
                log_record[14] = 'Riga chiusa'  # Not used in total
                report_qty = 0  # Removed TODO q!
            else:
                log_record[13] = 'X'  # Used in total

            # -----------------------------------------------------------------
            # Last updated: (TODO qty updated here)
            # -----------------------------------------------------------------
            # Clean oven stock with real used qty:
            oven_stock[oven_key][0] -= oven_used_qty

            # Oven record data (for cell):
            oven_report[color][key][deadline_ref] += report_qty

            # -----------------------------------------------------------------
            # Update log record:
            # -----------------------------------------------------------------
            log_record[6] = original['oc']  # oc_qty
            log_record[7] = original['mrp']  # mrp_qty
            log_record[8] = original['assigned']  # lock_qty
            log_record[9] = original['delivered']  # out_qty
            log_record[10] = report_qty  # Log real need:
            log_record[11] = oven_used_qty
            log_report.append(log_record)

        # ---------------------------------------------------------------------
        #                     Excel file with master data:
        # ---------------------------------------------------------------------
        format_mode = {}
        # Color loop:
        for color in oven_report:
            ws_name = False  # Create after (if needed)
            row = 0
            # Key: Family, Parent BOM Loop:
            for key in sorted(oven_report[color]):
                family, parent_bom = key
                code = parent_bom.code or 'NO CODE'
                total = empty[:]

                # Deadline Month Loop (total):
                for deadline_ref in oven_report[color][key]:
                    total[deadline_ref] += \
                        oven_report[color][key][deadline_ref]

                # -------------------------------------------------------------
                # Write line if data present:
                # -------------------------------------------------------------
                if print_all or any(total):  # Only if data is present!
                    # Write Family line:
                    oven_key = color, parent_bom
                    oven_total = oven_stock[oven_key]  # Always present here
                    # .get(oven_key, (0.0, 0.0))
                    record = [
                        parent_bom.id,
                        family,
                        code,
                        oven_total[0],  # - oven_total[1],  # Oven remain
                        oven_total[1],  # Oven pending
                    ]

                    if not ws_name:
                        # -----------------------------------------------------
                        # New page in Excel (only if there's data):
                        # -----------------------------------------------------
                        # WS setup new color page:
                        ws_name = color
                        excel_pool.create_worksheet(name=ws_name)
                        excel_pool.column_width(ws_name, width)
                        # Header (row 0):
                        excel_pool.write_xls_line(color, row, header)
                        excel_pool.autofilter(
                            ws_name, row, 0, row, len(header) - 1)
                        excel_pool.freeze_panes(ws_name, 1, 5)
                        excel_pool.column_hidden(ws_name, [0])

                        # Setup format:
                        excel_pool.set_format()
                        if not format_mode:
                            format_mode = {
                                'title': excel_pool.get_format('title'),
                                'header': excel_pool.get_format('header'),
                                'text': excel_pool.get_format('text'),
                                'number': excel_pool.get_format('number'),

                                'bg': {
                                    'red': excel_pool.get_format(
                                        'bg_red_number'),
                                    'blue': excel_pool.get_format(
                                        'bg_blue_number'),
                                    'yellow': excel_pool.get_format(
                                        'bg_yellow_number'),
                                    'green': excel_pool.get_format(
                                        'bg_green_number'),
                                },
                            }

                    # ---------------------------------------------------------
                    # Write data:
                    # ---------------------------------------------------------
                    # Clean and format empty box:
                    for item in total:
                        value = item or ''
                        record.append(value)
                        if value:
                            record.append(('', format_mode['bg']['green']))
                        else:
                            record.append(('', format_mode['bg']['yellow']))

                    row += 1
                    excel_pool.write_xls_line(ws_name, row, record)
        excel_pool.save_file_as(excel_filename)

        # ---------------------------------------------------------------------
        #                            XLS Log file:
        # ---------------------------------------------------------------------
        # Log file:
        del excel_pool
        excel_pool = self.pool.get('excel.writer')  # New report
        excel_filename = os.path.join(
            path, '2.MRP_Oven_Log_%s.xlsx' % now_text)

        _logger.warning('Excel: %s' % excel_filename)
        header = [
            'Colore',
            'Famiglia',
            'DB padre',
            'Codice',
            'OC',
            'Mese',

            'Ord',  # OC
            'Blocc.',  # B
            'Ass.',  # L
            'Cons.',  # Del
            'Da fare',  # TODO
            'Usato forno',  # Used stock oven production

            'Forzato',  # Closed manually
            'Usato',  # used
            'Commento',
            ]
        width = [
            10, 15, 12, 12, 15, 5,
            6, 6, 6, 6, 6, 6,
            6, 6, 40,
            ]

        ws_name = 'Log'
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)

        row = 0
        excel_pool.write_xls_line(ws_name, row, header)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)
        excel_pool.freeze_panes(ws_name, 1, 4)

        for record in log_report:
            row += 1
            excel_pool.write_xls_line(ws_name, row, record)

        # Save log file:
        excel_pool.save_file_as(excel_filename)

        # ---------------------------------------------------------------------
        #                            XLS Log file:
        # ---------------------------------------------------------------------
        del excel_pool
        excel_pool = self.pool.get('excel.writer')
        excel_filename = os.path.join(
            path, '1.MRP_Oven_Stock_Status_%s.xlsx' % now_text)

        # Stock status from Season Job
        header = [
            'Colore', 'DB padre',
            'Residuo',  # Done + Pending (all job) - used
            'Pendenti',  # Pending, Working
            'Totale',  # Done + Pending (all Job)
            ]
        width = [
            20, 30, 5, 5, 5,
            ]

        ws_name = 'Magazzino Forno'
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)

        row = 0
        excel_pool.write_xls_line(ws_name, row, header)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)
        excel_pool.freeze_panes(ws_name, 1, 2)

        for key in oven_stock:
            row += 1
            done, pending, done_all = oven_stock[key]
            color, parent_bom = key
            record = [
                color,
                u'%s' % (parent_bom.code or parent_bom.name),
                done,
                pending,
                done_all,
            ]
            excel_pool.write_xls_line(ws_name, row, record)
        excel_pool.save_file_as(excel_filename)
        return True
