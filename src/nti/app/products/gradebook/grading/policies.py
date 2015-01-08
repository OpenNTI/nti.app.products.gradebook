#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types

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

class BaseGradingPolicy(CreatedAndModifiedTimeMixin,
						PersistentPropertyHolder, 
						SchemaConfigured, 
						Contained):
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		CreatedAndModifiedTimeMixin.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)

	@Lazy
	def book(self):
		context = self.__parent__
		book = IGradeBook(ICourseInstance(context))
		return book
	
	def to_correctness(self, value, scheme):
		value = scheme.fromUnicode(value) if isinstance(value, string_types) else value
		scheme.validate(value)
		result = scheme.toCorrectness(value)
		return result
	
def validate_assigment_grade_schemes(book, items, default_scheme=None, category=None):
	names = set()
	sum_weight = 0.0
	for name, value in items.items():
		names.add(name)
		entry = book.getEntryByAssignment(name, check_name=True)
		if entry is None:
			raise Invalid("Could not find GradeBook Entry for %s", name)
		scheme = value.scheme if value.scheme else default_scheme
		if scheme is None:
			raise Invalid("Could not find grade scheme for %s", name)
		sum_weight +=  value.weight if value is not None else 0.0
		
	if len(names) != len(items):
		if category:
			msg = "Duplicate entries in category %s" % category
		else:
			msg = "Duplicate entries in policy"
		raise Invalid(msg)
	
	if round(sum_weight, 2) != 1:
		if category:
			msg = "Total weight for category %s is not equal to one" % category
		else:
			msg = "Total weight in policy is not equal to one"
		raise Invalid(msg)
	return names
		
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
class DefaultCourseGradingPolicy(BaseGradingPolicy):
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(IDefaultCourseGradingPolicy)
	
	assigments = items = alias('AssigmentGradeSchemes')

	def validate(self):
		validate_assigment_grade_schemes(self.book, self.items, self.DefaultGradeScheme)

	@Lazy
	def _schemes(self):
		result = {}
		book = self.book
		for name, value in self.items.items():
			entry = book.getEntryByAssignment(name, check_name=True)
			scheme = value.scheme if value.scheme else self.DefaultGradeScheme
			result[entry.assignmentId] = scheme
		return result

	@Lazy
	def _weights(self):
		result = {}
		book = self.book
		for name, value in self.items.items():
			entry = book.getEntryByAssignment(name, check_name=True)
			result[entry.assignmentId] = value.weight
		return result
	
	def grade(self, principal):
		result = 0
		book = self.book
		username = IPrincipal(principal).id		
		for grade in book.iter_grades(username):
			weight = self._weights.get(grade.AssignmentId)
			if IExcusedGrade.providedBy(grade):
				result += weight
				continue
			value = grade.value
			scheme = self._schemes.get(grade.AssignmentId)
			correctness = self.to_correctness(value, scheme)
			result += correctness * weight
		return result

## CS1323

from .interfaces import ICategoryGradeScheme
from .interfaces import ICS1323CourseGradingPolicy

@interface.implementer(ICategoryGradeScheme)
@WithRepr
@EqHash('GradeScheme', 'Weight', 'AssigmentGradeSchemes')
class CategoryGradeScheme(Persistent, SchemaConfigured):
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(ICategoryGradeScheme)

	weight = alias('Weight')
	scheme = alias('GradeScheme')
	assigments = items = alias('AssigmentGradeSchemes')
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)
	
@interface.implementer(ICS1323CourseGradingPolicy)
class CS1323CourseGradingPolicy(BaseGradingPolicy):
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(ICS1323CourseGradingPolicy)
	
	scheme = alias('DefaultGradeScheme')
	categories = alias('CategoryGradeSchemes')

	@Lazy
	def _rev_categories(self):
		result = {}
		for name, category in self.categories.items():
			result.update({x:name for x in category.AssigmentGradeSchemes.keys()})
		return result
	
	def validate(self):
		book = self.book
		sum_weight = 0.0
		assigments = set()
		for name, category in self.categories.items():
			items = category.AssigmentGradeSchemes
			scheme = category.GradeScheme or self.DefaultGradeScheme
			in_category = validate_assigment_grade_schemes(book, items, scheme, name)
			assigments.update(in_category)
			sum_weight = category.Weight
		
		if round(sum_weight, 2) != 1:
			msg = "Total category weight in policy do not equal to one"
			raise Invalid(msg)
		
		if len(self._rev_categories) != len(assigments):
			raise Invalid("There are assigments assigned to multiple categories")
		
	@Lazy
	def _weights(self):
		result = {}
		book = self.book
		for category in self.categories.values():
			for name, value in category.items.items():
				entry = book.getEntryByAssignment(name, check_name=True)
				result[entry.assignmentId] = value.weight * category.weight
		return result

	@Lazy
	def _schemes(self):
		result = {}
		book = self.book
		for category in self.categories.values():
			for name, value in category.items.items():
				entry = book.getEntryByAssignment(name, check_name=True)
				scheme = value.scheme or category.scheme or self.scheme
				result[entry.assignmentId] = scheme
		return result

	def grade(self, principal):
		result = 0
		book = self.book
		username = IPrincipal(principal).id
		for grade in book.iter_grades(username):
			weight = self._weights.get(grade.AssignmentId)
			if IExcusedGrade.providedBy(grade):
				result += weight
				continue
			value = grade.value
			scheme = self._schemes.get(grade.AssignmentId)
			correctness = self.to_correctness(value, scheme)
			result += correctness * weight
		return result
