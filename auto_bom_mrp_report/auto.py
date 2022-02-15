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


class MrpProduction(orm.Model):
    """ Model name: MrpProduction Report
    """

    _inherit = 'mrp.production'

    def send_future_mrp_production_report_scheduler(
            self, cr, uid, context=None):
        """ Generate PDF with data and send mail
        """
        _logger.info('Start auto send MRP 30 gg production report')

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
            'mode': 'mrp',
            'exclude_inventory_category': True,
            'days': 30,
            # exclude_inventory_list (use default)
            }

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
                cr, uid, [mrp_id], 'mrp_status_explode_report', datas, context)
        except:
            _logger.error('Error generation MRP 30 gg report [%s]' % (
                sys.exc_info(), ))
            return False
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        now = now.replace('-', '_').replace(':', '.')

        attachments = [('MRP_30gg_%s.odt' % now, result)]

        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 'auto_bom_mrp_report', 'group_mrp_report_admin')[1]
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)

        thread_pool.message_post(cr, uid, False,
            type='email',
            body='Stato MRP con dettaglio 30 GG',
            subject='Invio automatico stato materiali per le prossime '
                    'produzioni schedulate per 30 gg.: %s' % (
                        datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                        ),
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments,
            context=context,
            )
        return True
