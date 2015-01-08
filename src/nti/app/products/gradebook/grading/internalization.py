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

from .interfaces import ICategoryGradeScheme
from .interfaces import ICS1323CourseGradingPolicy
from .interfaces import IDefaultCourseGradingPolicy

@interface.implementer(IInternalObjectUpdater)
@component.adapter(IDefaultCourseGradingPolicy)
class _DefaultCourseGradingPolicyUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = IDefaultCourseGradingPolicy

	def parseAssigmentGradeSchemes(self, parsed):
		schemes = parsed.get('AssigmentGradeSchemes', {})
		for name, value in list(schemes.items()):
			obj = find_factory_for(value)()
			update_from_external_object(obj, value)
			schemes[name] = obj
		return schemes
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.parseAssigmentGradeSchemes(parsed)
		result = super(_DefaultCourseGradingPolicyUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result

@interface.implementer(IInternalObjectUpdater)
@component.adapter(ICategoryGradeScheme)
class _CategoryGradeSchemesUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = ICategoryGradeScheme

	def parseAssigmentGradeSchemes(self, parsed):
		schemes = parsed.get('AssigmentGradeSchemes', {})
		for name, value in list(schemes.items()):
			obj = find_factory_for(value)()
			update_from_external_object(obj, value)
			schemes[name] = obj
		return schemes
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.parseAssigmentGradeSchemes(parsed)
		result = super(_CategoryGradeSchemesUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result
	
@interface.implementer(IInternalObjectUpdater)
@component.adapter(ICS1323CourseGradingPolicy)
class _CS1323CourseGradingPolicyUpdater(InterfaceObjectIO):

	_ext_iface_upper_bound = ICS1323CourseGradingPolicy

	def parseCatagoryGradeSchemes(self, parsed):
		schemes = parsed.get('CategoryGradeSchemes', {})
		for name, value in list(schemes.items()):
			obj = find_factory_for(value)()
			update_from_external_object(obj, value)
			schemes[name] = obj
		return schemes
	
	def updateFromExternalObject(self, parsed, *args, **kwargs):
		self.parseCatagoryGradeSchemes(parsed)
		result = super(_CS1323CourseGradingPolicyUpdater,self).updateFromExternalObject(parsed, *args, **kwargs)
		return result
