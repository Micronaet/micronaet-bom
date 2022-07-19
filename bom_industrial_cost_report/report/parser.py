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
import xlsxwriter
import pickle
from openerp.tools.translate import _
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.osv import fields, osv, expression, orm
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)
import pdb

_logger = logging.getLogger(__name__)

type_i18n = {
    'industrial': 'COSTI INDUSTRIALI',
    'work': 'MANODOPERA',
    }

# -----------------------------------------------------------------------------
#                      UTILITY (TODO move in a module or class?):
# -----------------------------------------------------------------------------
def industrial_index_get_text(index):
    """ Convert all index value in string format
    """
    index_total = sum(index.values())
    res = ''
    for key, value in index.iteritems():
        if key not in type_i18n:
            continue # jump key not used
        res += '%s: %6.3f su %6.3f = %s%%\r\n' % (
            type_i18n[key],
            value, index_total,
            ('%6.3f' % (100.0 * value / index_total, )) if \
                index_total else 'ERRORE!',
            )
    return res


def get_pricelist(product, min_date, max_date=False, history_db=None):
    """ Return:
        min price, max price, all pricelist for this product active price,
        min_date: min quotation date (mandatory)
        max_date: max date (for evaluation in old period), not mandatory
        history_db: product last history price (maybe max date evaluation)
            key: default_code, value: (seller, price, date quotation)
    """
    # -------------------------------------------------------------------------
    # History database (price overridden but save in database):
    # -------------------------------------------------------------------------
    default_code = product.default_code

    # If there's an history value price use that for start value:
    if history_db and default_code in history_db:
        record = history_db[default_code]
        last_price = [
            # 0. supplier
            record[1],  # 0. price
            record[2],  # 1. date
            record[0],  # 2. supplier
            ]
        res = [
            record[1],  # 0. Min (not False)
            record[1],  # 1. Max
            [record],  # 2. Price list
            record[0],  # 3. Supplier min
            record[0],  # 4. Supplier max
            ]

    else:  # Empty data record:
        last_price = [False, False, False]  # Price, Date, Supplier
        res = [
            0.0,  # 0. Min (not False)
            0.0,  # 1. Max
            [],  # 2. Price list
            False,  # 3. Supplier Min
            False,  # 4. Supplier Max
            ]
    supplier = ''
    for seller in product.seller_ids:
        supplier = seller.name
        for pricelist in seller.pricelist_ids:
            # no inactive price XXX remove this filter?
            if not pricelist.is_active:  # no inactive
                continue

            # Take only period date:
            if product.bom_industrial_no_price:
                price = 0
            else:
                price = pricelist.price
            date_quotation = pricelist.date_quotation

            # XXX If max range test here:
            if max_date and date_quotation and date_quotation >= max_date:
                continue  # over maximum limit

            # -----------------------------------------------------------------
            # Max date for price (if no date or >):
            # -----------------------------------------------------------------
            if not last_price[1] or (  # no date or this is the last
                    date_quotation and date_quotation > last_price[1]):
                last_price[0] = price
                last_price[1] = date_quotation or False
                last_price[2] = supplier

            # -----------------------------------------------------------------
            # Range evaluation:
            # -----------------------------------------------------------------
            # XXX Keep here for analyse only one price:
            if date_quotation and date_quotation <= min_date:
                continue  # over minimum limit

            # Data for detail box:
            res[2].append((
                supplier,
                price,  # Unit price
                date_quotation,  # Date
                ))

            # Save min or max price:
            if not res[0] or price < res[0]:  # 0 price will be replaced
                res[0] = price
                res[3] = supplier  # Min supplier
            if price > res[1]:
                res[1] = price
                res[4] = supplier

    if not res[0] and last_price[0]:  # if not price but there's last
        # Keep the same:
        res[0] = last_price[0]
        res[1] = last_price[0]
        res[3] = supplier
        res[4] = supplier
    return res


def is_fabric_product(product):
    """ Is fabric test
        return dimension
    """
    # Start with T
    default_code = product.default_code
    if not default_code or len(default_code) < 6:
        return False

    if not default_code.startswith('T'):
        return False

    # UOM is meter:
    if product.uom_id.name != 'm':
        return False

    # Has TEX001 format:
    for (from_c, to_c) in [(3, 6), (6, 9)]:
        h = product.default_code[from_c:to_c]
        is_fabric = True
        for c in h:
            if not c.isdigit():
                is_fabric = False

        if is_fabric:
            try:
                return float(h) / 100.0 # meter
            except:
                _logger.error('Error convert %s to float' % h)
                return 0.0
    return False


def get_price_detail(price_ids):
    """ With detail
    """
    res = ''
    # If not detail:
    """
    for seller, price, date_quotation in price_ids:
        res += '%s EUR (%s) %s \n' % (
            price,  # Unit price
            date_quotation,
            seller.name,  # Supplier browse
            )
    return res
    """
    return res  # XXX no detail mode


class ProductProductBOMDump(orm.Model):
    """ Model name: Product dump product
    """

    _name = 'product.product.bom.dump'
    _description = 'Dump BOM'
    _order = 'dump_datetime desc'
    _rec_name = 'product_id'

    colors = {
        'red': '#fccac7',
        'error': '#fc5555',
        'green': '#e3fcc7',
        'blue': '#c7e1fc',
        'orange': '#fcc332',
    }

    def open_single_report_with_compare_dump(self, cr, uid, ids, context=None):
        """ Return single report (not launched from interface but from code)
        """
        product_pool = self.pool.get('product.product')
        current = self.browse(cr, uid, ids, context=context)[0]
        return product_pool.open_single_report_with_compare_dump(
            cr, uid, [current.product_id.id], context=context)

    def get_html_tag(self, data, tag='td', parameters=None):
        """ Format tag data
        """
        if parameters is None:
            parameters = {}
        data = data or ''
        tag_param = ''
        for param in parameters:
            tag_param += ' %s="%s"' % (param, parameters[param])
        return '<%s%s>%s</%s>' % (tag, tag_param, data, tag)

    def dump_data_in_html(
            self, cr, uid, dump_data, dump_compare_data, context=None):
        """ Dump data
        """
        product_pool = self.pool.get('product.product')

        # ---------------------------------------------------------------------
        #                            BOM History:
        # ---------------------------------------------------------------------
        history = ''
        dump_data = pickle.loads(dump_data)
        history += 'Range di prezzo: [<b>%s</b> - <b>%s</b>]<br/>' % (
            dump_data.get('from_industrial'),
            dump_data.get('to_industrial'),
        )

        history += '<table width="100%" border="1">'
        history += '<tr>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Categoria</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Semilavorato' \
            '</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Nome</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Codice</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Nome</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Q.</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Min</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Max</th>' \
            '</tr>'

        mixed_data = {}
        records = dump_data['product']
        counter = 0
        for record in sorted(
                records,
                key=lambda x: (x['semiproduct'], x['default_code'])):
            counter += 1

            # Semiproduct part:
            semiproduct_id = record.get('semiproduct_id')
            semiproduct = semiproduct_name = ''
            try:
                if semiproduct_id:
                    semiproduct = product_pool.browse(
                        cr, uid, semiproduct_id, context=context)
                    semiproduct_name = semiproduct.name
            except:
                semiproduct_name = '[Semilavorato eliminato]'

            # Product part:
            product_id = record.get('product_id')
            product = ''
            try:
                product = product_pool.browse(
                    cr, uid, product_id, context=context)
                product_name = product.name
            except:
                product_name = '[Prodotto eliminato]'

            category = record.get('category')
            quantity = record.get('quantity')
            min_price = record.get('min_price')
            max_price = record.get('max_price')

            # Write row:
            if not counter % 2:
                parameters = {
                    'bgcolor': self.colors['blue'],
                    }
            else:
                parameters = {}

            if not min_price or not max_price:
                parameters['bgcolor'] = self.colors['error']
                parameters['title'] = 'Prezzo minimo o massimo non presente'

            history += '<tr>%s%s%s%s%s%s%s%s</tr>' % (
                self.get_html_tag(category, parameters=parameters),
                self.get_html_tag(
                    record.get('semiproduct'), parameters=parameters),
                self.get_html_tag(semiproduct_name, parameters=parameters),

                self.get_html_tag(
                    record.get('default_code'), parameters=parameters),
                self.get_html_tag(product_name, parameters=parameters),

                self.get_html_tag(quantity, parameters=parameters),
                self.get_html_tag(min_price, parameters=parameters),
                self.get_html_tag(max_price, parameters=parameters),
                )

            # Mixed data:
            key = category, product_id

            if key in mixed_data:
                # Particular case (for SL with same more component)
                mixed_data[key]['history']['quantity'] += quantity
            else:
                mixed_data[key] = {
                    'status': 'red',  # no more present as default
                    'category': category,
                    'semiproduct': semiproduct,
                    'product': product,
                    'history': {
                        'quantity': quantity,
                        'min_price': min_price,
                        'max_price': max_price,
                    },
                    'compare': {},
                }
        history += '</table>'

        # ---------------------------------------------------------------------
        # Compare
        # ---------------------------------------------------------------------
        compare = ''
        dump_compare_data = pickle.loads(dump_compare_data)

        records = dump_compare_data['product']
        for record in records:
            # Product part:
            product_id = record.get('product_id')
            category = record.get('category')
            quantity = record.get('quantity')
            min_price = record.get('min_price')
            max_price = record.get('max_price')

            key = (category, product_id)
            if key in mixed_data:
                mixed_data[key]['status'] = 'green'  # Find in both
                if 'quantity' in mixed_data[key]['compare']:
                    # Particular case:
                    mixed_data[key]['compare']['quantity'] += quantity
                else:
                    mixed_data[key]['compare'] = {
                        'quantity': quantity,
                        'min_price': min_price,
                        'max_price': max_price,
                    }
            else:  # Present only in compare not in history
                # Semiproduct part:
                semiproduct_id = record.get('semiproduct_id')
                semiproduct = ''
                try:
                    if semiproduct_id:
                        semiproduct = product_pool.browse(
                            cr, uid, semiproduct_id, context=context)
                except:
                    pass

                # Product part:
                product_id = record.get('product_id')
                product = ''
                try:
                    product = product_pool.browse(
                        cr, uid, product_id, context=context)
                except:
                    pass

                mixed_data[key] = {
                    'status': 'blue',  # No more present
                    'category': category,
                    'semiproduct': semiproduct,
                    'product': product,
                    'history': {},
                    'compare': {
                        'quantity': quantity,
                        'min_price': min_price,
                        'max_price': max_price,
                    },
                }

        # ---------------------------------------------------------------------
        # Compare
        # ---------------------------------------------------------------------
        if dump_data.get('from_industrial') != \
                dump_compare_data.get('from_industrial'):
            bg_color_1 = 'blue'
        else:
            bg_color_1 = 'black'
        if dump_data.get('to_industrial') != \
                dump_compare_data.get('to_industrial'):
            bg_color_2 = 'blue'
        else:
            bg_color_2 = 'black'

        compare += 'Range di prezzo storico: ' \
                   '[<b>%s</b> - <b>%s</b>] <br/>' \
                   'Range di prezzo attuale: ' \
                   '[<span style="color:%s"><b>%s</b></span> - ' \
                   ' <span style="color:%s"><b>%s</b></span>] <br/>' % (
                        dump_data.get('from_industrial'),
                        dump_data.get('to_industrial'),
                        bg_color_1,
                        dump_compare_data.get('from_industrial'),
                        bg_color_2,
                        dump_compare_data.get('to_industrial'),
                        )

        compare += '<table width="100%" border="1">'
        compare += '<tr>' \
            '<th bgcolor="#bcbcbc" colspan="5" style="text-align:center;">' \
            'Dettaglio</th>' \
            '<th bgcolor="#bcbcbc" colspan="3" style="text-align:center;">' \
            'Storico</th>' \
            '<th bgcolor="#bcbcbc" colspan="3" style="text-align:center;">' \
            'Attuale</th></tr>'

        compare += '<tr>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Categoria</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Semilavorato' \
            '</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Nome</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Codice</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Nome</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Q.</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Min</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Max</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Q.</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Min</th>' \
            '<th bgcolor="#bcbcbc" style="text-align:center;">Max</th>' \
            '</tr>'

        # Differnce in q, min or max
        parameters_error = {
            'bgcolor': self.colors['orange'],
            # 'color': 'blue',
        }
        for key in sorted(mixed_data):
            record = mixed_data[key]

            status = record.get('status')
            semiproduct = record.get('semiproduct')
            product = record.get('product')
            history_block = record.get('history')
            compare_block = record.get('compare')

            # -----------------------------------------------------------------
            # Color parameters:
            # -----------------------------------------------------------------
            parameters = {
                'bgcolor': self.colors[status],
                }
            if not history_block.get('min_price') or not \
                    history_block.get('max_price'):
                parameters['bgcolor'] = self.colors['error']
                parameters['title'] = 'Prezzo minimo o massimo non presente'

            difference = {}
            for field in ('quantity', 'min_price', 'max_price'):
                difference[field] = (
                    history_block.get(field) and compare_block.get(field) and
                    compare_block.get(field) != history_block.get(field))

            compare += '<tr>%s%s%s%s%s%s%s%s%s%s%s</tr>' % (
                    self.get_html_tag(
                        record.get('category'),
                        parameters=parameters,
                        ),

                    self.get_html_tag(
                        semiproduct.default_code if semiproduct else '',
                        parameters=parameters,
                        ),
                    self.get_html_tag(
                        semiproduct.name if semiproduct else '',
                        parameters=parameters,
                        ),

                    self.get_html_tag(
                        product.default_code if product else '',
                        parameters=parameters,
                        ),
                    self.get_html_tag(
                        product.name if product else '',
                        parameters=parameters,
                        ),

                    self.get_html_tag(
                        history_block.get('quantity'),
                        parameters=parameters,
                        ),
                    self.get_html_tag(
                        history_block.get('min_price'),
                        parameters=parameters,
                        ),
                    self.get_html_tag(
                        history_block.get('max_price'),
                        parameters=parameters,
                        ),

                    self.get_html_tag(
                        compare_block.get('quantity'),
                        parameters=parameters_error if difference['quantity']
                        else parameters,
                        ),
                    self.get_html_tag(
                        compare_block.get('min_price'),
                        parameters=parameters_error if difference['min_price']
                        else parameters,
                        ),
                    self.get_html_tag(
                        compare_block.get('max_price'),
                        parameters=parameters_error if difference['max_price']
                        else parameters,
                        ),
                    )
        compare += '</table>'
        return history, compare

    def _get_dump_data(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            dump_html, dump_compare_html = self.dump_data_in_html(
                cr, uid, record.dump_data, record.product_id.dump_data,
                context=context)
            res[record.id] = {
                'dump_html': dump_html,
                'dump_compare_html': dump_compare_html,
            }
        return res

    _columns = {
        'product_id': fields.many2one('product.product', 'Prodotti'),
        'dump_data': fields.text(
            'Dump data',
            help='File di dump ultima distinta controllata dal responsabile'),
        'dump_user_id': fields.many2one(
            'res.users', 'Controllore DB',
            help='Responsabile che ha controllato e storicizzato la DB'),
        'dump_datetime': fields.datetime(
            'Data controllo',
            help='Data e ora della storicizzazione ultima distinta controllata'
                 'dal responsabile'),
        'dump_html': fields.function(
            _get_dump_data, method=True, type='text', string='DB storica',
            multi=True),
        'dump_compare_html': fields.function(
            _get_dump_data, method=True, type='text', string='DB comparata',
            multi=True),
        }


class ProductProduct(orm.Model):
    """ Model name: ProductProduct add utility for report
    """

    _inherit = 'product.product'

    _columns = {
        'dump_data': fields.text(
            'Dump data',
            help='File di dump ultima distinta controllata dal responsabile'),
        'dump_user_id': fields.many2one(
            'res.users', 'Controllore DB',
            help='Responsabile che ha controllato e storicizzato la DB'),
        'dump_datetime': fields.datetime(
            'Data controllo',
            help='Data e ora della storicizzazione ultima distinta controllata'
                 'dal responsabile'),
        }

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def get_medea_data(self, value):
        return ''

    def open_single_report(self, cr, uid, ids, context=None):
        """ Return single report
        """
        datas = {}
        datas['wizard'] = True  # started from wizard
        datas['active_ids'] = ids
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report',
            'datas': datas,
            # 'context': context,
            }

    def open_single_report_with_dump(self, cr, uid, ids, context=None):
        """ Return single report
        """
        datas = {}
        datas['wizard'] = True  # started from wizard
        datas['active_ids'] = ids
        datas['json_history'] = 'locked'
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report',
            'datas': datas,
            # 'context': context,
            }

    def open_history_dump(self, cr, uid, ids, context=None):
        """ History dump list
        """
        # model_pool = self.pool.get('ir.model.data')
        view_id = False  # model_pool.get_object_reference(
        # cr, uid, 'auto_bom_tx_report', 'view_order_line_tree')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('DB Storicizzate'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': 1,
            'res_model': 'product.product.bom.dump',
            'view_id': view_id,
            'views': [(view_id, 'tree'), (view_id, 'form')],
            'domain': [('product_id', '=', ids[0])],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
        }

    def open_single_report_with_compare_dump(self, cr, uid, ids, context=None):
        """ Return single report (not launched from interface but from code)
        """
        datas = {}
        datas['wizard'] = True  # started from wizard
        datas['active_ids'] = ids
        datas['json_history'] = 'compare'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report',
            'datas': datas,
            # 'context': context,
            }

    def compare_locked_bom_dump(self, cr, uid, ids, context=None):
        """ Compare procedure for check locked bom and this
        """
        for product in self.browse(cr, uid, ids, context=context):
            # todo call compare report for store before?
            locked = pickle.loads(product.dump_data)
            compare = pickle.loads(product.dump_compare_data)
        return True

    def open_multi_report(self, cr, uid, ids, context=None):
        """ Return multi report
        """
        datas = {}
        datas['wizard'] = True # started from wizard
        datas['active_ids'] = False
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'industrial_cost_bom_report',
            'datas': datas,
            # 'context': context,
            }

    def open_xls_report(self, cr, uid, ids, context=None):
        """ Return xls report extracted from get_object method
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def xls_write_row(WS, row, row_data, format_cell):
            """ Print line in XLS file
            """
            ''' Write line in excel file
            '''
            col = 0
            for item in row_data:
                WS.write(row, col, item, format_cell)
                col += 1
            return True

        datas = {}
        datas['wizard'] = True  # started from wizard
        datas['active_ids'] = False

        xls_filename = '/tmp/bom_report.xlsx'
        _logger.info('Start export BOM cost on %s' % xls_filename)

        # Open file and write header
        ws_name = ('Prezzi DB %s' % datetime.now())[:10]
        WB = xlsxwriter.Workbook(xls_filename)
        WS = WB.add_worksheet(ws_name)

        # Format:
        format_title = WB.add_format({
            'bold': True,
            'font_color': 'black',
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': 'gray',
            'border': 1,
            'text_wrap': True,
            })

        format_text = WB.add_format({
            'font_name': 'Arial',
            # 'align': 'left',
            'font_size': 9,
            'border': 1,
            })

        format_white = WB.add_format({
            'font_name': 'Arial',
            'font_size': 9,
            'align': 'right',
            'bg_color': 'white',
            'border': 1,
            'num_format': '0.00',
            })

        # ---------------------------------------------------------------------
        # Get database of industrial cost:
        # ---------------------------------------------------------------------
        cost_db = {}
        cost_pool = self.pool.get('mrp.bom.industrial.cost')
        cost_ids = cost_pool.search(cr, uid, [], order='name', context=context)
        i = 0
        for cost in cost_pool.browse(cr, uid, cost_ids, context=context):
            cost_db[cost.name] = i  # position in Excel file
            i += 1

        # ---------------------------------------------------------------------
        # Setup excel layout and columns:
        # ---------------------------------------------------------------------
        WS.set_column('A:A', 10)
        WS.set_column('B:B', 35)
        WS.set_column('C:AX', 10)

        header = [
            _('Codice'),
            _('Descrizione'),
            _('Min'),
            _('Max'),
            _('Simul.'),
            _('Simul. %'),
            _('Costo (anag.)'),

            _('Marg. A'),
            _('Marg B.'),
            _('P.d.V. (anag.)'),

            _('Prezzo non presente'),
            ]
        header.extend(sorted(cost_db, key=lambda x: cost_db[x]))
        xls_write_row(WS, 0, header, format_title)

        # ---------------------------------------------------------------------
        # Get product cost information
        # ---------------------------------------------------------------------
        # Extract data from ODT master function:
        row = 0
        for (r_min, r_max, r_error, r_components, r_extra1, r_extra2, r_index,
             r_total, product, r_parameter, r_total_text, pipe_data,
             simulated_cost) in self.report_get_objects_bom_industrial_cost(
                    cr, uid, datas=datas, context=context):
            row += 1

            if r_max:
                simulated_rate = 100 * (simulated_cost - r_max) / r_max
            else:
                simulated_rate = '/'

            # Default data:
            row_data = [
                product.default_code,
                product.name,

                # Cost:
                r_min,
                r_max,
                simulated_cost,
                simulated_rate,
                product.standard_price,

                # Revenue:
                r_total['margin_a'],
                r_total['margin_b'],
                product.lst_price,

                'X' if r_error else '',
                ]

            # Extra column for costs:
            industrial_cost = [0.0 for col in range(0, len(cost_db))]

            # Loop on 2 cost table (industrial cost):
            for table in (r_extra1, r_extra2):
                for item, details, time_qty in table:
                    if time_qty:
                        industrial_cost[cost_db[item.cost_id.name]] = \
                            '%s (T. %s)' % (details, time_qty)
                    else:
                        industrial_cost[cost_db[item.cost_id.name]] = details

            # -----------------------------------------------------------------
            # Print XLS row data:
            # -----------------------------------------------------------------
            row_data.extend(industrial_cost)
            xls_write_row(WS, row, row_data, format_text)
        _logger.info('End export BOM cost on %s' % xls_filename)
        WB.close()

        attachment_pool = self.pool.get('ir.attachment')
        b64 = open(xls_filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'BOM industrial cost',
            'datas_fname': 'bom_industrial_cost_report.xlsx',
            'type': 'binary',
            'datas': b64,
            'partner_id': 1,
            'res_model': 'res.partner',
            'res_id': 1,
            }, context=context)

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/saveas?model=ir.attachment&field=datas&'
                   'filename_field=datas_fname&id=%s' % attachment_id,
            'target': 'self',
            }

    # -------------------------------------------------------------------------
    # Report utility:
    # -------------------------------------------------------------------------
    def _report_industrial_get_objects(self, cr, uid, data=None, context=None):
        """ Return single report or list of selected bom
            Used in report and in XLSX extract files
        """
        # Readability:
        if data is None:
            data = {}

        if not data.get('wizard', False):
            raise osv.except_osv(
                _('Access error'),
                _('No right to print BOM'),
                )

        active_ids = data.get('active_ids', False)
        if not active_ids:
            active_ids = self.search(cr, uid, [
                ('bom_selection', '=', True),
                ], context=context)
        objects = self.browse(cr, uid, active_ids, context=context)

        return sorted(objects, key=lambda o: o.default_code)

    def report_get_objects_bom_industrial_cost(
            self, cr, uid, datas=None, context=None):
        """ Report action for generate database used (both ODT and XLSX export)
        """
        def get_simulated(value, supplier, product, simulation_db):
            """ Simulation price for now use max value)
            """
            default_code = product.default_code or ''
            for param in simulation_db:
                rule_supplier = param.supplier_id
                start = param.name

                if rule_supplier == supplier or (
                        start and default_code.startswith(start)):
                    if param.mode == 'rate':
                        value *= (100.0 + param.value) / 100.0
                    elif param.mode == 'fixed':
                        value = param.value
                    else:
                        value += param.value
                    break
            return value

        def get_pipe_material_price(material_price_db, cmpt, reference_year):
            """ Extract pipe price also in previous period
            """
            material_id = cmpt.product_id.pipe_material_id.id
            return material_price_db.get(
                material_id, {}).get(reference_year) or 0.0

        if datas is None:
            datas = {}

        # ---------------------------------------------------------------------
        # Parameters in datas dictionary:
        # ---------------------------------------------------------------------
        dump_pool = self.pool.get('product.product.bom.dump')

        simulation_db = []
        simulation_pool = self.pool.get('mrp.bom.industrial.simulation')
        simulation_ids = simulation_pool.search(cr, uid, [], context=context)
        for simulation in simulation_pool.browse(
                cr, uid, simulation_ids, context=context):
            simulation_db.append(simulation)

        # Material history price if needed:
        material_price_db = {}
        material_price_pool = self.pool.get('product.pipe.material.history')
        material_price_ids = material_price_pool.search(
            cr, uid, [], context=context)
        for material_price in material_price_pool.browse(
                cr, uid, material_price_ids, context=context):
            material = material_price.material_id
            material_id = material.id
            if material_id not in material_price_db:
                material_price_db[material_id] = {}
            material_price_db[material_id][material_price.year] = \
                material_price.last_price

        # Need update record price:
        update_record = datas.get('update_record', False)
        if update_record:
            _logger.warning('Product price will save in history!')
        else:
            _logger.warning('No product price updated!')

        update_current_industrial = datas.get(
            'update_current_industrial', False)
        if update_current_industrial:
            _logger.warning('Product price current will be updated!')
        else:
            _logger.warning('No current product price updated!')
        update_after = []

        # Note: used pickle for better read in python non JSON
        json_history = datas.get('json_history', False)
        # Json history save locked version of dump BOM
        # Json compare history saved version just for compare with original
        # locked
        if json_history:
            _logger.warning('Status BOM will saved in Dump data (%s)!' %
                            json_history)
        else:
            _logger.warning('Status BOM Dump data not saved!')

        # Range date:
        from_date = datas.get('from_date', '')
        to_date = datas.get('to_date', '')
        reference_year = to_date[:4]
        _logger.warning('Reference year for pipe price: %s' % reference_year)

        # ---------------------------------------------------------------------
        # Load history database if to_date range is setup:
        # ---------------------------------------------------------------------
        history_db = {}
        if to_date:
            _logger.warning(
                'Max date mode so read also history: %s!' % to_date)

            # Load history database not empty with range passed:
            history_pool = self.pool.get('pricelist.partnerinfo.history')
            history_ids = history_pool.search(cr, uid, [
                # ('date_quotation', '>=', from_date),
                # ('date_quotation', '<=', to_date),
                ('price', '>', 0),
                ], context=context)

            for history in sorted(history_pool.browse(
                    cr, uid, history_ids, context=context),
                    key=lambda x: x.date_quotation or x.write_date,
                    reverse=True):
                date_quotation = history.date_quotation or \
                    history.write_date[:10]
                if not date_quotation or \
                        date_quotation < from_date or \
                        date_quotation > to_date:
                    continue  # External date or not present

                product = history.pricelist_id.product_id

                default_code = product.default_code
                if default_code in history_db:
                    continue  # old price

                if product.bom_industrial_no_price:  # todo remove? dont' work
                    price = 0.0
                else:
                    price = history.price
                history_db[default_code] = (
                    history.pricelist_id.supplier_id,  # Seller name
                    price,  # Price
                    date_quotation,  # Date
                    )
        else:
            _logger.warning('No max date limit!')

        res = []
        selected_product = self._report_industrial_get_objects(
            cr, uid, data=datas, context=context)
        if selected_product:
            margin_a = \
                selected_product[0].company_id.industrial_margin_a
            margin_b = \
                selected_product[0].company_id.industrial_margin_b
            # todo manage extra:
            margin_extra = \
                selected_product[0].company_id.industrial_margin_extra

            # Min date limit:
            if from_date:
                _logger.warning(
                    'Min date limit from wizard: %s!' % from_date)

            else:
                days = selected_product[0].company_id.industrial_days or 500
                from_date = (datetime.now() - timedelta(days=days)).strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
                _logger.warning(
                    'Min date limit from parameter [%s]: %s!' % (
                        days,
                        from_date,
                        ))

            parameter = _(
                'Parametri: Margine A: %s%% - Margine B: %s%% - '
                'Margine extra: %s%% Giorni min rif. prezzi %s') % (
                    margin_a,
                    margin_b,
                    margin_extra,
                    from_date,
                    )
        else:
            return res  # No selection return empty records

        component_f = open(os.path.expanduser('~/component.txt'), 'w')
        component_saved = []
        for product in selected_product:
            # History:
            if json_history:
                # Manage history in pickle field
                dump_data = {
                    'product': [],
                }  # Clean every new product

            data = [
                0.0,  # 0. Min
                0.0,  # 1. Max
                False,  # 2. Error
                [],  # 3. Component data
                [],  # 4. Extra cost (1) industrial
                [],  # 5. Extra cost (2) work
                {},  # 6. Index (total for calculate index)
                {},  # 7. Total (margin element)
                product,  # 8. Product browse
                '',   # 9. Parameter of report
                '',  # 10. Total text
                [0.0, 0.0],  # 11. Pipe weight total (q, total)
                0.0,  # 12. Simulated price
                ]

            # -----------------------------------------------------------------
            # Load component list (and subcomponent for HW):
            # -----------------------------------------------------------------
            for item in product.dynamic_bom_line_ids:
                category_name = item.category_id.name or ''
                component = item.product_id
                if component.bom_placeholder or component.bom_alternative:
                    _logger.warning('Jump placeholder elements')
                    continue  # jump component

                half_bom_ids = component.half_bom_ids  # if half component
                if half_bom_ids:   # HW component (level 2 and Frame!)
                    hw_total = 0.0
                    for master_cmpt in half_bom_ids:
                        # -----------------------------------------------------
                        # Manage 3 level BOM:
                        # -----------------------------------------------------
                        if master_cmpt.product_id.half_bom_ids:
                            extra_reference = ' [%s]' % (
                                master_cmpt.product_id.default_code)
                            cmpt_loop = master_cmpt.product_id.half_bom_ids
                        else:
                            extra_reference = ''
                            cmpt_loop = [master_cmpt]

                        for cmpt in cmpt_loop:
                            # last_date = False # TODO last price?
                            cmpt_q = item.product_qty * cmpt.product_qty  # XXX

                            # Simulation:
                            (min_value, max_value, price_ids, supplier_min,
                             supplier_max) = get_pricelist(
                                cmpt.product_id, from_date, to_date,
                                history_db)
                            simulated_cost = cmpt_q * get_simulated(
                                max_value, supplier_max, cmpt.product_id,
                                simulation_db)
                            price_detail = get_price_detail(price_ids)

                            # Fabric element:
                            is_fabric = is_fabric_product(cmpt.product_id)
                            uom_name = cmpt.product_id.uom_id.name
                            fabric_text = ''
                            if is_fabric:
                                fabric_text = '(MQ: %8.5f EUR/MQ: %8.5f)' % (
                                    cmpt_q * is_fabric,
                                    max_value / is_fabric,
                                    )

                            # Pipe element:
                            if cmpt.product_id.is_pipe:
                                # Calc with weight and price kg not cost mng.:
                                # todo Simulation:
                                if reference_year:
                                    pipe_price = get_pipe_material_price(
                                        material_price_db, cmpt,
                                        reference_year)
                                else:
                                    pipe_price = \
                                        cmpt.product_id.pipe_material_id.\
                                            last_price

                                min_value = max_value = \
                                    pipe_price * cmpt.product_id.weight
                                # Total pipe weight:
                                q_pipe = item.product_qty * cmpt.product_qty *\
                                    cmpt.product_id.weight

                                simulated_cost = q_pipe * get_simulated(
                                    pipe_price, supplier_max, cmpt.product_id,
                                    simulation_db)

                                data[11][0] += q_pipe
                                data[11][1] += q_pipe * pipe_price

                            # todo manage as pipe?
                            red_price = \
                                not cmpt.product_id.bom_industrial_no_price \
                                and not max_value
                            if cmpt.product_id.bom_industrial_no_price:
                                min_value = max_value = 0.0  # no price in BOM

                            record = [
                                '%s - %s%s' % (
                                    cmpt.product_id.default_code or '',
                                    cmpt.product_id.name or '',
                                    extra_reference,
                                    ),
                                cmpt_q,  # q. total
                                uom_name,  # UOM
                                max_value,  # unit price (max not the last!)
                                max_value * cmpt_q,  # subt. (last = unit x q)
                                price_detail,  # list of price, used for detail
                                component,  # HW product
                                cmpt.product_id,  # Product for extra data
                                red_price,  # no price
                                fabric_text,  # fabric text for price
                                simulated_cost,
                                ]

                            if red_price:
                                data[2] = True  # This product now is in error!

                            # Update min and max value:
                            data[0] += min_value * cmpt_q
                            data[1] += max_value * cmpt_q
                            data[12] += simulated_cost

                            if component.default_code not in component_saved:
                                hw_total += max_value * cmpt_q
                                component_f.write('%-30s|%25.5f\r\n' % (
                                    component.default_code,
                                    hw_total,
                                    ))
                                component_saved.append(component.default_code)

                            data[3].append(record)  # Populate product database

                            # History:
                            if json_history:
                                dump_data['product'].append({
                                    'category': category_name,
                                    # only here:
                                    'semiproduct_id': component.id,
                                    'product_id': cmpt.product_id.id,

                                    'default_code':
                                        cmpt.product_id.default_code,
                                    'semiproduct': '%s%s' % (
                                        component.default_code,
                                        extra_reference,
                                        ),
                                    'quantity': cmpt_q,  # item x component
                                    # 'uom': uom_name,
                                    'min_price': min_value,
                                    'max_price': max_value,
                                    # simulated?
                                })

                else:  # Raw material (level 1)
                    cmpt_q = item.product_qty
                    # Simulation:
                    (min_value, max_value, price_ids, supplier_min,
                     supplier_max) = get_pricelist(
                        item.product_id, from_date, to_date, history_db)
                    simulated_cost = cmpt_q * get_simulated(
                        max_value, supplier_max, item.product_id,
                        simulation_db)
                    price_detail = get_price_detail(price_ids)

                    red_price = \
                        not component.bom_industrial_no_price and not max_value
                    if component.bom_industrial_no_price:
                        min_value = max_value = 0.0
                    data[3].append([
                        '%s - %s' % (
                            component.default_code or '',
                            component.name or '',
                            ),
                        cmpt_q,  # q. total
                        component.uom_id.name,  # UOM
                        max_value,  # unit price (max not the last!)
                        max_value * cmpt_q,  # subtotal
                        price_detail,  # list of price (used for detail),
                        False,  # HW product (not here)
                        component,  # Product for extra data
                        red_price,  # Prod with no price
                        '',  # fabric text for price
                        simulated_cost,  # Simulated price
                        ])  # Populate product database

                    if red_price:
                        data[2] = True  # This product now is in error!

                    data[0] += min_value * cmpt_q
                    data[1] += max_value * cmpt_q
                    data[12] += simulated_cost

                    # History:
                    if json_history:
                        dump_data['product'].append({
                            'category': category_name,
                            'product_id': component.id,
                            'default_code': component.default_code,
                            'semiproduct': False,
                            'semiproduct_id': False,
                            'quantity': cmpt_q,  # item x component
                            # 'uom': uom_name,
                            'min_price': min_value,
                            'max_price': max_value,
                            # simulated?
                        })

            # Add extra (save in total the max)
            data[0] += data[0] * margin_extra / 100.0
            margin_extra_value = data[1] * margin_extra / 100.0

            data[12] += data[12] * margin_extra / 100.0

            # Update total text:
            data[10] += '%10.5f +%10.5f' % (
                data[1],
                margin_extra_value,
                )

            data[1] += margin_extra_value

            # -----------------------------------------------------------------
            # Extra data end report:
            # -----------------------------------------------------------------
            data[6] = {  # Index
                _('component'): data[1],  # used max:
                }
            for cost, item in self.get_cost_industrial_for_product(
                    cr, uid, [product.id], context=context).iteritems():

                # Index total:
                if cost.type not in data[6]:
                    data[6][cost.type] = 0.0

                # 2 case: with product or use unit_cost
                if item.product_id:  # use item price
                    value = item.qty * item.last_cost
                    time_qty = False
                else:
                    value = item.qty * cost.unit_cost
                    time_qty = item.qty

                if item.cost_id.name == 'Manodopera MEDEA':
                    value = self.get_medea_data(item.name)
                cost_item = (item or '???', value, time_qty)
                if cost.type == 'industrial':
                    data[5].append(cost_item)
                elif cost.type == 'work':
                    data[4].append(cost_item)
                else:
                    raise osv.except_osv(
                        _('Tipo errato'),
                        _('Tipo di costo non presente: %s') %
                        product.default_code,
                        )

                data[0] += value  # min
                data[1] += value  # max
                data[6][cost.type] += value  # Index total
                data[12] += value  # simulated

            # Save margin parameters:
            data[7]['margin_a'] = data[1] * margin_a / 100.0
            data[7]['margin_b'] = data[1] * margin_b / 100.0

            # Write status in row:
            data[7]['index'] = industrial_index_get_text(data[6])

            # -----------------------------------------------------------------
            # Update product industrial price:
            # -----------------------------------------------------------------
            if update_record:
                update_after.append((product.id, {
                    'from_industrial': data[0],
                    'to_industrial': data[1],
                    'industrial_missed': data[2],
                    'industrial_index': data[7]['index'],
                    }))

            # -----------------------------------------------------------------
            # Update product current industrial price:
            # -----------------------------------------------------------------
            if update_current_industrial:
                update_after.append((product.id, {
                    'current_from_industrial': data[0],
                    'current_to_industrial': data[1],
                    }))

            # -----------------------------------------------------------------
            # History:
            # -----------------------------------------------------------------
            if json_history:
                # Update dump with totals:
                dump_data['from_industrial'] = data[0]
                dump_data['to_industrial'] = data[1]

                if datas['json_history'] == 'locked':
                    # Update with dump and manager data
                    update_after.append((product.id, {
                        'dump_data': pickle.dumps(dump_data),
                        'dump_user_id': uid,
                        'dump_datetime': datetime.now()
                    }))

                    # Only for locked write in history:
                    dump_id = dump_pool.create(cr, uid, {
                        'product_id': product.id,
                        'dump_data': pickle.dumps(dump_data),
                        'dump_user_id': uid,
                        'dump_datetime': datetime.now(),
                    }, context=context)

                    # todo also file PDF?
                else:  # Compare dump
                    # Update with dump only
                    update_after.append((product.id, {
                        'dump_data': pickle.dumps(dump_data),
                    }))

            # Total text:
            # Mat + Extra + Cost1 + Cost2
            for t in type_i18n:
                if t in data[6]:
                    data[10] += ' +%8.5f' % data[6][t]

            # Sort data:
            data[3].sort(key=lambda x: x[0])  # XXX raise error without key
            data[4].sort(key=lambda x: x[0].cost_id.name)  # Table 1
            data[5].sort(key=lambda x: x[0].cost_id.name)  # Table 2
            res.append(data)

        # Update parameters:
        res[0][9] = parameter

        # Update product record after:
        for product_id, record in update_after:
            self.write(cr, uid, product_id, record, context=context)
        return res


class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            'get_date': self.get_date,
            })

    def get_date(self, ):
        """ Return date
        """
        date = '%s' % datetime.now()
        return '%s/%s/%s' % (
            date[8:10],
            date[5:7],
            date[:4],
            )

    def get_objects(self, datas=None):
        """ Return single report or list of selected bom
        """
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}
        product_pool = self.pool.get('product.product')

        return product_pool.report_get_objects_bom_industrial_cost(
            cr, uid, datas=datas, context=context)

