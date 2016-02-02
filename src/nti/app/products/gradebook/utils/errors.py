# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys

from pyramid import httpexceptions as hexc

from nti.app.externalization.error import raise_json_error

def raise_field_error(request, field, message):
	exc_info = sys.exc_info()
	data = {u'field':field, u'message': message}
	raise_json_error(request, hexc.HTTPUnprocessableEntity, data, exc_info[2])
