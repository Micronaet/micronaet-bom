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


class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'

    _columns = {
        'dynamic_bom_checked': fields.boolean(
            'DB controllata', readonly=True),
        'dynamic_bom_checked_date': fields.date(
            'Data controllo DB', readonly=True),
        }


class MrpBomCheckProblemWizard(orm.TransientModel):
    """ Wizard for
    """
    _name = 'mrp.bom.check.problem.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_show_line_list(self, cr, uid, ids, context=None):
        """ Show list in tree view (product in bom)
        """
        # TODO
        return True

    def action_show_list(self, cr, uid, ids, context=None):
        """ Show list in tree view
        """
        product_pool = self.pool.get('product.product')

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        start_code = wiz_proxy.start_code or ''
        component = wiz_proxy.component or False

        product_ids = product_pool.search(cr, uid, [
            ('default_code', '=ilike', '%s%%' % start_code),
            ('relative_type', '=', 'half'),
            ], context=context)

        res_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            if not component or len(product.half_bom_ids) >= component:
                res_ids.append(product.id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Product list'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': 1,
            'res_model': 'product.product',
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', res_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def excel_extract_bom_check(
            self, cr, uid, wizard, only_hw=False, context=None):
        """ Report for excel BOM compare in all category
            2 ways: only_hw or not
        """
        # ---------------------------------------------------------------------
        # Parameters
        # ---------------------------------------------------------------------
        check_order = True
        demo = False
        with_hw = True

        # Generate dynamic reference date (2 years)
        now = u'%s' % datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        now_year = int(now[:4])
        if now[5:7] >= u'09':
            reference_date = u'%s-09-01' % (now_year - 2)
        else:
            reference_date = u'%s-09-01' % (now_year - 1)
        if demo:
            reference_date = u'2019-09-01'

        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def is_placeholder(product):
            """ Check if product is a placeholder
            """
            return product.bom_placeholder or product.bom_alternative

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')
        # mrp_pool = self.pool.get('mrp.bom')
        # mrp_line_pool = self.pool.get('mrp.bom.line')
        excel_pool = self.pool.get('excel.writer')
        sale_line_pool = self.pool.get('sale.order.line')

        # ---------------------------------------------------------------------
        # Collect data::
        # ---------------------------------------------------------------------
        domain = [
            ('parent_bom_id', '!=', False),
            ]

        if only_hw:
            domain.extend([
                '|',  # '|',
                ('default_code', '=ilike', 'MT%'),
                ('default_code', '=ilike', 'TL%'),
                # ('default_code', '=ilike', 'PO%'),
                # ('default_code', '=ilike', 'MS%'),
                # ('default_code', '=ilike', 'TS%'),
                ])

        # Product and bom data:
        product_ids = product_pool.search(cr, uid, domain, context=context)

        if demo:
            product_ids = product_ids[:30]
        parents = {}
        hw = []  # HW BOM

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            parent_bom = product.parent_bom_id
            if parent_bom not in parents:
                parents[parent_bom] = []
            parents[parent_bom].append(product)

        # ---------------------------------------------------------------------
        # Sale order product:
        # ---------------------------------------------------------------------
        # Check if used / ordered < 2 year ago
        _logger.info('Read order from reference date: %s' % reference_date)
        ordered_product = []
        if check_order:
            sale_line_ids = sale_line_pool.search(cr, uid, [
                ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
                ('order_id.date_order', '>=', reference_date)
                ], context=context)
            for line in sale_line_pool.browse(
                    cr, uid, sale_line_ids, context=context):
                product = line.product_id
                if product not in ordered_product:
                    ordered_product.append(product)

        # ---------------------------------------------------------------------
        #                              Excel file:
        # ---------------------------------------------------------------------
        # First page: Note:
        # ---------------------------------------------------------------------
        ws_note_name = u'Note'
        excel_pool.create_worksheet(ws_note_name)

        excel_pool.set_format()
        cell_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'text': excel_pool.get_format('text'),
            'number': excel_pool.get_format('number'),

            'bg': {
                'red': excel_pool.get_format('bg_red'),
                'blue': excel_pool.get_format('bg_blue'),
                'yellow': excel_pool.get_format('bg_yellow'),
                'green': excel_pool.get_format('bg_green'),
                'header_blue': excel_pool.get_format('bg_blue_number_bold'),
                },
            }

        excel_pool.column_width(ws_note_name, [50])

        # ---------------------------------------------------------------------
        # Title:
        # ---------------------------------------------------------------------
        note_row = 0
        excel_pool.write_xls_line(ws_note_name, note_row, [
            u'Elenco annotazioni generiche di controllo:',
            ], default_format=cell_format['title'])
        note_row += 1

        # ---------------------------------------------------------------------
        # Header:
        # ---------------------------------------------------------------------
        excel_pool.write_xls_line(ws_note_name, note_row, [
            u'Note',
            ], default_format=cell_format['header'])
        header_row = note_row

        # todo needed?
        page_error = []
        for parent in sorted(
                parents, key=lambda x: x.product_id.default_code):
            parent_product = parent.product_id

            # -----------------------------------------------------------------
            # Create sheet:
            # -----------------------------------------------------------------
            ws_name = parent_product.default_code or u''
            if not ws_name:  # No product code so used ID
                ws_name = u'ID %s' % parent_product.id
                # Write error in "Note" page:
                excel_pool.write_xls_line(ws_note_name, note_row, [
                    u'ID %s è il prodotto: %s' % (
                        parent_product.id,
                        parent_product.name,
                    ), ], default_format=cell_format['title'])
                note_row += 1

            _logger.warning(u'New page: %s' % ws_name)
            version = 1
            while True:
                try:
                    excel_pool.create_worksheet(ws_name)
                    break  # Created so exit
                except:
                    page_error.append(ws_name)
                    _logger.error(
                        u'Cannot create %s sheet, use yet created' % ws_name)
                    ws_name = u'%s vers. %s' % (
                        ws_name, version
                    )

            header = [
                u'OK', u'Venduto', u'Prodotto', u'Nome', u'Pz',
                ]
            footer = []
            width = [
                3, 6, 12, 40, 4,
                ]

            extra_col = len(header)

            # -----------------------------------------------------------------
            #               Extract category list (extra columns):
            # -----------------------------------------------------------------
            category_db = {}  # DB used for col header and pos translation
            categories = []  # temp list
            for line in parent.bom_line_ids:
                category = line.category_id
                product = line.product_id
                categories.append((
                    category,
                    is_placeholder(product),
                    # Compare with lines:
                    product,
                    line.product_qty,
                    ))

            pos = 0
            for category, placeholder, product, qty in sorted(
                    categories, key=lambda x: x[0].name):
                category_db[category.name] = (
                    (2 * pos) + extra_col,
                    placeholder,
                    product,
                    qty,
                    )

                # 2 Header column (2nd empty will be merged)
                header.append(u'%s%s%s' % (
                    u'[' if placeholder else u'',
                    category.name,
                    u']' if placeholder else u'',
                    ))
                header.append(u'')
                footer.append(u'')

                width.append(16)
                width.append(3)

                excel_pool.merge_cell(ws_name, [
                    header_row, (2 * pos) + extra_col,
                    header_row, (2 * pos) + extra_col + 1])
                pos += 1

            # Note:
            header.append(u'Note')
            width.append(40)

            last = len(header) - 1

            # -----------------------------------------------------------------
            # Title:
            # -----------------------------------------------------------------
            excel_pool.column_width(ws_name, width)
            row = 0
            excel_pool.write_xls_line(ws_name, row, [
                u'Elenco DB con padre: %s - %s' % (
                    ws_name, parent_product.name),
                ], default_format=cell_format['title'])
            excel_pool.freeze_panes(ws_name, 2, 5)

            # -----------------------------------------------------------------
            # Header:
            # -----------------------------------------------------------------
            row += 1
            excel_pool.write_xls_line(
                ws_name, row, header, default_format=cell_format['header'])
            excel_pool.row_height(ws_name, [row], height=30)

            # -----------------------------------------------------------------
            # Create page with parent bom:
            # -----------------------------------------------------------------
            for product in sorted(
                    parents[parent], key=lambda x: x.default_code):
                if product == parent.product_id:
                    format_mode = cell_format['bg']['yellow']
                elif product in ordered_product:
                    format_mode = cell_format['bg']['green']
                else:
                    format_mode = cell_format['text']

                record = [
                    (u'X' if product.dynamic_bom_checked else u'', format_mode),
                    (u'X' if product in ordered_product else u'', format_mode),
                    (u'%s' % product.default_code, format_mode),
                    (u'%s' % product.name, format_mode),
                    (u'%s' % int(product.q_x_pack), format_mode),
                    ]
                record.extend(['' for i in range(0, 2 * pos)])
                record.append('')  # Note

                for line in product.dynamic_bom_line_ids:
                    product = line.product_id
                    category = line.category_id.name
                    qty = line.product_qty
                    # Jump category in dynamic rules not found!
                    if category not in category_db:
                        if not record[last]:
                            record[last] += \
                                u'Categorie in regole non in DB padre:'
                        record[last] += u' [%s]' % category
                        continue
                    col = category_db[category][0]

                    cell_text = u'%s' % product.default_code
                    if is_placeholder(product):
                        record[col] = (
                            cell_text, cell_format['bg']['red'])
                    elif product == category_db[category][2]:
                        record[col] = cell_text
                    else:
                        record[col] = (
                            cell_text, cell_format['bg']['blue'])

                    if qty == category_db[category][3]:
                        record[col + 1] = qty
                    else:
                        record[col + 1] = (
                            qty, cell_format['bg']['blue'])

                    # ---------------------------------------------------------
                    # HW part:
                    # ---------------------------------------------------------
                    if with_hw:
                        if product.half_bom_id:
                            hw.append(product)

                row += 1
                excel_pool.write_xls_line(
                    ws_name, row, record, default_format=cell_format['text'])

        for error in page_error:
            excel_pool.write_xls_line(ws_note_name, note_row, [
                u'Errori pagine non create: %s '
                u'(distinte padre doppie e magari non attiva?)' % error,
                ], default_format=cell_format['title'])
            note_row += 1

        # ---------------------------------------------------------------------
        #                              HW Page
        # ---------------------------------------------------------------------
        if with_hw:
            # Title:
            ws_name = u'Semilavorati'
            excel_pool.create_worksheet(ws_name)

            excel_pool.column_width(ws_name, [
                15, 35,
                12, 4, 12, 4, 12, 4, 12, 4, 12, 4, 12, 4, 12, 4, 12, 4, 12, 4,
                ])
            row = 0
            excel_pool.write_xls_line(ws_name, row, [
                u'Distinte base: %s' % ws_name,
                ], default_format=cell_format['title'])

            # Header:
            row += 1
            excel_pool.write_xls_line(ws_name, row, [
                u'Semilavorato', u'Codice', u'Componente', u'Q.',
                ], default_format=cell_format['header'])

            # -----------------------------------------------------------------
            # Create page with parent bom:
            # -----------------------------------------------------------------
            for product in sorted(
                    hw, key=lambda x: x.default_code):
                row += 1
                excel_pool.write_xls_line(ws_name, row, [
                    product.default_code,
                    product.name,
                    ], default_format=cell_format['text'])

                # Expand component
                col = 0
                for component in sorted(
                        product.half_bom_ids,
                        key=lambda x: x.product_id.default_code):
                    col += 2
                    product_cmpt = component.product_id
                    excel_pool.write_xls_line(ws_name, row, [
                        product_cmpt.default_code,
                        component.product_qty,
                        ], default_format=cell_format['text'], col=col)

        return excel_pool.return_attachment(
            cr, uid, 'BOM check',
            # name_of_file='confronto_db.xlsx', version='8.0',  # php=True,
            context=context)

    def action_print(self, cr, uid, ids, context=None):
        """ Event for button print
        """
        if context is None:
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]

        datas = {
            'from_wizard': True,
            'from_date': wiz_proxy.from_date or False,
            'to_date': wiz_proxy.to_date or False,
            'start_code': wiz_proxy.start_code or '',
            'from_order': wiz_proxy.from_order,
            'only': wiz_proxy.only,
            'modal': wiz_proxy.modal or False,
            'component': wiz_proxy.component,
            'no_bom_product': wiz_proxy.no_bom_product,
            }

        if wiz_proxy.mode == 'order':
            report_name = 'order_bom_component_check_report'
        elif wiz_proxy.mode == 'parent':
            report_name = 'aeroo_parent_final_component_check_report'
        elif wiz_proxy.mode == 'product':
            report_name = 'aeroo_bom_all_component_check_report'
        elif wiz_proxy.mode == 'half':
            report_name = 'aeroo_hw_bom_all_component_check_report'
        elif wiz_proxy.mode == 'pipe':
            report_name = 'aeroo_pipe_bom_all_component_check_report'
        elif wiz_proxy.mode == 'line':
            report_name = 'aeroo_product_in_bom_report'
        elif wiz_proxy.mode == 'not_product':
            report_name = 'aeroo_product_not_in_bom_report'
        elif wiz_proxy.mode == 'excel':
            return self.excel_extract_bom_check(
                cr, uid, wiz_proxy, context=context)
        elif wiz_proxy.mode == 'excel_hw':
            return self.excel_extract_bom_check(
                cr, uid, wiz_proxy, only_hw=True, context=context)
        else:
            _logger.error('No report mode %s!' % wiz_proxy.mode)

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            }

    _columns = {
        'mode': fields.selection([
            ('order', 'Product BOM from order'),
            ('parent', 'Parent BOM'),
            ('product', 'Product result BOM'),
            ('half', 'Halfworked BOM'),
            ('pipe', 'Pipe in Halfworked'),
            ('line', 'Product presence bom'),
            ('not_product', 'Excluded product'),
            ('excel', 'Excel check'),
            ('excel_hw', 'Excel semilavorati'),
            ], 'Report mode', required=True),

        'from_order': fields.boolean('From order'),

        'modal': fields.selection([
            ('pipe', 'Pipe layout'),
            ], 'Report mode', required=False),

        'from_date': fields.date('From', help='Date >='),
        'to_date': fields.date('To', help='Date <'),

        'start_code': fields.char('Start code', size=20),
        'component': fields.integer('> # component'),

        'only': fields.selection([
            ('all', 'All'),
            ('error', 'Only error'),
            ('override', 'Only error and overrided'),
            ], 'Only line', required=True),
        'no_bom_product': fields.boolean('No BOM product'),
        }

    _defaults = {
        'mode': lambda *x: 'order',
        'only': lambda *x: 'all',
        }
