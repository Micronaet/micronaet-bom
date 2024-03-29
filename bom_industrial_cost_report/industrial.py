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


class ResPartner(orm.Model):
    """ Model name: Partner
    """
    _inherit = 'res.partner'

    _columns = {
        'industrial_transport_rate': fields.float(
            'Tasso trasporto %', digits=(16, 4),
            help='Il tasso del trasporto viene calcolato e sommato al costo'
                 'effettivo del prodotto',
        ),
        'industrial_extra_discount': fields.float(
            'Sconto extra', digits=(16, 4),
            help='In tasso di extra sconto viene tolto dal fatturato',
        ),
    }


class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'

    _columns = {
        'industrial_margin_a': fields.float('Margine A%', digits=(16, 4)),
        'industrial_margin_b': fields.float('Margine B%', digits=(16, 4)),
        'industrial_days': fields.integer('Giorni prezzo',
            help='Giorni prima di oggi in cui prendere il prezzo inserito'),
        'industrial_margin_extra': fields.float('Margine extra%',
            digits=(16, 4)),
        }

    _defaults = {
        'industrial_days': lambda *x: 500,
        'industrial_margin_extra': lambda *x: 0.1,
        }


class MrpBomIndustrialSimulation(orm.Model):
    """ Model name: Industrial simulation
    """

    _name = 'mrp.bom.industrial.simulation'
    _description = 'Industrial simulation'
    _order = 'sequence, name'
    _rec_name = 'supplier_id'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'name': fields.char('Inizio', size=20),
        'value': fields.float('Valore', digits=(16, 5), required=True),
        'supplier_id': fields.many2one('res.partner', 'Fornitore'),
        'from': fields.date('Dalla data'),
        'mode': fields.selection([
            ('fixed', 'Fisso'),
            ('value', 'Aumento a valore'),
            ('rate', 'Aumento a percentuale'),
            ], 'Modalità'),
        }

    _defaults = {
        # Default value:
        'mode': lambda *x: 'rate',
        }


class MrpBomIndustrialCost(orm.Model):
    """ Model name: Industrial cost
    """

    _name = 'mrp.bom.industrial.cost'
    _description = 'Industrial cost'
    _order = 'name'

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def open_load_detail_list(self, cr, uid, ids, context=None):
        """ Open list in tree view
        """
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        line_ids = line_pool.search(cr, uid, [
            ('cost_id', '=', ids[0]),
            ], context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail for cost selected'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'mrp.bom.industrial.cost.line',
            # 'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def load_detail_from_BOM(self, cr, uid, ids, context=None):
        """ Load all mask list from bom selected
        """
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')

        current_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Load current mask selected:
        current_mask = []
        for line in current_proxy.line_ids:
            current_mask.append(line.name)

        # Create only new elements:
        mask_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True),
            ], context=context)
        if not mask_ids:
            raise osv.except_osv(
                _('Error:'),
                _('Error product reference selected for BOM'),
                )
        for product in product_pool.browse(cr, uid, mask_ids, context=context):
            mask = '%s%%' % product.default_code
            if mask in current_mask:
                continue

            line_pool.create(cr, uid, {
                'cost_id': current_proxy.id,
                'cost': current_proxy.default_cost,
                'name': mask,
                }, context=context)
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'unit_cost': fields.float(
            'Costo Unitario', digits=(16, 3),
            help='Default cost used when append imported BOM'),
        'type': fields.selection([
            ('work', 'Manodopera'),
            ('industrial', 'Costi industriali'),
            ], 'Tipo', required=True),
        'note': fields.text('Note'),
        # todo REMOVE:
        'default_cost': fields.float(
            'Default cost', digits=(16, 3),
            help='Default cost used when append imported BOM'),
        }

    _defaults = {
        'type': lambda *x: 'industrial',
        }


class MrpBomIndustrialCostLine(orm.Model):
    """ Model name: Cost line
    """

    _name = 'mrp.bom.industrial.cost.line'
    _description = 'Industrial cost line'
    _order = 'name'

    def _get_last_cost_info(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            product = line.product_id
            res[line.id] = {}
            res[line.id]['last_cost'] = 0.0
            res[line.id]['last_date'] = False
            if not product:
                continue

            # Loop on sellers and pricelist:
            for seller in product.seller_ids:
                for pricelist in seller.pricelist_ids:  # XXX multi q. probl?
                    if not pricelist.is_active:
                        continue

                    date_quotation = pricelist.date_quotation or False
                    if not res[line.id]['last_cost'] or \
                            date_quotation > res[line.id]['last_date']:
                        res[line.id]['last_cost'] = pricelist.price
                        res[line.id]['last_date'] = date_quotation
        return res

    _columns = {
        'name': fields.char(
            'Mask', size=64, required=True,
            help='Mask for code, use % for all, _ for replace one char'),
        'product_id': fields.many2one('product.product', 'Prodotto'),
        'uom_id': fields.related(
            'product_id', 'uom_id',
            type='many2one', relation='product.uom',
            string='UM', readonly=True),
        'cost_id': fields.many2one(
            'mrp.bom.industrial.cost', 'Cost'),
        'qty': fields.float('Q.', digits=(16, 3), required=True),

        # Get product cost info:
        'last_cost': fields.function(
            _get_last_cost_info, method=True,
            type='float', string='Costo ultimo',
            store=False, multi=True, readonly=True),
        'last_date': fields.function(
            _get_last_cost_info, method=True,
            type='char', string='Data ultimo',
            store=False, multi=True, readonly=True),
        }


class MrpBomIndustrialCostInherit(orm.Model):
    """ Model name: Industrial cost
    """

    _inherit = 'mrp.bom.industrial.cost'

    _columns = {
        'line_ids': fields.one2many(
            'mrp.bom.industrial.cost.line', 'cost_id', 'Line'),
        }


class MrpBomIndustrialHistory(orm.Model):
    """ Model name: Mrp Bom IndustrialHistory
    """
    _name = 'mrp.bom.industrial.history'
    _description = 'BOM Industrial history'
    _order = 'name'

    def scheduled_update_current_price(
            self, cr, uid, always_report=False, gap=5.0, context=None):
        """ Scheduled update of current price
        """
        product_pool = self.pool.get('product.product')
        excel_pool = self.pool.get('excel.writer')

        if context is None:
            context = {}
        context['update_current_industrial'] = True

        # Call update button parameter update current:
        self.button_history_now(cr, uid, False, context=context)

        # Generate report if necessary:
        product_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True),
        ], context=context)

        # ---------------------------------------------------------------------
        # Excel report:
        # ---------------------------------------------------------------------
        WS_name = _('Costi industriali')
        excel_pool.create_worksheet(WS_name)

        # Format used:
        excel_pool.set_format(number_format='#,##0.#0')
        format_mode = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),

            'text': {
                'white': excel_pool.get_format('text'),
                'red': excel_pool.get_format('bg_red'),
                'blue': excel_pool.get_format('bg_blue'),
                },
            'number': {
                'white': excel_pool.get_format('number'),
                'red': excel_pool.get_format('bg_red_number'),
                'blue': excel_pool.get_format('bg_blue_number'),
                },
            }

        now = datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT)

        excel_pool.column_width(WS_name, [
            15, 45,
            10, 10, 10, 10,
            10, 10,
            ])

        # Title line:
        row = 0  # Start line
        excel_pool.write_xls_line(
            WS_name, row, [
                'Variazione costi industriali prodotti (modello):'
                ], default_format=format_mode['title'])

        # Header line:
        row += 2
        excel_pool.write_xls_line(
            WS_name, row, [
                'Codice', 'Descrizione',
                'Storico min.', 'Storico max.',
                'Attuale min.', 'Attuale max.',
                'Diff. min.', '%',
                ], default_format=format_mode['header'])

        gap_total = 0
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            history = product.from_industrial
            if not history:
                continue  # jump no price
            current = product.current_from_industrial

            difference = history - current
            difference_rate = 100.0 * difference / history
            if abs(difference_rate) >= gap:
                found = True
                gap_total += 1
            else:
                found = False

            if always_report or found:
                row += 1
                text_format = format_mode['text']['white']
                number_format = format_mode['number']['white']
                if found:
                    if difference > 0:
                        text_format = format_mode['text']['blue']
                        number_format = format_mode['number']['blue']
                    else:
                        text_format = format_mode['text']['red']
                        number_format = format_mode['number']['red']

                excel_pool.write_xls_line(
                    WS_name, row, [
                        (product.default_code, text_format),
                        (product.name, text_format),
                        product.from_industrial,
                        product.to_industrial,
                        product.current_from_industrial,
                        product.current_to_industrial,
                        difference,
                        difference_rate,
                        ], default_format=number_format)

        if always_report or gap_total > 0:
            return excel_pool.send_mail_to_group(
                cr, uid,
                'bom_industrial_cost_report.group_margin_check_report',
                'Confronto prezzi DB modello %s' % (
                    ('[PRESENTI GAP: %s!]' % gap_total) if
                    gap_total > 0
                    else '[NON PRESENTI]',
                    ),
                'Confronto costi DB modello storico e attuale: %s' % now,
                'template_check_cost.xlsx',
                context=context)
        else:
            _logger.warning('Current industrial cost are all right < %s' % gap)
            excel_pool.close_workbook()  # remove file
            return True

    def button_history_now(self, cr, uid, ids, context=None):
        """ History button
        """
        _logger.info('Run report background')
        if not ids:
            ids = [self.create(cr, uid, {
                'name': 'Schedulata il %s' % datetime.now(),
                }, context=context)]
        history_id = ids[0]
        line_pool = self.pool.get('mrp.bom.industrial.history.line')

        # Parameters (folder):
        path = '~/.local/share/Odoo/history/%s' % cr.dbname
        path = os.path.expanduser(path)
        os.system('mkdir -p %s' % path)  # Create if not present

        # Context:
        if context is None:
            context = {
                'lang': 'it_IT',
                }

        # ---------------------------------------------------------------------
        # Bom current cost:
        # ---------------------------------------------------------------------
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True)], context=context)

        # History line management (use only max price industrial):
        history_price = {}
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            history_price[product] = product.to_industrial

        # ---------------------------------------------------------------------
        # Setup call of report:
        # ---------------------------------------------------------------------
        # 2 mode of update : current value, history value:
        if context.get('update_current_industrial'):
            # Update current from / to industrial in product
            update_current_industrial = True
            update_record = False
        else:
            # Update only data from / to industrial in template
            update_current_industrial = False
            update_record = True

        datas = {
            # Report setup:
            'model': 'product.product',
            'active_id': False,
            'active_ids': [],  # no active_ids means all template BOM!
            'context': context,

            # Datas setup:
            'update_record': update_record,
            'update_current_industrial': update_current_industrial,
            'wizard': True,
            }

        # ---------------------------------------------------------------------
        # Call report:
        # ---------------------------------------------------------------------
        try:
            result, extension = openerp.report.render_report(
                cr, uid, [], 'industrial_cost_bom_report',
                datas, context)
        except:
            _logger.error('Error generation history BOM report [%s]' % (
                sys.exc_info(), ))
            return False

        # ---------------------------------------------------------------------
        # Filename generation:
        # ---------------------------------------------------------------------
        # Parameter:
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')
        filename = 'Storico_db_%s.%s' % (now, extension)
        filename = filename.replace(':', '.').replace('/', '_')
        fullname = os.path.join(path, filename)

        # Save report in history folder
        # result
        f_out = open(fullname, 'wb+')
        f_out.write(result)
        f_out.close()
        _logger.warning('Create files: %s' % fullname)

        # ---------------------------------------------------------------------
        # Bom after cost:
        # ---------------------------------------------------------------------
        # History line management (use only max price industrial):
        # Reload for sure:
        product_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True)], context=context)
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            line_pool.create(cr, uid, {
                'history_id': history_id,
                'product_id': product.id,
                'previous': history_price.get(product),
                'current': product.to_industrial,
            }, context=context)

        # ---------------------------------------------------------------------
        # Save history record data:
        # ---------------------------------------------------------------------
        # todo save in lines:
        """
        self.write(cr, uid, ids, {
            'name': 'Storico %s' % now,
            'filename': filename,
            'previous_text': previous_text,
            'post_text': post_text,
            }, context=context)
        """
        return True

    _columns = {
        'name': fields.char('Rif.', size=64),
        'filename': fields.char('Filename.', size=80),
        'create_uid': fields.many2one('res.users', 'Utente', readonly=True),
        'create_date': fields.date('Data', readonly=True),
        'note': fields.text('Note', readonly=True),
        }

    _defaults = {
        'note': lambda *x: u'''
            <p><b>Storicizzazione prezzi</b></p>
            <p>Premere il bottone per storicizzare i prezzi sulle 
               attuali distinte base, verrà generato il report totale e,
               in funzione dei costi registrati al momento, stalvati
               nella scheda prodotto il costo di partenza con i vari 
               margini impostati ad oggi.</p>
            <p>Tale processo sovrascrive gli attuali prezzi quindi
               lanciarlo solo se sicuri dell'operazione. Una volta
               Storicizzato controllare che non siano presenti 
               distinte con i valori in rosso (prezzi mancanti), in
               tal caso è necessario identificare il problema e 
               rigenerare un altro storico.               
               </p>   
            <p>Attenzione la generazione del report storico può durare
               qualche minuto...</p>   
            ''',
        }


class MrpBomIndustrialHistoryLine(orm.Model):
    """ Model name: Mrp Bom IndustrialHistoryLine
    """
    _name = 'mrp.bom.industrial.history.line'
    _rec_name = 'product_id'

    _columns = {
        'history_id': fields.many2one(
            'mrp.bom.industrial.history', 'Storico'),
        'product_id': fields.many2one(
            'product.product', 'DB', required=True),
        'previous': fields.float(
            'Precedente', digits=(16, 2)),
        'current': fields.float(
            'Corrente', digits=(16, 2), required=True),
    }


class MrpBomIndustrialHistoryRelation(orm.Model):
    """ Model name: Mrp Bom IndustrialHistory
    """
    _inherit = 'mrp.bom.industrial.history'

    _columns = {
        'line_ids': fields.one2many(
            'mrp.bom.industrial.history.line', 'history_id', 'Dettaglio'),
        }


class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Utility function:
    # -------------------------------------------------------------------------
    def get_cost_industrial_for_product_xmlrpc(self, cr, uid, ids,
            context=None):
        """ Procedure for return via XMLRLC call
        """
        res = {}
        cost_db = self.get_cost_industrial_for_product(
                cr, uid, ids, context=context)
        for cost, line in cost_db.iteritems():
            res[cost.name] = (
                line.qty,
                line.cost_id.name,
                line.product_id.default_code or '',
                line.last_cost,
                line.last_date,
                )
        return res

    def get_cost_industrial_for_product(self, cr, uid, ids, context=None):
        """ Return all list of industrial cost for product passed
            ids: product ids XXX now is one!
        """
        # Pool used:
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')

        product = self.browse(cr, uid, ids, context=context)[0]
        default_code = product.default_code
        if not default_code:
            return {}

        # Update category element priority order len mask
        query = '''
            SELECT id FROM mrp_bom_industrial_cost_line 
            WHERE '%s' ilike name ORDER BY length(name) desc;
            ''' % default_code
        cr.execute(query)

        # XXX 28/10/2017 Changed for report use:
        res = {}
        item_ids = [item[0] for item in cr.fetchall()]
        for item in line_pool.browse(
                cr, uid, item_ids, context=context):
            if item.cost_id in res:
                continue
            res[item.cost_id] = item
        return res

    # -------------------------------------------------------------------------
    # Button for select
    # -------------------------------------------------------------------------
    def bom_selection_on(self, cr, uid, ids, context=None):
        """ Select as template
        """
        return self.write(cr, uid, ids, {
            'bom_selection': True,
            }, context=context)

    def bom_selection_off(self, cr, uid, ids, context=None):
        """ Discard from template
        """
        return self.write(cr, uid, ids, {
            'bom_selection': False,
            }, context=context)

    def _get_industrial_sale_ab(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            cost = product.to_industrial
            res[product.id] = {}
            res[product.id]['industrial_sale_a'] = \
                cost * product.company_id.industrial_margin_a / 100.0
            res[product.id]['industrial_sale_b'] = \
                cost * product.company_id.industrial_margin_b / 100.0
        return res

    _columns = {
        'bom_selection': fields.boolean('BOM Selection'),
        'bom_industrial_no_price': fields.boolean('BOM no price OK',
            help='Se il prodotto fa parte di DB viene indicato senza prezzo',
            ),

        'current_from_industrial': fields.float(
            'Current from industrial cost', digits=(16, 3)),
        'current_to_industrial': fields.float(
            'Current to industrial cost', digits=(16, 3)),

        'from_industrial': fields.float(
            'From industrial cost', digits=(16, 3)),
        'to_industrial': fields.float(
            'To industrial cost', digits=(16, 3)),
        'industrial_missed': fields.boolean('Manca',
            help='Manca prezzo di alcuni componenti'),
        'industrial_index': fields.text('Indici'),

        # Calculated:
        'industrial_sale_a': fields.function(
            _get_industrial_sale_ab, method=True,
            type='float', string='Vend. A%', multi=True,
            store=False),
        'industrial_sale_b': fields.function(
            _get_industrial_sale_ab, method=True,
            type='float', string='Vend. B%', multi=True,
            store=False),
        }
