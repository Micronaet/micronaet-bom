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
    'name': 'Extract invoicer product BOM',
    'version': '0.1',
    'category': 'Check',
    'description': '''    
        Check invoiced product on sales
        Extract BOM component and price to get cost element
        XLS file to check total
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'product',
        'sale',
        'account',
        'bom_industrial_cost_report', # for BOM template
        'excel_export',
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'wizard/extract_view.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
