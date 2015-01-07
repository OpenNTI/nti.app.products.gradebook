#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import interface
from zope.interface import Invalid
from zope.container.contained import Contained
from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.datastructures import CreatedAndModifiedTimeMixin

from nti.externalization.representation import WithRepr

from nti.schema.schema import EqHash
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.utils.property import Lazy
from nti.utils.property import alias

from nti.zodb.persistentproperty import PersistentPropertyHolder

from ..interfaces import IGradeBook
from ..interfaces import IExcusedGrade

from ..utils import MetaGradeBookObject

from .interfaces import IAssigmentGradeScheme
from .interfaces import IDefaultCourseGradingPolicy

@interface.implementer(IAssigmentGradeScheme)
@WithRepr
@EqHash('GradeScheme', 'Weight')
class AssigmentGradeScheme(Persistent, SchemaConfigured):
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(IAssigmentGradeScheme)

	weight = alias('Weight')
	scheme = alias('GradeScheme')
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)
	
@interface.implementer(IDefaultCourseGradingPolicy)
class DefaultCourseGradingPolicy(CreatedAndModifiedTimeMixin,
								 PersistentPropertyHolder, 
								 SchemaConfigured, 
								 Contained):
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(IAssigmentGradeScheme)
	
	items = alias('AssigmentGradeSchemes')

	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		CreatedAndModifiedTimeMixin.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)

	def validate(self):
		book = self._book
		sum_weight = 0.0
		for name, value in self.items.items():
			entry = book.getEntryByAssignment(name, check_name=True)
			if entry is None:
				raise Invalid("Could not find GradeBook Entry for %s", name)
			scheme = value.scheme if value.scheme else self.DefaultGradeScheme
			if scheme is None:
				raise Invalid("Could not find grade scheme for %s", name)
			sum_weight +=  value.weight if value is not None else 0.0
			
		if round(sum_weight, 2) != 1:
			raise Invalid("Weight in policy do not equal to one")

	@Lazy
	def _book(self):
		context = self.__parent__
		book = IGradeBook(ICourseInstance(context))
		return book
	
	@Lazy
	def _schemes(self):
		result = {}
		book = self._book
		for name, value in self.items.items():
			entry = book.getEntryByAssignment(name, check_name=True)
			scheme = value.scheme if value.scheme else self.DefaultGradeScheme
			result[entry.assignmentId] = scheme
		return result

	@Lazy
	def _weights(self):
		result = {}
		book = self._book
		for name, value in self.items.items():
			entry = book.getEntryByAssignment(name, check_name=True)
			result[entry.assignmentId] = value.weight
		return result
	
	def _to_correctness(self, value, scheme):
		value = scheme.fromUnicode(value) \
				if isinstance(value, six.string_types) else value
		scheme.validate(value)
		result = scheme.toCorrectness(value)
		return result
	
	def grade(self, principal):
		result = 0
		book = self._book
		username = IPrincipal(principal).id		
		for grade in book.iter_grades(username):
			weight = self._weights.get(grade.AssignmentId)
			if IExcusedGrade.providedBy(grade):
				result += weight
				continue
			value = grade.value
			scheme = self._schemes.get(grade.AssignmentId)
			correctness = self._to_correctness(value, scheme)
			result += correctness * weight
		return result
