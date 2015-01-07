#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook internalization

.. $Id: internalization.py 49381 2014-09-15 21:03:16Z carlos.sanchez $
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.externalization.interfaces import IInternalObjectUpdater

from nti.externalization.internalization import find_factory_for
from nti.externalization.datastructures import InterfaceObjectIO
from nti.externalization.internalization import update_from_external_object

from .interfaces import IDefaultCourseGradingPolicy

@interface.implementer(IInternalObjectUpdater)
@component.adapter(IDefaultCourseGradingPolicy)
class _DefaultCourseGradingPolicytUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = IDefaultCourseGradingPolicy

	def updateFromExternalObject(self, ext, *args, **kwargs):
		schemes = ext.get('AssigmentGradeSchemes', {})
		for name, value in list(schemes.items()):
			obj = find_factory_for(value)()
			update_from_external_object(obj, value)
			schemes[name] = obj
		result = super(_DefaultCourseGradingPolicytUpdater,self).updateFromExternalObject(ext, *args, **kwargs)
		return result
