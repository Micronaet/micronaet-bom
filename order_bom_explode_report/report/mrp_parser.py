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
import openerp
import xlsxwriter  # XLSX export
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp import tools
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class MrpBomInherit(orm.Model):
    """ Add master function here
    """
    _inherit = 'mrp.bom'

    def report_mrp_status_component_excel_file(self, cr, uid, context=None):
        """ Extract filename from master data
        """
        excel_pool = self.pool.get('excel.writer')
        parameters = {'width': 300, }  # Comment box

        res = self.report_mrp_status_component_master_data(
            cr, uid, context=context)

        # ---------------------------------------------------------------------
        # Excel report:
        # ---------------------------------------------------------------------
        ws_name = _(u'Consumi MRP schedulate')
        excel_pool.create_worksheet(ws_name)

        # Format used:
        excel_pool.set_format(number_format='#,##0.#0')
        format_mode = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),

            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
            },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),

            },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
            },
            'green': {
                'text': excel_pool.get_format('bg_green'),
                'number': excel_pool.get_format('bg_green_number'),
            },
        }

        now = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        excel_pool.column_width(ws_name, [
            15, 45,
            40,
            10, 10, 10, 10, 10, 10,
            15,
            ])

        # Title line:
        row = 0  # Start line
        excel_pool.write_xls_line(
            ws_name, row, [
                u'Analisi componenti in produzione:'
                ], default_format=format_mode['title'])

        # Header line:
        row += 2
        excel_pool.write_xls_line(
            ws_name, row, [
                u'MRP', u'Pianificata',
                u'Componente',
                u'Fabbis.', u'Pre', u'Post',
                u'Fabb.\nperiodo', u'Ordini\nForn.', u'Arrivi',
                u'Stato'
                ], default_format=format_mode['header'])

        # Add comment:
        comment = u'E\' lo stato magazzino dopo lo scarico dell\'attuale ' \
                  u'produzione (stato magazzino – scarico produzioni chiuse ' \
                  u'– attuale fabbisogno produzione)'
        excel_pool.write_comment(
            ws_name, row, 5, comment, parameters=parameters)

        header_col = 2
        for key in res:
            mrp, components, state = key
            if state == 'yellow':
                color_format = format_mode['yellow']
            elif state == 'red':
                color_format = format_mode['red']
            else:  # green
                color_format = format_mode['black']

            header_data = [
                mrp.name,
                mrp.date_planned,
            ]
            for component_data in components:
                row += 1

                # Header part:
                try:
                    excel_pool.write_xls_line(
                        ws_name, row, header_data,
                        default_format=color_format['text'])
                    # Line part:
                    excel_pool.write_xls_line(
                        ws_name, row, component_data,
                        default_format=color_format['text'], col=header_col)
                except:
                    pdb.set_trace()

        return excel_pool.send_mail_to_group(
            cr, uid,
            u'order_bom_explode_report.'
            u'group_report_mrp_stock_availability_mail_user',
            u'Controllo stato componenti su MRP pianificate',
            u'Dettaglio fattibilità MRP alla data: %s' % now,
            u'mrp_availability_check.xlsx',
            context=context)

    def report_mrp_status_component_master_data(
            self, cr, uid, context=None):
        """ Master function called from parser in old report
        """
        # ---------------------------------------------------------------------
        # Utility function:
        # ---------------------------------------------------------------------
        # A. Log:
        def write_xls_log(mode, log):
            """ Write log in WS updating counter
            """
            col = 0
            for item in log:
                self.WS[mode].write(self.counter[mode], col, item)
                col += 1
            self.counter[mode] += 1
            return

        # B. Report sort
        def report_order_component(x):
            """ Order for component in reporting
            """
            if x[5] == 'green':
                return 1, x[0].default_code
            elif x[5] == 'yellow':
                return 2, x[0].default_code
            else: # red
                return 3, x[0].default_code

        # ---------------------------------------------------------------------
        #                         Master function:
        # ---------------------------------------------------------------------
        _logger.info('Master function: Report stock unload planned MRP')

        # Read parameters:
        if context is None:
            context = {}
        data = context.get('data', {})

        # Pool used:
        sol_pool = self.pool.get('sale.order.line')
        mrp_pool = self.pool.get('mrp.production')

        days = data.get('days', 30)
        # first_supplier_id = data.get('first_supplier_id')

        now = '%s' % datetime.now()
        if now[5:7] >= '09':
            year_now = now[:4]
        else:  # next year for 01 > 08
            year_now = int(now[:4]) - 1
        reference_date = '%s-09-01 00:00:00' % year_now

        limit_date = '%s 23:59:59' % (
            datetime.now() + timedelta(days=days)).strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        _logger.warning(u'Range period: MRP from %s, Max open MRP <= %s' % (
            reference_date, limit_date))

        # Database used:
        mrp_db = {}
        mrp_unload = {}  # Stock unload from MRP
        mrp_order = {}  # Order opened
        delta_stock = {}  # Consumed component in stock (assume start is 0)

        # ---------------------------------------------------------------------
        # XLS log export:
        # ---------------------------------------------------------------------
        filename = '/home/administrator/photo/log/mrp_product.xlsx'
        _logger.warning('Log file: %s' % filename)

        # Work Sheet:
        WB = xlsxwriter.Workbook(filename)
        self.WS = {
            'mrp': WB.add_worksheet('MRP'),
            'order': WB.add_worksheet('Order'),
            }
        # Row counters:
        self.counter = {'mrp': 1, 'order': 1}

        # ------------------
        # Write Header line:
        # ------------------
        headers = {
            'mrp': [
                u'MRP', u'Data', u'Ordine', u'Prodotto', u'TODO',
                u'Componente', u'Q. TODO', u'Delta', u'Commento',
                ],
            'order': [
                u'MRP', u'Data', u'Ordine',
                u'Prodotto', u'Q. Usata prod.', u'Q. TODO prod.',
                u'Componente', u'Q. Usata comp.', u'Q. TODO comp.',
                u'Commento',
                ],
            }
        for mode, header in headers.iteritems():
            col = 0
            for h in header:
                self.WS[mode].write(0, col, h)
                col += 1

        # ---------------------------------------------------------------------
        # BLOCK A: PRODUCTION OPEN IN RANGE: TODO production needed
        # ---------------------------------------------------------------------
        # Prepare data for remain production component
        # Update mrp stock with used semi product in productions

        mrp_ids = mrp_pool.search(cr, uid, [
            # State filter:
            ('state', 'not in', ('done', 'cancel')),
            # XXX Period filter (only up not down limit), correct?
            ('date_planned', '<=', limit_date),
            ('date_planned', '>=', '2023-01-01'),  # todo remove
            ], order='date_planned, id', context=context)

        _logger.warning('Found #%s MRP <= %s' % (
            len(mrp_ids), limit_date))
        # Generate MRP total component report with totals:
        for mrp in mrp_pool.browse(cr, uid, mrp_ids, context=context):
            mrp_db[mrp] = {}

            for sol in mrp.order_line_ids:
                comment = ''

                # Total elements:
                qty = sol.product_uom_qty
                qty_maked = sol.product_uom_maked_sync_qty
                qty_delivered = sol.delivered_qty
                # todo manage assigned?
                # qty_assigned = sol.mx_assigned_qty
                # qty_ready = qty_maked + qty_assigned

                # Depend on maked or delivery check:
                if qty_maked >= qty_delivered:
                    todo = qty - qty_maked
                else:
                    todo = qty - qty_delivered

                if todo < 0.0:
                    comment += u'Over delivered'
                elif not todo:
                    comment += u'All delivered'
                elif sol.mx_closed:
                    todo = 0.0  # closed
                    comment += u'Forced closed'

                for component in sol.product_id.dynamic_bom_line_ids:
                    product = component.product_id

                    # Total to do product
                    if product not in mrp_db[mrp]:
                        # This, Delta previous MRP
                        mrp_db[mrp][product] = [0.0, 0.0]
                    if product.id not in delta_stock:
                        delta_stock[product.id] = 0.0

                    # This order:
                    this_qty = todo * component.product_qty
                    mrp_db[mrp][product][0] += this_qty

                    # Update delta with this unload
                    delta_stock[product.id] -= this_qty

                    # Current delta stock saved in order component:
                    mrp_db[mrp][product][1] = delta_stock[product.id]

                    write_xls_log('mrp', [
                        u'%s [%s]' % (mrp.name, mrp.id),
                        mrp.date_planned,
                        sol.order_id.name,
                        sol.product_id.default_code,
                        todo,  # Product TODO
                        product.default_code,  # Component
                        this_qty,
                        delta_stock[product.id],
                        comment,
                        ])

        # ---------------------------------------------------------------------
        # BLOCK B: ALL PRODUCTION: OC Total and unload maked
        # ---------------------------------------------------------------------
        # Search in all production from reference date:
        # 1. get produced element for unload stock
        # 2. get order remain in open mrp for total needed

        sol_ids = sol_pool.search(cr, uid, [
            # Linked to production # TODO remove?
            ('mrp_id', '!=', False),

            # Date range production:
            ('mrp_id.date_planned', '>=', reference_date),
            ('mrp_id.date_planned', '<=', limit_date),
            ], context=context)
        sol_ids = sol_ids[-1:]  # todo remove
        sol_proxy = sol_pool.browse(cr, uid, sol_ids, context=context)
        _logger.warning('Unload from stock old B sale line maked #%s' % len(
            sol_ids))
        for sol in sol_proxy:
            comment = ''
            qty = sol.product_uom_qty
            qty_maked = sol.product_uom_maked_sync_qty
            qty_delivered = sol.delivered_qty

            # Depend on maked or delivery check:
            if qty_maked >= qty_delivered:
                order_remain = qty - qty_maked
            else:
                order_remain = qty - qty_delivered

            if order_remain < 0.0:
                comment += u'Over delivered'
            elif not order_remain:
                comment += u'All delivered'
            elif sol.mx_closed:
                order_remain = 0.0  # closed
                comment += u'Forced closed'

            for component in sol.product_id.dynamic_bom_line_ids:
                product = component.product_id

                # Maked (unload stock)
                if product.id not in mrp_unload:
                    mrp_unload[product.id] = 0.0
                qty_maked_cmpt = qty_maked * component.product_qty
                mrp_unload[product.id] -= qty_maked_cmpt

                # Remain (order total)
                if product.id not in mrp_order:
                    mrp_order[product.id] = 0.0

                # Done and cancel means no OC remain:
                if sol.mrp_id.state in ('done', 'cancel'):
                    component_qty = 0.0  # for log
                else:
                    component_qty = order_remain * component.product_qty
                    mrp_order[product.id] -= component_qty

                write_xls_log('order', [
                    sol.mrp_id.name,
                    sol.mrp_id.date_planned,
                    sol.order_id.name,

                    # Product:
                    sol.product_id.default_code,
                    qty_maked,  # Maked / Used
                    order_remain,  # Remain order to produce

                    # Component:
                    product.default_code,  # Component
                    qty_maked_cmpt,
                    component_qty,

                    comment,
                    ])

        # ---------------------------------------------------------------------
        # BLOCK C: PREPARE FOR REPORT
        # ---------------------------------------------------------------------
        res = []
        for mrp in sorted(mrp_db, key=lambda x: (x.date_planned, x.id)):
            record = mrp_db[mrp]
            components = []
            mrp_status = 'green'
            for component, qty in record.iteritems():
                this_qty = qty[0]
                delta_stock_qty = qty[1]

                # Current stock = stock - mrp (previous unload) - delta TODO
                stock_today = mrp_unload.get(component.id, 0.0)
                stock_net_qty = component.mx_net_qty  # XXX without mrp unload!
                stock = stock_net_qty + stock_today + delta_stock_qty
                oc_period = mrp_order.get(component.id, 0.0)
                of = component.mx_of_in
                of_move = ''
                for move in component.mx_of_ids:
                    of_move += u'%s (%s)\n' % (
                        int(move.product_uom_qty or 0.0),
                        u'%s-%s' % (
                            move.date_expected[8:10],
                            move.date_expected[5:7],
                            ) if move.date_expected else '?',
                        )

                if stock >= 0.0:
                    status = 'green'
                elif stock + of >= 0.0:
                    status = 'yellow'
                    if mrp_status == 'green':
                        mrp_status = 'yellow'
                else:
                    status = 'red'
                    if mrp_status != 'red':
                        mrp_status = 'red'

                # component, need, stock, OC period, OF, status
                components.append((
                    component,  # 0. Component
                    this_qty,  # 1. MRP net q.
                    stock,  # 2. net stock after this order
                    oc_period,  # 3.
                    of,  # 4.
                    status,  # 5.
                    of_move,  # 6.
                    stock_today,  # 7. Stock net
                    stock_net_qty,  # 8. Stock without mrp unload
                    ))
            res.append((
                mrp,
                sorted(components, key=lambda x: report_order_component(x)),
                mrp_status,
                ),
                )
        WB.close()
        return res


class Parser(report_sxw.rml_parse):
    """ Report for MRP Product
    """
    # default_days = 30

    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object': self.get_object,
            'get_filter': self.get_filter,
            'get_date': self.get_date,
        })

    def get_date(self, ):
        """ Get filter selected
        """
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    def get_filter(self, data):
        """ Get filter selected
        """
        if data is None:
            data = {}

        days = data.get('days', self.default_days)

        return _('Active production for %s days') % days

    def get_object(self, data):
        """" Parser function to get master data
        """
        bom_pool = self.pool.get('mrp.bom')

        # Readability:
        cr = self.cr
        uid = self.uid
        context = {
            'data': data,
            }

        return bom_pool.report_mrp_status_component_master_data(
            cr, uid, context=context)
