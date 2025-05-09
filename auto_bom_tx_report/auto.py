# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
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


class ProductProduct(orm.Model):
    """ Model name: MrpProduction
    """

    _inherit = 'product.product'

    _columns = {
        'ordered_hw': fields.boolean('Semilavorato ordinato'),

        'old_tcar': fields.integer('Old Tcar'),
        'old_tscar': fields.integer('Old Tscar'),

        'report_minimum_qty': fields.float(
            'Liv. riordino',
            help='Livello di riordino report approvvigionamenti'),
        'report_note': fields.text('Note report'),
        }


class ComponentStatusReportWizard(orm.TransientModel):
    """ Wizard for print status
    """
    _inherit = 'component.status.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_open_report_xlsx(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {
                'lang': 'it_IT',
                }
        mrp_pool = self.pool.get('mrp.production')
        attachment_pool = self.pool.get('ir.attachment')

        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        datas = {
            'mode': wiz_browse.mode,  # 'mode': 'component',
            'mp_mode': wiz_browse.mp_mode,  # 'mp_mode': 'fabric',
            'days': wiz_browse.days,
            'first_supplier_id': wiz_browse.first_supplier_id.id or False,
            # 'negative_start': wiz_browse.negative_start,
            'type_id': False,  # todo remove ex. wiz_browse.type_id.id or
            'with_type_ids':
                [item.id for item in wiz_browse.with_type_ids],
            'without_type_ids':
                [item.id for item in wiz_browse.without_type_ids],
            'with_deadline': wiz_browse.with_deadline,
            'only_negative': wiz_browse.only_negative,
            'exclude_inventory_category':
                wiz_browse.exclude_inventory_category,
            # Report setup:
            # 'model': 'mrp.production',
            # 'active_id': False,
            # 'active_ids': [],
            # 'context': context,
            }

        # Generate excel file:
        filename = mrp_pool.extract_mrp_production_report_xlsx(
            cr, uid, data=datas, context=context)
        _logger.info('Extracted file in %s' % filename)

        # Append stock page here:
        # _logger.info('Integrate stock page in %s' % filename)
        # mrp_pool.integrate_stock_total_page_to_excel(
        #    cr, uid, ids, filename, context=context)

        # Read binary for attach to ir.attachment:
        b64 = open(filename, 'rb').read().encode('base64')
        attachment_id = attachment_pool.create(cr, uid, {
            'name': 'Stato materiali',
            'datas_fname': 'stato_materiali_%s.xlsx' % wiz_browse.mode,
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


class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    _inherit = 'mrp.production'

    def _get_gamma_terms(self, status):
        """ Return translation for terms
        """
        status_translate = {
            'catalog': 'A Catalogo',
            'exit': 'In Uscita',
            'obsolete': 'Obsoleto',
            'used': 'Attivo',
            'kurtz': 'Kurtz',
        }
        return status_translate.get(status, '')

    def where_is_used_component(self, cr, uid, product, context=None):
        """ Check DB where this product is used as component
        """
        bom_line = self.pool.get('mrp.bom.line')
        res = ''

        try:
            # Where component is used:
            line_ids = bom_line.search(cr, uid, [
                ('product_id', '=', product.id),
                ('bom_id.bom_category', 'in', ('parent', 'half', 'dynamic')),
            ], context=context)

            if not line_ids:
                return res

            for line in bom_line.browse(cr, uid, line_ids, context=context):
                if line.dynamic_mask:
                    res += u'[%s]* ' % line.dynamic_mask
                else:  # Parent bom or half
                    bom = line.bom_id
                    bom_product = bom.product_id
                    res += u'[%s] ' % bom_product.default_code or \
                           bom_product.name
        except:
            _logger.error('Error searching BOM where it is used!')
        return res

    # todo MOVE IN MODULE? used also from component auto report
    def extract_mrp_production_report_xlsx(self, cr, uid, data=None, context=None):
        """ Extract data from report and put in excel mode
        """
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def write_xls_list_line(WS, row, line, col=0):
            """ Write line in excel file
            """
            for record in line:
                if len(record) == 2:  # Normal text, format
                    WS.write(row, col, *record)
                else:  # Rich format
                    WS.write_rich_string(row, col, *record)
                col += 1
            return True

        def get_xls_format(mode=False, WB=None):
            """ Database for format cells
                first call is with mode not present and WB passed
                next call with only mode
            """
            if not mode or not self.xls_format_db:
                self.xls_format_db = {
                    'title': WB.add_format({
                        'bold': True,
                        'font_name': 'Courier 10 pitch',
                        'font_size': 11,
                        'align': 'left',
                        }),
                    'header': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',  # 'Arial'
                        'font_size': 9,
                        'align': 'center',
                        'valign': 'vcenter',
                        'bg_color': '#cfcfcf',  # gray
                        'border': 1,
                        # 'text_wrap': True,
                        }),
                    'header_extra': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',  # 'Arial'
                        'font_size': 9,
                        'align': 'center',
                        'valign': 'vcenter',
                        'bg_color': '#808080',  # gray dark
                        'border': 1,
                        # 'text_wrap': True,
                        }),
                    'text': WB.add_format({
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'text_center': WB.add_format({
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'center',
                        'border': 1,
                        }),

                    # ---------------------------------------------------------
                    # With text color:
                    # ---------------------------------------------------------
                    'bg_red': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': '#FF6500',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'bg_yellow': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': '#FFFF01',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'bg_green': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': '5FCE03',  # '#A7F2B4',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'bg_blue': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': 'BED0F5',  # '#4F8DD8',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'hide': WB.add_format({
                        'bold': False,
                        'font_color': 'white',
                        'bg_color': '#FFFFFF',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 6,
                        'align': 'left',
                        'border': 1,
                        }),
                    'bg_order': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': '#cc9900',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'right',
                        'border': 1,
                        'num_format': num_format,
                        }),
                    'bg_no_order': WB.add_format({
                        'bold': True,
                        'font_color': 'white',
                        'bg_color': '#000000',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'right',
                        'border': 1,
                        'num_format': num_format,
                    }),

                    # ---------------------------------------------------------
                    # With text color:
                    # ---------------------------------------------------------
                    'text_black': WB.add_format({
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        'text_wrap': True
                        }),
                    'text_blue': WB.add_format({
                        'font_color': 'blue',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        'text_wrap': True
                        }),
                    'text_red': WB.add_format({
                        'font_color': '#ff420e',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        'text_wrap': True
                        }),
                    'text_green': WB.add_format({
                        'font_color': '#328238',  # #99cc66
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        'text_wrap': True
                        }),

                    'text_grey': WB.add_format({
                        'font_color': '#eeeeee',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),
                    'text_wrap': WB.add_format({
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        'text_wrap': True,
                        }),

                    'text_bg_yellow': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'bg_color': '#ffff99',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'border': 1,
                        }),

                    'number': WB.add_format({
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'right',
                        'border': 1,
                        'num_format': num_format,
                        }),
                    'number_blue': WB.add_format({
                        'font_color': 'blue',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'right',
                        'border': 1,
                        'num_format': num_format,
                        }),
                    'text_total': WB.add_format({
                        'bold': True,
                        'font_color': 'black',
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'left',
                        'bg_color': '#DDDDDD',
                        'border': 1,
                        # 'text_wrap': True,
                        }),
                    'number_total': WB.add_format({
                        'bold': True,
                        'font_name': 'Courier 10 pitch',
                        'font_size': 9,
                        'align': 'right',
                        'bg_color': '#DDDDDD',
                        'border': 1,
                        'num_format': num_format,
                        }),
                }
            return self.xls_format_db.get(mode, False)

        def write_xls_block_line(WS, row, line):
            """ Write line block for fabric, return new row position
            """
            # -----------------------------------------------------------------
            # Extract element from line:
            # -----------------------------------------------------------------
            (inv, tcar, tscar, mm, oc, of, sal, o, category, hw, hw_total, purchase, inventory_category) = line

            # 1. Hide not active product:
            if not o.active:
                return row

            # 2. Jump pipes:
            if category == 'Pipes':
                return row  # same row

            # 3. Check DB where is used this component
            # Note external reference for cr, uid, context
            db_comment = self.where_is_used_component(cr, uid, o, context)

            # -----------------------------------------------------------------
            #                            ROW 0
            # -----------------------------------------------------------------
            gamma_status = self._get_gamma_terms(o.status)
            status_filter = (
                gamma_status,
                get_xls_format('hide'),
            )
            format_white = get_xls_format('text')

            # Merge cell:
            WS.merge_range(row, 0, row, 13, '')
            WS.merge_range(row, 16, row, 19, '')  # Inventory category
            WS.merge_range(row, 20, row, 22, '')  # Not order status

            # todo add extra color here!
            if sal[11] < 0:
                format_text = get_xls_format('bg_red')
                color = 'Rosso'
            elif sal[11] < o.report_minimum_qty:
                format_text = get_xls_format('bg_yellow')
                color = 'Giallo'
            else:
                format_text = get_xls_format('bg_green')
                color = 'Verde'
            filter_color = (color, get_xls_format('hide'))

            line0 = [
                ('%s - %s (forn. abit.: %s) %s' % (
                    o.name,
                    o.colour,
                    o.recent_supplier_id.name or o.first_supplier_id or '',
                    purchase,
                    ), format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),

                ('', format_white),
                ('', format_white),

                (inventory_category, format_text),
                ('', format_text),
                ('', format_text),
                ('', format_text),
                ('CON ORDINI' if any(oc) else 'SENZA ORDINI', format_text),
                ('', format_text),
                ('', format_text),
                (gamma_status, format_text),
                status_filter,
                filter_color,
            ]
            write_xls_list_line(WS, row, line0)
            row += 1

            # -----------------------------------------------------------------
            #                            ROW 1
            # -----------------------------------------------------------------
            format_header = get_xls_format('header')
            format_number = get_xls_format('number')

            # Merge cell:
            WS.merge_range(row, 0, row, 1, '')  # Code
            WS.merge_range(row, 16, row, 23, '')  # Interline

            # Create row data:
            line1 = [
                ('%s' % o.default_code, format_header),
                ('', format_header),
                ('Set.', format_header),
                ('Ott.', format_header),
                ('Nov.', format_header),
                ('Dic.', format_header),
                ('Gen.', format_header),
                ('Feb.', format_header),
                ('Mar.', format_header),
                ('Apr.', format_header),
                ('Mag.', format_header),
                ('Giu.', format_header),
                ('Lug.', format_header),
                ('Ago.', format_header),

                ('', format_white),
                ('', format_white),

                ('DB: %s' % db_comment, format_header),  # DB where is used!
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                status_filter,
                filter_color,
                ]
            write_xls_list_line(WS, row, line1)
            row += 1

            # -----------------------------------------------------------------
            #                            ROW 2
            # -----------------------------------------------------------------
            WS.merge_range(row, 16, row, 23, '')  # Extra table header

            format_text = get_xls_format('text')
            format_header_extra = get_xls_format('header_extra')

            # Create row data:
            line2 = [
                ('Inv. %s: %s' % (
                    o.mx_start_date or '', inv), format_text),
                ('MM', get_xls_format('text_center')),
                (mm[0], format_number),
                (mm[1], format_number),
                (mm[2], format_number),
                (mm[3], format_number),
                (mm[4], format_number),
                (mm[5], format_number),
                (mm[6], format_number),
                (mm[7], format_number),
                (mm[8], format_number),
                (mm[9], format_number),
                (mm[10], format_number),
                (mm[11], format_number),

                ('', format_white),
                ('', format_white),

                ('Dettagli extra', format_header_extra),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                ('', format_header),
                status_filter,
                filter_color,
                ]
            write_xls_list_line(WS, row, line2)
            row += 1

            # -----------------------------------------------------------------
            #                            ROW 3
            # -----------------------------------------------------------------
            old_tscar = ' (%s)' % o.old_tscar if o.old_tscar else ''
            line3 = [
                ('Tot. Scar.: %s%s' % (tscar, old_tscar), format_text),
                ('OC', get_xls_format('text_center')),
                (oc[0], format_number),
                (oc[1], format_number),
                (oc[2], format_number),
                (oc[3], format_number),
                (oc[4], format_number),
                (oc[5], format_number),
                (oc[6], format_number),
                (oc[7], format_number),
                (oc[8], format_number),
                (oc[9], format_number),
                (oc[10], format_number),
                (oc[11], format_number),

                ('', format_white),
                ('', format_white),

                ('', format_header),
                ('Leadtime', format_header),
                ('Lotto', format_header),
                ('Categ. invent.', format_header),
                ('Stato', format_header),
                ('Liv. riord.', format_header),
                ('Note', format_header),
                ('Valore mag.', format_header),
                status_filter,
                filter_color,
                ]
            write_xls_list_line(WS, row, line3)
            row += 1

            # -----------------------------------------------------------------
            #                            ROW 4
            # -----------------------------------------------------------------
            text_center = get_xls_format('text_center')

            # 1. Stock value end season:
            stock_value = 0.0
            try:
                if sal[11] > 0 and purchase:
                    stock_value = sal[11] * float(
                        purchase.split(']')[0].split(' ')[-1])
            except:
                pass  # remain 0

            # 2. Old T. Car.
            old_tcar = ' (%s)' % o.old_tcar if o.old_tcar else ''

            line4 = [
                ('Tot. Car.: %s%s' % (tcar, old_tcar), format_text),
                ('OF', get_xls_format('text_center')),
                (of[0], format_number),
                (of[1], format_number),
                (of[2], format_number),
                (of[3], format_number),
                (of[4], format_number),
                (of[5], format_number),
                (of[6], format_number),
                (of[7], format_number),
                (of[8], format_number),
                (of[9], format_number),
                (of[10], format_number),
                (of[11], format_number),

                ('', format_white),
                ('', format_white),

                ('Attuale', format_header),
                (o.leadtime or 0, text_center),
                (o.purchase_lot_block or 0, text_center),
                (inventory_category, text_center),
                (gamma_status, text_center),
                (o.report_minimum_qty, text_center),
                (o.report_note or '', text_center),
                (stock_value, format_number),
                status_filter,
                filter_color,
                ]
            write_xls_list_line(WS, row, line4)

            # Add comment:
            if o.report_note:
                WS.write_comment(
                    xl_rowcol_to_cell(row, 22),
                    o.report_note or '',
                )
            WS.write_comment(
                xl_rowcol_to_cell(row, 23),
                'Cliccare sulla colonna X per vedere il totale del foglio'
                '(valorizzazione fatta con prezzo ultimo doc. di acquisto)',
            )

            row += 1

            # -----------------------------------------------------------------
            #                            ROW 5
            # -----------------------------------------------------------------
            format_text_blue = get_xls_format('bg_blue')

            line5 = [
                ('Mag.: %s' % o.mx_net_mrp_qty, get_xls_format(
                    'text_bg_yellow')),
                ('SAL', get_xls_format('text_center')),
                (sal[0], format_number),
                (sal[1], format_number),
                (sal[2], format_number),
                (sal[3], format_number),
                (sal[4], format_number),
                (sal[5], format_number),
                (sal[6], format_number),
                (sal[7], format_number),
                (sal[8], format_number),
                (sal[9], format_number),
                (sal[10], format_number),
                (sal[11], format_number),

                ('', format_white),
                ('', format_white),

                ('Nuovo', format_header),
                ('', format_text_blue),
                ('', format_text_blue),
                ('', format_text_blue),
                ('', format_text_blue),
                ('', format_text_blue),
                ('', format_text_blue),
                ('', format_number),
                status_filter,
                filter_color,
                ]
            write_xls_list_line(WS, row, line5)

            # Add comment:
            WS.write_comment(
                xl_rowcol_to_cell(row, 19),
                'Utilizzare i nomi dei fogli per scegliere la nuova categoria',
            )
            WS.write_comment(
                xl_rowcol_to_cell(row, 20),
                '[O=Obsoleto] [C=Catalogo] [U=Uscente] [K=Kurtz]\n'
                '[A=Attivo (in uso)]',
            )
            WS.write_comment(
                xl_rowcol_to_cell(row, 21),
                'Indicare la q. di riordino (se va sotto tale valore la '
                'la testata della tabella diventa gialla)',
            )

            # -----------------------------------------------------------------
            #                            Order line:
            # -----------------------------------------------------------------
            row += 1
            try:
                if o.status in ('obsolete', 'exit'):
                    order_text = 'Non ordinare:'
                    format_order = get_xls_format('bg_no_order')
                else:
                    order_text = 'Ordinare:'
                    format_order = get_xls_format('bg_order')
            except:
                import pdb; pdb.set_trace()

            lineOrd = [
                (order_text, format_order),
                (o.uom_id.name or '?', get_xls_format('text_center')),
                ]
            # Order only from now to the end of block:
            for i in range(1, 13):
                if i >= self.current_day_cell:
                    lineOrd.append(('',  format_order))
                else:
                    lineOrd.append(('', format_text))

            write_xls_list_line(WS, row, lineOrd)

            # Obsolete filter:
            write_xls_list_line(
                WS, row, [
                    status_filter, filter_color], col=obsolete_filter_col)
            row += 1

            # -----------------------------------------------------------------
            #                           ROW Halfwork
            # -----------------------------------------------------------------
            if hw:
                # Merge cell:
                WS.merge_range(row, 0, row, 12, '')

                # Create row data:
                line6 = [
                    [],  # rich text format
                    ('', format_text), ('', format_text), ('', format_text),
                    ('', format_text), ('', format_text), ('', format_text),
                    ('', format_text), ('', format_text), ('', format_text),
                    ('', format_text), ('', format_text), ('', format_text),

                    # Total (cell 14):
                    # HW in Mt. of fabric that can be used:
                    [0, get_xls_format('number_blue')],  # initial setup
                    # To be ordered - used = Total order
                    [0, get_xls_format('bg_green')],  # initial setup green!
                    ]
                hw_total_mt = 0.0
                for hw_code, hw_status in hw.iteritems():
                    hw_total_mt += hw_status[2]  # usabled

                    # OC covered with stock (color the HW text):
                    if hw_status[1] <= hw_status[0]:  # black
                        line6[0].append(get_xls_format('text'))
                    else:  # red
                        line6[0].append(get_xls_format('text_red'))

                    line6[0].append('%s OC:%s' % (
                        hw_code,
                        int(hw_status[1]),
                        ))

                    # Green:
                    line6[0].append(get_xls_format('text_green'))
                    line6[0].append(' M.:%s' % int(hw_status[0]))
                    line6[0].append(get_xls_format('text_black'))
                    # line6[0].append('(%s)>>>' % hw_status[3])
                    line6[0].append('>>>')
                    line6[0].append(get_xls_format('text_blue'))
                    line6[0].append('%s ' % int(hw_status[2]))
                    # line6[0].append(get_xls_format('text_wrap'))
                line6[13][0] = int(hw_total_mt)  # Update total mt. calc here

                # -------------------------------------------------------------
                # Total with color:
                # -------------------------------------------------------------
                # TODO comment the total
                order_total = int(sal[11] + hw_total_mt)
                line6[14][0] = order_total  # Total to be ordered
                if order_total <= 0:
                    line6[14][1] = get_xls_format('bg_red')
                elif order_total < o.report_minimum_qty:
                    line6[14][1] = get_xls_format('bg_yellow')
                line6[0].append(get_xls_format('text_black'))

                write_xls_list_line(WS, row, line6)

                # Write obsolete filter cell:
                write_xls_list_line(
                    WS, row, [
                        status_filter, filter_color], col=obsolete_filter_col)
                row += 1

            # -----------------------------------------------------------------
            #                          EXTRA ROW
            # -----------------------------------------------------------------
            write_xls_list_line(
                WS, row, [status_filter, filter_color],
                col=obsolete_filter_col)
            row += 1  # TODO remove?!?!?
            return row

        # Parameters:
        obsolete_filter_col = 24  # Y column
        filename = '/tmp/extract_fabric_report.xlsx'
        _logger.info('Start create file %s' % filename)

        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def get_add_page(WB, name):
            """ Add WS with that name
                if present return WS reference
            """
            WS = WB.add_worksheet(name)

            # -----------------------------------------------------------------
            # Format columns width:
            # -----------------------------------------------------------------
            WS.set_column('A:A', 19)
            WS.set_column('B:B', 3)
            WS.set_column('C:O', 7)
            WS.set_column('P:P', 1)
            WS.set_column('Q:S', 7)
            WS.set_column('T:V', 13)
            WS.set_column('W:W', 25)
            WS.set_column('X:X', 9)
            return WS

        # ---------------------------------------------------------------------
        # Create Excel file:
        # ---------------------------------------------------------------------
        WB = xlsxwriter.Workbook(filename)
        WS_page = {}  # Multi page

        # Current month cell:
        convert_month = {
            1: 5, 2: 6, 3: 7, 4: 8, 5: 9, 6: 10, 7: 11, 8: 12, 9: 1, 10: 2, 11: 3, 12: 4,
            }
        self.current_day_cell = convert_month[datetime.now().month]

        # Format for cell:
        num_format = '#,##0'

        # ---------------------------------------------------------------------
        #                     EXPORT EXCEL REPORT
        # ---------------------------------------------------------------------
        # Generate format database:
        get_xls_format(mode=False, WB=WB)  # First call for create formats
        format_text = get_xls_format('text')

        # ---------------------------------------------------------------------
        # A. Generate data report:
        # ---------------------------------------------------------------------
        res, all_component_ids = self.get_explode_report_object(
            cr, uid, data=data, context=context)

        # ---------------------------------------------------------------------
        # Data record in different sheet: Loop all record to write
        # ---------------------------------------------------------------------
        for line in res:
            category_name = line[12] or 'Non presente'
            if category_name not in WS_page:
                WS = get_add_page(WB, category_name)
                WS_page[category_name] = [
                    WS,
                    1,  # row
                    ]

                # Write title for filter line:
                write_xls_list_line(
                    WS, 0, [
                        ('Stato', format_text),
                        ('Colore', format_text),
                    ], col=obsolete_filter_col)
                WS.merge_range(0, 0, 0, obsolete_filter_col - 1, '')
                WS.autofilter(
                    0, obsolete_filter_col, 0, obsolete_filter_col + 1)

            WS, row = WS_page[category_name]

            # Save row returned:
            WS_page[category_name][1] = write_xls_block_line(WS, row, line)

        # ---------------------------------------------------------------------
        # B. Extra page unused component
        # ---------------------------------------------------------------------
        if all_component_ids:
            _logger.warning('Write unused lines in Excel')
            product_pool = self.pool.get('product.product')
            WS = WB.add_worksheet(_('Non usati'))
            WS.set_column('A:A', 30)
            WS.set_column('B:B', 15)
            WS.set_column('C:D', 30)
            WS.set_column('E:F', 15)

            # Header
            format_text = get_xls_format('text')
            row = 0
            write_xls_list_line(WS, row, [(
                'Elenco componenti non presenti nella stampa appartenenti a: '
                'DB Dinamiche, padre e semilavorato (se filtro fornitore '
                'attivo viene applicato anche qui)', format_text),
                ])
            row = 1
            write_xls_list_line(WS, row, [
                ('Categoria inv.', format_text),
                ('Codice', format_text),
                ('Nome', format_text),
                ('Ultimo forn.', format_text),
                ('Netto', format_text),
                ('Lordo', format_text),
                ])

            # Sort data:
            sorted_product = sorted(product_pool.browse(
                cr, uid, all_component_ids, context=context),
                key=lambda x: (x.inventory_category_id.name, x.default_code),
                )

            # Line:
            for product in sorted_product:
                row += 1
                write_xls_list_line(WS, row, [
                    (product.inventory_category_id.name, format_text),
                    (product.default_code or '', format_text),
                    (product.name, format_text),
                    (product.recent_supplier_id.name or '', format_text),
                    (product.mx_net_mrp_qty, format_text),
                    (product.mx_lord_mrp_qty, format_text),
                    ])

        WB.close()
        _logger.info('End creation file %s' % filename)
        return filename

    def send_fabric_mrp_report_scheduler(
            self, cr, uid, mode='odt', context=None):
        """ Generate PDF with data and send mail
        """
        if context is None:
            context = {
                'lang': 'it_IT',
                }

        # Prepare data selection filter (as wizard):
        datas = {
            # Report setup:
            'model': 'mrp.production',
            'active_id': False,
            'active_ids': [],
            'context': context,

            # Datas setup:
            'mp_mode': 'fabric',
            'only_negative': False,  # TODO
            'without_type_ids': [],
            'mode': 'component',
            'type_id': False,
            'with_deadline': False,
            'days': 30,
            'first_supplier_id': False,
            'with_type_ids': []
            }

        # ---------------------------------------------------------------------
        # Report in ODT mode:
        # ---------------------------------------------------------------------
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')
        if mode == 'odt':  # TODO remove, no more used!
            report_name = 'stock_status_explode_report'

            # -----------------------------------------------------------------
            # Call report:
            # -----------------------------------------------------------------
            # Procedure for problem in setup language in ODT report
            mrp_ids = self.search(cr, uid, [], context=context)
            if mrp_ids:
                mrp_id = mrp_ids[0]
            else:
                mrp_id = False

            try:
                result, extension = openerp.report.render_report(
                    cr, uid, [mrp_id], report_name, datas, context)
            except:
                _logger.error('Error generation TX report [%s]' % (
                    sys.exc_info(),))
                return False
            attachments = [('Completo_%s.odt' % now, result)]
        elif mode == 'xlsx':
            filename = self.extract_mrp_production_report_xlsx(cr, uid, data=datas, context=context)

            # Append stock page here:
            _logger.info('Integrate stock page in %s' % filename)
            self.integrate_stock_total_page_to_excel(filename)

            # Create attachment block for send after:
            xlsx_raw = open(filename, 'rb').read()
            attachments = [('Stato_tessuti_%s.xlsx' % now, xlsx_raw)]
        else:
            _logger.error('Only odt or xlsx mode for this report!')
            return False

        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(cr, uid, 'textilene_status', 'group_textilene_admin')[1]
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)

        thread_pool.message_post(
            cr, uid, False,
            type='email',
            body='Stato tessuti settimanale',
            subject='Invio automatico stato tessuto: %s' % (datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT), ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments,
            context=context,
            )
        return True
