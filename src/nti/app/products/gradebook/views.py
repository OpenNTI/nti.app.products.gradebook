#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.appserver.dataserver_pyramid_views import _GenericGetView as GenericGetView

from nti.dataserver import authorization as nauth

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

@view_config(context=grades_interfaces.IGradeBook)
@view_config(context=grades_interfaces.IGradeBookPart)
@view_config(context=grades_interfaces.IGradeBookEntry)
@view_defaults( **_r_view_defaults )
class GradeBookGetView(GenericGetView):
	""" Support for simply returning the gradebooks """
	pass

del _view_defaults
del _c_view_defaults
del _r_view_defaults
del _d_view_defaults
