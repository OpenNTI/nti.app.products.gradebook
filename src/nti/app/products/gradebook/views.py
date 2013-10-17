#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

import simplejson

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.appserver.dataserver_pyramid_views import _GenericGetView as GenericGetView

from nti.dataserver import authorization as nauth

from nti.utils.maps import CaseInsensitiveDict

from . import utils
from . import grades
from . import interfaces as grades_interfaces

_view_defaults = dict(  route_name='objects.generic.traversal',
						renderer='rest' )
_c_view_defaults = _view_defaults.copy()
_c_view_defaults.update( permission=nauth.ACT_CREATE,
						 request_method='POST' )
_r_view_defaults = _view_defaults.copy()
_r_view_defaults.update( permission=nauth.ACT_READ,
						 request_method='GET' )
_d_view_defaults = _view_defaults.copy()
_d_view_defaults.update( permission=nauth.ACT_DELETE,
						 request_method='DELETE' )

class _PostView(object):

	def __init__(self, request):
		self.request = request

	def readInput(self):
		request = self.request
		values = simplejson.loads(unicode(request.body, request.charset)) if request.body else {}
		return CaseInsensitiveDict(**values)

@view_config(context=grades_interfaces.IGradeBook)
@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults( **_r_view_defaults )
class GradeBookGetView(GenericGetView):
	""" Support for simply returning the gradebooks """
	pass

@view_config(context=grades_interfaces.IGrades)
@view_defaults(**_c_view_defaults)
class SetGradeView(_PostView):

	def __call__(self):
		request = self.request
		values = self.readInput()
		grade = grades.Grade()
		entryId = values.get('entryId')
		if not entryId:
			utils.raise_field_error(request, "entryid", _("must specify a valid grade entry"))
		grade.entryId = entryId
	
		value = values.get('grade')
		if value is None:
			utils.raise_field_error(request, "grade", _("must specify a valid grade"))

		try:
			field = grades_interfaces.IGrade['grade']
			value = field.fromUnicode(value)
			grade.grade = value
		except:
			utils.raise_field_error(request, "grade", _("must specify a valid grade"))

		username = values.get('username', values.get('student'))
		if not username:
			utils.raise_field_error(request, "username", _("must specify a valid student name"))

		store = request.context
		store.add_grade(username, grade)
		return hexc.HTTPNoContent()

del _view_defaults
del _c_view_defaults
del _r_view_defaults
del _d_view_defaults
