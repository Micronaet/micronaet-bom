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


class ProductProductInventoryCategory(orm.Model):
    """ Model name: Inventory category
    """
    _inherit = 'product.product.inventory.category'

    _columns = {
        'mrp_total_report': fields.boolean(
            'Report MRP totale',
            help='Presente nel report di approvvigiomento e produzione totale')
    }


class MrpBomStructureCategory(orm.Model):
    """ Model name: Inventory category
    """
    _inherit = 'mrp.bom.structure.category'

    _columns = {
        'mrp_total_report': fields.boolean(
            'Report MRP totale',
            help='Presente nel report di approvvigiomento e produzione totale')
    }


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
                self, cr, uid, empty_number, empty_text, week_pos, range_date,
                context=None):
            """ Get product touched in OC and MRP items
            """
            product_touched = {}
            product_comment = {}
            sale_line_pool = self.pool.get('sale.order.line')
            sale_line_ids = sale_line_pool.search(cr, uid, [
                ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
                ('mx_closed', '=', False),
                ('order_id.mx_closed', '=', False),
                # ('order_id.name', '=', 'OC/1/2020/07666'),  # todo demo

                # # ('product_id.not_in_report', '=', False),
                # # ('product_id.bom_placeholder', '=', False),
                # # ('product_id.bom_alternative', '=', False),
                ], context=context)
            _logger.warning('Total lines found: %s' % len(sale_line_ids))
            for line in sale_line_pool.browse(
                    cr, uid, sale_line_ids, context=context):
                product = line.product_id
                if product not in product_touched:
                    product_touched[product] = empty_number[:]
                    product_comment[product] = empty_text[:]

                # Find position in record:
                has_mrp = line.mrp_id
                if has_mrp:
                    deadline = line.mrp_id.date_planned  # todo check unlinked
                    comment = 'MRP: %s' % line.mrp_id.name
                else:
                    deadline = line.date_deadline
                    comment = 'OC: %s' % line.order_id.name
                deadline = (deadline or '/')[:10]
                if not deadline or deadline < range_date[0] or \
                        deadline > range_date[1]:
                    _logger.warning('Date extra range period: %s' % deadline)
                    # todo manage order deadlined!
                    continue

                comment = '%s [%s]' % (comment, deadline)
                relative_pos = get_week_cell(deadline, week_pos)
                if relative_pos < 0 or relative_pos > len(empty_number) - 1:
                    continue  # Extra range  # todo remove not necessary

                # Find quantity needed:
                product_uom_qty = line.product_uom_qty
                delivered_qty = line.delivered_qty
                # todo assigned_qty = line.assigned_qty

                undelivered_qty = product_uom_qty - delivered_qty
                ready_qty = 0.0
                if has_mrp:
                    maked_qty = line.product_uom_maked_sync_qty
                    if delivered_qty < maked_qty:
                        ready_qty = maked_qty - delivered_qty  # to deliver
                todo_qty = undelivered_qty - ready_qty
                product_touched[product][relative_pos] += todo_qty
                # todo add comment?
                comment += ' q. %s\n' % todo_qty
                if product_comment[product][relative_pos]:
                    product_comment[product][relative_pos] += comment
                else:
                    product_comment[product][relative_pos] = comment
            return product_touched, product_comment

        def get_purchased_material(self, cr, uid, context=None):
            """ Get list of purchase material awaiting delivery
            """
            purchase_data = {}
            company_pool = self.pool.get('res.company')  # for utility
            company_ids = company_pool.search(cr, uid, [])
            company = company_pool.browse(cr, uid, company_ids)[0]
            exclude_partner_ids = []
            exclude_partner_ids.append(company.partner_id.id)

            in_picking_type_ids = []
            for item in company.stock_report_tx_load_in_ids:
                in_picking_type_ids.append(item.id)

            move_pool = self.pool.get('stock.move')
            move_ids = move_pool.search(cr, uid, [
                ('picking_id.picking_type_id', 'in', in_picking_type_ids),
                ('picking_id.partner_id', 'not in', exclude_partner_ids),
                ('state', '=', 'assigned'),  # Only not delivered

                # todo filter period?
                # ('date', '>=', from_date), # XXX correct for virtual?
                # ('date', '<=', to_date),
            ])

            for move in move_pool.browse(cr, uid, move_ids, context=context):
                pick = move.picking_id
                date = pick.date
                date_expected = move.date_expected

                product = move.product_id
                default_code = product.default_code
                qty = line.product_uom_qty

                if product not in purchase_data:
                    purchase_data[product] = {}
                    # pick.name, pick.origin, pick.date,

                # Order not current delivered:
                # todo how to save data in database?
            return purchase_data

        def get_week_cell(date, week_pos):
            """ Get position cell
            """
            extra_range = -1  # common value
            if not date:
                _logger.error('No date for OC on MRP!')
                return extra_range
            date = date[:10]
            date_dt = datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT)
            year_week = date_dt.isocalendar()[1]
            try:
                return week_pos[year_week - 1]
            except:
                return extra_range

        def generate_header(weeks):
            """ Generate header for total report
            """
            header = [
                'Livello', 'Famiglia', 'Prodotto', 'Nome', 'Mag.',
            ]
            week_pos = {}
            columns = [15, 20, 20, 35, 10]
            fixed_col = len(header)
            day = datetime.now()
            # go sunday before:
            day = day - timedelta(days=day.isocalendar()[2])
            pos = 0
            range_date = [str(day)[:10]]
            for week in range(weeks):
                isocalendar = day.isocalendar()

                week_of_year = isocalendar[1]
                from_date = str(day)[:10]
                header.append('Y%s-W%s\n%s' % (
                    isocalendar[0], week_of_year, from_date))
                columns.append(10)
                week_pos[week_of_year] = pos
                day += timedelta(days=7)
                pos += 1
            range_date.append(str(day)[:10])
            return header, week_pos, columns, fixed_col, range_date

        # ---------------------------------------------------------------------
        # Start procedure:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}

        setup = {
            'only_data': False,  # Show lines that have data
        }
        # Add status status ON
        user_pool = self.pool.get('res.users')
        previous_status = user_pool.set_no_inventory_status(
            cr, uid, value=False, context=context)

        # Read parameter for generate structure:
        company = self.browse(cr, uid, ids[0], context=context)
        total_week = company.total_report_week

        # Generate datasheet structure:
        header, week_pos, columns, fixed_col, range_date = \
            generate_header(total_week)
        _logger.info('Start report for range: [%s %s]' % tuple(range_date))
        total_col = fixed_col + total_week - 1

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        empty_number = [0.0 for item in range(total_week)]
        empty_text = ['' for item in range(total_week)]
        total_report, product_comment = get_product_touched(
            self, cr, uid, empty_number, empty_text, week_pos, range_date,
            context=context)
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
            'grey': {  # normal grey background
                'text': excel_pool.get_format('bg_grey'),
                'number': excel_pool.get_format('bg_grey_number'),
            },
            'blue': {  # normal grey background
                'text': excel_pool.get_format('bg_blue'),
                'number': excel_pool.get_format('bg_blue_number'),
            },
            'green': {  # normal grey background
                'text': excel_pool.get_format('bg_green'),
                'number': excel_pool.get_format('bg_green_number'),
            },
            'yellow': {  # normal grey background
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
            },
            'orange': {  # normal grey background
                'text': excel_pool.get_format('bg_orange'),
                'number': excel_pool.get_format('bg_orange_number'),
            },
        }
        parameters = {'width': 300, }

        # Column setup:
        excel_pool.column_width(ws_name, columns)
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header, default_format=xls_format['header'])
        excel_pool.autofilter(ws_name, row, 0, row, fixed_col - 1)
        excel_pool.row_height(ws_name, [row], height=25)

        stock_status = {}
        for product in sorted(total_report,
                              key=lambda p: (p.family_id.name, p.default_code)
                              ):
            week_data = total_report[product]
            comment_data = product_comment[product]
            if setup['only_data'] and not any(week_data):
                _logger.warning(
                    'Removed empty line: %s' % product.default_code)
                continue
            row += 1
            available_stock = product.mx_net_mrp_qty - product.mx_mrp_b_locked

            if product not in stock_status:
                stock_status[product] = available_stock

            # -----------------------------------------------------------------
            # Fixed row part:
            # -----------------------------------------------------------------
            row_data = [
                'L1. prodotto',
                product.family_id.name,
                product.default_code,
                product.name,
                (available_stock, xls_format['blue']['number']),
            ]
            excel_pool.write_xls_line(
                ws_name, row, row_data,
                default_format=xls_format['blue']['text'])
            excel_pool.write_comment(
                ws_name, row, fixed_col - 1, 'Netto %s - Bloccato %s' % (
                    product.mx_net_mrp_qty, product.mx_mrp_b_locked
                ), parameters=parameters)

            # -----------------------------------------------------------------
            # Week dynamic row part:
            # -----------------------------------------------------------------
            # Cover with stock (all week range block):
            cover_position = 0
            while stock_status[product] > 0.0 and cover_position < total_week:
                needed_qty = week_data[cover_position]
                if not needed_qty:
                    cover_position += 1
                    continue
                stock_qty = stock_status[product]

                if stock_qty > needed_qty:
                    week_data[cover_position] = 0.0
                    stock_status[product] -= needed_qty
                    # Comment
                    comment_data[cover_position] += \
                        'Coperta da mag.: %s\n' % needed_qty
                elif stock_qty < needed_qty:
                    # not enough used all remain stock:
                    week_data[cover_position] -= stock_qty
                    stock_status[product] = 0.0  # used all available!
                    # Comment
                    comment_data[cover_position] += \
                        'Coperta da mag.: %s\n' % stock_qty
                cover_position += 1

            # -----------------------------------------------------------------
            # Write data:
            excel_pool.write_xls_line(
                ws_name, row, week_data,
                default_format=xls_format['white']['number'],
                col=fixed_col)
            # Comment:
            excel_pool.write_comment_line(
                ws_name, row, comment_data, col=fixed_col,
                parameters=parameters)

            # =================================================================
            # Sviluppo semilavorati se presenti:
            # =================================================================
            for line in product.dynamic_bom_line_ids:
                if line.category_id.mrp_total_report:
                    semiworked = line.product_id
                    if semiworked.bom_placeholder or product.bom_alternative:
                        _logger.warning('Jump placeholder')
                        continue
                    available_stock = \
                        semiworked.mx_net_mrp_qty  # not used mx_mrp_b_locked

                    if semiworked not in stock_status:
                        stock_status[semiworked] = available_stock

                    # ---------------------------------------------------------
                    # Fixed row part:
                    # ---------------------------------------------------------
                    row += 1
                    multi = line.product_qty
                    row_data = [
                        'L2. semilavorati',
                        semiworked.family_id.name,
                        '%s (x %s)' % (
                            semiworked.default_code, multi),
                        semiworked.name,
                        (available_stock, xls_format['yellow']['number']),
                        # No locked part
                    ]
                    excel_pool.write_xls_line(
                        ws_name, row, row_data,
                        default_format=xls_format['yellow']['text'])

                    excel_pool.write_comment(
                        ws_name, row, 2, 'Categoria %s' %
                        line.category_id.name, parameters=parameters)
                    excel_pool.write_comment(
                        ws_name, row, fixed_col - 1, 'Netto %s' %
                        semiworked.mx_net_mrp_qty, parameters=parameters)

                    # ---------------------------------------------------------
                    # Week dynamic row part:
                    # ---------------------------------------------------------
                    sw_week_data = [item * multi for item in week_data]
                    # Cover with stock (all week range block):
                    cover_position = 0
                    while stock_status[semiworked] > 0.0 and \
                            cover_position < total_week:
                        needed_qty = sw_week_data[cover_position]
                        if not needed_qty:
                            cover_position += 1
                            continue
                        stock_qty = stock_status[semiworked]

                        sw_comment_text = \
                            'Nr. %s x %s\n' % (int(needed_qty), multi)
                        if stock_qty > needed_qty:
                            sw_week_data[cover_position] = 0.0
                            stock_status[semiworked] -= needed_qty
                            sw_comment_text += \
                                'Coperta da mag.: %s\n' % needed_qty
                        elif stock_qty < needed_qty:
                            # not enough used all remain stock:
                            sw_week_data[cover_position] -= stock_qty
                            stock_status[semiworked] = 0.0  # used all av.!
                            sw_comment_text += 'Coperta da mag.: %s\n' % \
                                stock_qty
                        excel_pool.write_comment(
                            ws_name, row, cover_position + fixed_col,
                            sw_comment_text,
                            parameters=parameters)
                        cover_position += 1

                    # ---------------------------------------------------------
                    # Write data:
                    excel_pool.write_xls_line(
                        ws_name, row, sw_week_data,
                        default_format=xls_format['white']['number'],
                        col=fixed_col)

                    # =====================================================
                    # Sviluppo materie prime se presenti:
                    # =====================================================
                    for raw_line in semiworked.half_bom_ids:
                        raw_material = raw_line.product_id
                        inventory_category = \
                            raw_material.inventory_category_id
                        if not inventory_category.mrp_total_report:
                            _logger.warning('Inventory category not needed')
                            continue

                        available_stock = raw_material.mx_net_mrp_qty
                        if raw_material not in stock_status:
                            stock_status[raw_material] = available_stock

                        # ---------------------------------------------
                        # Fixed row part:
                        # ---------------------------------------------
                        row += 1
                        multi = raw_line.product_qty
                        row_data = [
                            'L3. materie prime',
                            raw_material.family_id.name,
                            '%s (x %s)' % (
                                raw_material.default_code, multi),
                            raw_material.name,
                            (available_stock, xls_format['orange']['number']),
                            # No locked part
                        ]
                        excel_pool.write_xls_line(
                            ws_name, row, row_data,
                            default_format=xls_format['orange']['text'])

                        # Comment:
                        excel_pool.write_comment(
                            ws_name, row, 2, 'Categoria inv. %s' %
                                             inventory_category.name,
                            parameters=parameters)
                        excel_pool.write_comment(
                            ws_name, row, fixed_col - 1, 'Netto %s' %
                            raw_material.mx_net_mrp_qty,
                            parameters=parameters)

                        # ---------------------------------------------
                        # Week dynamic row part:
                        # ---------------------------------------------
                        rm_week_data = [
                            item * multi for item in sw_week_data]
                        # Cover with stock (all week range block):
                        cover_position = 0
                        while stock_status[raw_material] > 0.0 and \
                                cover_position < total_week:
                            needed_qty = rm_week_data[cover_position]
                            if not needed_qty:
                                cover_position += 1
                                continue
                            stock_qty = stock_status[raw_material]

                            rm_comment_text = \
                                'Nr. %s x %s\n' % (int(needed_qty), multi)
                            if stock_qty > needed_qty:
                                rm_week_data[cover_position] = 0.0
                                stock_status[raw_material] -= \
                                    needed_qty
                                rm_comment_text += \
                                    'Coperta da mag.: %s\n' % \
                                    needed_qty
                            elif stock_qty < needed_qty:
                                # not enough used all remain stock:
                                rm_week_data[cover_position] -= stock_qty
                                stock_status[raw_material] = 0.0  # used all av
                                rm_comment_text += \
                                    'Coperta da mag.: %s\n' % stock_qty
                            excel_pool.write_comment(
                                ws_name, row,
                                cover_position + fixed_col,
                                rm_comment_text,
                                parameters=parameters)
                            cover_position += 1

                    # ---------------------------------------------------------
                    # Write data:
                    excel_pool.write_xls_line(
                        ws_name, row, rm_week_data,
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
