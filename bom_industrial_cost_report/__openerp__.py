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

{
    'name': 'BOM Industrial cost',
    'version': '0.1',
    'category': 'MRP',
    'description': '''        
        BOM Industrial cost calculation. 
        Mark a list of observed product and calculate all cost from material
        and work on MRP.
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mrp',
        'product',
        'account',
        'bom_production_cost',
        'bom_dynamic_structured', # for dynamic bom structure
        'bom_check_problem_wizard', # For checked bom
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/bom_group.xml',
        'security/ir.model.access.csv',

        'industrial_view.xml',
        'report/report_bom.xml',
        'wizard/open_report_view.xml',

        'scheduler.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
