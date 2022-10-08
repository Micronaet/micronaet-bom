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


class ProductProduct(orm.Model):
    """ Model name: ProductProduct add utility for report
    """
    _inherit = 'product.product'

    def get_medea_data(self, value):
        medea_cost = {  # packaging:
            '005': 1.37,
            '014': 3.23,
            '021': 5.14,
            '022': 1.32,
            '023': 1.74,
            '024': 3.23,
            '025': 3.23,
            '026': 1.9,
            '027': 1.9,
            '028': 1.48,
            '029': 6.42,
            '030': 6.42,
            '031': 1.73,
            '033': 3.02,
            '034': 3.76,
            '035': 3.02,
            '035TX': 3.02,
            '036': 3.02,
            '037': 6.42,
            '038': 6.42,
            '039': 3.76,
            '041': 1.9,
            '045': 2.6,
            '046': 2.6,
            '048': 2.6,
            '049': 2.6,
            '050': 8.0,
            '051': 8.0,
            '070': 6.42,
            '071': 7.15,
            '090': 5.5,
            '091': 5.5,
            '121': 5.14,
            '123': 1.74,
            '126': 1.9,
            '127': 1.9,
            '128': 1.48,
            '129': 6.42,
            '130': 6.42,
            '131': 1.73,
            '132': 3.02,
            '135': 3.02,
            '145': 2.6,
            '147': 2.6,
            '148': 2.6,
            '149': 2.6,
            '150': 1.3,
            '161': 1.48,
            '162': 1.48,
            '163': 1.48,
            '165': 1.48,
            '190': 5.5,
            '205': 1.37,
            '223': 2.5,
            '300': 2.2,
            '301': 2.2,
            '322': 1.42,
            '330': 1.42,
            '331': 1.42,
            '332': 1.42,
            '334': 5.5,
            '334HP': 5.5,
            '335': 5.5,
            '336': 5.5,
            '337': 5.5,
            '375': 8.0,
            '375HP': 8.0,
            '376': 8.0,
            '550': 2.39,
            '552': 0.81,
            '600': 0.74,
            '601': 0.74,
            '800': 3.02,
            '831': 6.6,
            'G420': 3.02,
            'G421': 3.76,
            }
        medea_code = value.strip('%')
        res = medea_cost.get(medea_code, 0.0)
        if not res:
            _logger.error('Empty code: %s' % value)
        return res

    def report_get_objects_bom_industrial_cost(
            self, cr, uid, datas=None, context=None):
        """ Integration report
        """
        _logger.info('Start extracting...')
        # todo reactivate
        # data =  {
        #    'active_ids': False, # Load all template
        #    'model': 'product.product',
        #    'wizard': True,
        #   }
        res = super(
            ProductProduct, self).report_get_objects_bom_industrial_cost(
                cr, uid, datas=datas, context=context)
        _logger.info('Start reporting...')
        # removed
        return res

        # ---------------------------------------------------------------------
        # NEW VERSION:
        # ---------------------------------------------------------------------
        f_bom = open('/home/odoo/0.bom_report.csv', 'w')

        header = u'Componente|Q.|UM|Prezzo|Totale\n'
        for item in res:
            (min, max, error, components, extra1, extra2, index, total,
                product, parameter, total_text, pipe_total_weight,
                simulated_price) = item
            f_bom.write(u'%s|%s' % (
                product.default_code,
                product.name,
                ))

            # -----------------------------------------------------------------
            # Component line:
            # -----------------------------------------------------------------
            f_bom.write(header)
            for line in components:
                (name, q, um, price, total, list_detail, hw, element,
                    red_price, fabric_text) = line
                if hw:
                    block1 = u'%s %s' % (
                        name,
                        # list_ids,
                        hw.default_code,
                        )
                else:
                    block1 = name

                f_bom.write(u'%s|%s|%s|%s|%s\n' % (
                    block1,
                    q,
                    um,
                    price,
                    total,
                    ))

            # -----------------------------------------------------------------
            # Work
            # -----------------------------------------------------------------
            f_bom.write(u'Manodopera|Prodotto|Totale\n')
            for item, details, time_qty in extra1:
                f_bom.write('%s (unit. %s)||%s|%s\n' % (
                    item.cost_id.name,
                    item.cost_id.unit_cost,
                    item.product_id.default_code or '/',
                    details,
                    ))

            # -----------------------------------------------------------------
            # Industrial
            # -----------------------------------------------------------------
            f_bom.write(u'Costi industriali|Prodotto|Totale\n')
            for item, details, time_qty in extra2:
                f_bom.write('%s (unit. %s)||%s|%s\n' % (
                    item.cost_id.name,
                    item.cost_id.unit_cost,
                    item.product_id.default_code or '/',
                    details,
                    ))

            # -----------------------------------------------------------------
            # Total:
            # -----------------------------------------------------------------
            f_bom.write(u'Subtotali|%s|Costo|%s-%s\n' % (
                total_text, min, max
                ))
            # f_bom.write('Indici|%s|Vendita|%s-%s\n' % (
            #    total['index'],
            #    total['margin']
            #    ))

        f_bom.close()
        return res
