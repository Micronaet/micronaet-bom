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
        preload_pool = self.pool.get('mrp.production.oven.selected')

        excluded_code = {
            2: ('TL', 'TS', 'MT', 'MS', 'PO'),
            3: ('CUS', 'SET', 'CIN', 'BRA'),
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

        '''
        # =====================================================================
        # Oven preload Job done or pending
        # =====================================================================
        job_pool = self.pool.get('industria.job')
        oven_pool = self.pool.get('mrp.production.oven.selected')
        oven_data = {}
        # =====================================================================
        '''

        # ---------------------------------------------------------------------
        # Preload Oven Jobs (cover order need!):
        # ---------------------------------------------------------------------
        preload_ids = preload_pool.search(cr, uid, [
            ('job_id.created_at', '>=', '%s 00:00:00' % period_from),
            ('job_id.created_at', '<=', '%s 23:59:59' % period_to),
            ('job_id.state', '!=', 'ERROR'),
        ], context=context)

        preload_stock = {}
        _logger.info('Loading %s Job done' % len(preload_ids))
        for preload in preload_pool.browse(
                cr, uid, preload_ids, context=context):
            state = preload.job_id.state
            key = preload.color_code, preload.bom_id
            if key not in preload_stock:
                preload_stock[key] = [
                    0.0,  # COMPLETED, DRAFT, RUNNING >> All!
                    0.0,  # Pending
                    ]
            total = preload.total
            if state != 'COMPLETED':  # Not done
                preload_stock[key][1] += total
            preload_stock[key][0] += total

        # ---------------------------------------------------------------------
        #                            XLS Log file:
        # ---------------------------------------------------------------------
        path = '/home/administrator/photo/log/oven'
        now = datetime.now()
        now_text = str(now).replace('/', '_').replace(':', '.')

        excel_pool = self.pool.get('excel.writer')
        excel_filename = os.path.join(
            path,
            '1.Stock_Status_Oven_%s.xlsx' % (
                now_text,
                ))

        # Stock status from Season Job
        header = [
            'Colore',
            'DB padre',
            'Fatti',
            'Pendenti',
            ]
        width = [
            20, 30, 5, 5,
            ]

        ws_name = 'Forno'
        excel_pool.create_worksheet(name=ws_name)
        excel_pool.column_width(ws_name, width)

        row = 0
        excel_pool.write_xls_line(ws_name, row, header)
        excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)
        excel_pool.freeze_panes(ws_name, 1, 2)

        for key in preload_stock:
            row += 1
            done, pending = preload_stock[key]
            color, parent_bom = key
            record = [
                color,
                parent_bom.code or parent_bom.name,
                done,
                pending,
            ]
            excel_pool.write_xls_line(ws_name, row, record)
        excel_pool.save_file_as(excel_filename)
        del(excel_pool)

        # ---------------------------------------------------------------------
        #                          XLS Data file:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        excel_filename = os.path.join(
            path,
            '0.MRP_Oven_%s.xlsx' % (
                now_text,
                ))

        _logger.warning('Excel: %s' % excel_filename)
        header = [
            'BOM ID', 'Famiglia', 'DB padre', 'Fatti', 'Pend.',
            '09', '10', '11', '12', '01', '02', '03', '04', '05', '06',
            '07', '08',
            ]
        header_period = {
            '09': 0, '10': 1, '11': 2, '12': 3,
            '01': 4, '02': 5, '03': 6, '04': 7, '05': 8, '06': 9,
            '07': 10, '08': 11,
            }
        fixed_col = len(header)
        empty = [0.0 for i in range(len(header_period))]
        width = [5, 15, 10, 5, 5]
        width.extend([5 for i in range(len(header_period))])

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

        master_data = {}
        log_data = []
        lines = len(line_ids)
        counter = 0

        # Order by Deadline (if empty use last date?):
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            counter += 1
            if not(counter % 50):
                _logger.info('Order line %s or %s' % (
                    counter, lines,
                ))

            # -----------------------------------------------------------------
            # Readability:
            # -----------------------------------------------------------------
            order = line.order_id
            product = line.product_id
            parent_bom = product.parent_bom_id
            deadline = line.date_deadline or ''
            deadline_month = deadline[5:7]
            deadline_ref = header_period.get(deadline_month)
            default_code = product.default_code or ''
            color = default_code[6:8]
            family = product.family_id.name or 'NON PRESENTE'
            order_closed = order.mx_closed
            line_closed = line.mx_closed

            log_record = [
                # Fixed:
                color,
                family,
                parent_bom.code or '',
                default_code,
                order.name,
                deadline_month,

                # Only for used:
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
            # Remove unneeded data:
            # -----------------------------------------------------------------
            # 1. Excluded code:
            code2 = default_code[:2]
            code3 = default_code[:3]
            if code2 in excluded_code[2] or code3 in excluded_code[3]:
                log_record[14] = 'Codice escluso'
                log_data.append(log_record)
                continue

            # 2. No color:
            if not color.strip():
                log_record[14] = 'Senza colore (no forno)'
                log_data.append(log_record)
                continue

            # 3. Mandatory data not present or not deadline filtered as present
            if not parent_bom or not default_code or not color:
                # Line not used
                log_record[14] = 'Riga non di MRP (colore, BOM, codice)'
                log_data.append(log_record)
                continue

            # -----------------------------------------------------------------
            #                          COLLECT DATA:
            # -----------------------------------------------------------------
            if color not in master_data:
                master_data[color] = {}

            # Key for record organization:
            key = family, parent_bom
            if key not in master_data[color]:
                master_data[color][key] = {}

            if product not in master_data[color][key]:
                master_data[color][key][product] = {}  # todo remove product?
            if deadline_ref not in master_data[color][
                    key][product]:
                # Total record data:
                master_data[color][key][product][deadline_ref] = {
                    'OC': 0.0,  # Order
                    'B': 0.0,  # MRP
                    'LOCK': 0.0,  # Locked
                    'D': 0.0,  # Delivered
                    'TODO': 0.0,  # TODO
                    }
            data = master_data[color][key][product][deadline_ref]

            # -----------------------------------------------------------------
            # A. Read data from line:
            # -----------------------------------------------------------------
            oc_qty = line.product_uom_qty
            b_qty = line.product_uom_maked_sync_qty
            lock_qty = line.mx_assigned_qty
            del_qty = line.delivered_qty

            # Used after for total operation
            original = {
                'oc': oc_qty,
                'mrp': b_qty,
                'assigned': lock_qty,
                'delivered': del_qty,
            }

            # -----------------------------------------------------------------
            # B. Pre clean phase 1
            # -----------------------------------------------------------------
            # Check oven stock if covered B qty and clean all real data!
            stock_key = color, parent_bom  # Key
            if stock_key not in preload_stock:
                # Use an empty record to remove much IF clause!:
                preload_stock[stock_key] = [0.0, 0.0]

            # Read if there's oven movement
            stock_qty = preload_stock[stock_key][0]

            # Available for cover OC qty (DONE and PENDING!)
            if stock_qty > b_qty:  # Full covered
                clean_qty = b_qty
            elif stock_qty > 0.0:  # Partially covered
                clean_qty = stock_qty
            else:  # Not covered
                clean_qty = 0.0

            # Clean qty (if present) cover only MRP (if present):
            if clean_qty:
                # Clean procedure:
                preload_stock[stock_key][0] -= clean_qty
                stock_qty = preload_stock[stock_key][0]  # New stock qty
                oc_qty = max(0.0, oc_qty - clean_qty)
                b_qty = max(0.0, b_qty - clean_qty)
                del_qty = max(0.0, del_qty - clean_qty)

            # -----------------------------------------------------------------
            # C. Clean Oven data with pre cleaned changing:
            # -----------------------------------------------------------------
            need_qty = max(
                0.0, oc_qty - max(b_qty + lock_qty, del_qty))

            # Check again oven total for cover this line:
            if stock_qty > need_qty:  # 1. All covered
                todo_qty = 0.0  # No need Oven operation
                used_stock = need_qty  # used only need
                # preload_stock[stock_key][0] -= need_qty  # Remove used qty
            elif stock_qty > 0.0:  # 2. Partially covered (stock present):
                todo_qty = need_qty - stock_qty  # Use remain
                used_stock = stock_qty  # used all remain
                # preload_stock[stock_key][0] = 0  # Remove used qty
            else:
                todo_qty = need_qty  # 3. All in oven
                used_stock = 0  # Not used stock

            '''
            # =================================================================
            # todo oven part (to remove!)
            # =================================================================
            # Oven Job date (first of month if not present):
            created_at = '%s-01' % (deadline or '2023-09-01')[:7]
            if created_at not in oven_data:
                oven_data[created_at] = {}

            if color not in oven_data[created_at]:
                oven_data[created_at][color] = {}

            parent_bom_id = parent_bom.id
            if parent_bom_id not in oven_data[created_at][color]:
                oven_data[created_at][color][parent_bom_id] = 0

            oven_data[created_at][color][parent_bom_id] += b_qty
            '''
            # =================================================================

            # -----------------------------------------------------------------
            # Update total for this key:
            # -----------------------------------------------------------------
            data['OC'] += original['oc']  # oc_qty
            data['B'] += original['mrp']  # b_qty
            data['LOCK'] += original['assigned']  # lock_qty
            data['D'] += original['delivered']  # del_qty

            # -----------------------------------------------------------------
            # Update log record:
            # -----------------------------------------------------------------
            log_record[6] = original['oc']  # oc_qty
            log_record[7] = original['mrp']  # b_qty
            log_record[8] = original['assigned']  # lock_qty
            log_record[9] = original['delivered']  # del_qty

            # todo correct in this position? (before instead of using stock?)
            if line_closed or order_closed:
                if oc_qty != del_qty:
                    log_record[12] = 'X'  # Forced closed manually
                    used_stock = 0.0  # Not used stock for this line
                log_record[13] = ''  # Used in total
                log_record[14] = 'Riga chiusa'  # Not used in total
                todo_qty = 0  # Removed TODO q!
            else:
                log_record[13] = 'X'  # Used in total

            # -----------------------------------------------------------------
            # Last updated: (TODO qty updated here)
            # -----------------------------------------------------------------
            # Clean oven stock with real used qty:
            try:
                preload_stock[stock_key][0] -= used_stock
            except:
                pdb.set_trace()

            log_record[11] = used_stock

            # Log real need:
            log_record[10] = todo_qty

            # Master report with real need:
            data['TODO'] += todo_qty

            # todo possible free q. if B > delivered!
            log_data.append(log_record)

        # ---------------------------------------------------------------------
        #                     Excel file with master data:
        # ---------------------------------------------------------------------
        for color in master_data:   # Color loop
            ws_name = False  # Create after (if needed)
            row = 0
            for key in sorted(master_data[color]):
                family, parent_bom = key
                # parent_bom_id = parent_bom.id
                code = parent_bom.code or 'NO CODE'

                total = empty[:]
                for product in sorted(
                        master_data[color][key],
                        key=lambda p: (p.default_code or '')):

                    # Month total columns:
                    for deadline_ref in master_data[color][key][product]:
                        data = master_data[color][key][product][deadline_ref]
                        # oc = data['OC']
                        # todo = oc - max(
                        #    data['B'] + data['LOCK'], data['D'])
                        total[deadline_ref] += data['TODO']

                # -------------------------------------------------------------
                # Write line
                # -------------------------------------------------------------
                if any(total):  # Only if data is present!
                    # Write Family line:
                    stock_key = color, parent_bom
                    stock_total = preload_stock.get(stock_key, (0.0, 0.0))
                    record = [
                        parent_bom.id,
                        family,
                        code,
                        stock_total[0] - stock_total[1],  # Oven completed
                        stock_total[1],  # Oven pending
                    ]
                    record.extend([(d or '') for d in total])

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
                    row += 1
                    excel_pool.write_xls_line(ws_name, row, record)
        excel_pool.save_file_as(excel_filename)

        # ---------------------------------------------------------------------
        #                            XLS Log file:
        # ---------------------------------------------------------------------
        # Log file:
        del(excel_pool)
        excel_pool = self.pool.get('excel.writer')  # New
        excel_filename = os.path.join(
            path,
            '2.Log_MRP_Oven_%s.xlsx' % (
                now_text,
                ))

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

        for record in log_data:
            row += 1
            excel_pool.write_xls_line(ws_name, row, record)

        # Save log file:
        excel_pool.save_file_as(excel_filename)

        # =====================================================================
        # Create Job:  todo remove after!
        # =====================================================================
        '''
        import pickle
        pickle.dump(
            oven_data,
            open('/home/administrator/photo/log/oven/log/oven.pickle', 'wb'),
        )

        ctx = context.copy()
        for created_at in oven_data:
            # New document every change data:
            ctx['force_data'] = {
                'created_at': created_at
                }
            _logger.info('Create Job for data: %s' % created_at)
            for color in oven_data[created_at]:
                for parent_bom_id in oven_data[created_at][color]:
                    b_qty = oven_data[created_at][color][parent_bom_id]
                    if b_qty > 0:
                        oven_pool.create(cr, uid, {
                            'total': b_qty,
                            'bom_id': parent_bom_id,
                            'color_code': color,
                        }, context=context)

            # Generate Job with passed reference:
            oven_pool.generate_oven_job_all(cr, uid, [], context=ctx)
        # =====================================================================
        '''
        return True


