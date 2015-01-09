#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types
from collections import defaultdict

from zope import interface
from zope.interface import Invalid
from zope.container.contained import Contained
from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.datastructures import CreatedAndModifiedTimeMixin

from nti.externalization.representation import WithRepr

from nti.ntiids.ntiids import is_valid_ntiid_string

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

def to_correctness(value, scheme):
	value = scheme.fromUnicode(value) if isinstance(value, string_types) else value
	scheme.validate(value)
	result = scheme.toCorrectness(value)
	return result
	
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
		result = to_correctness(value, scheme)
		return result
	
def validate_assigment_grade_schemes(book, items, default_scheme=None, category=None):
	names = set()
	sum_weight = 0.0
	for name, value in items.items():
		names.add(name)
		if is_valid_ntiid_string(name):
			entry = book.getEntryByAssignment(name)
			if entry is None:
				raise Invalid("Could not find GradeBook Entry for %s", name)
		scheme = value.scheme if value.scheme else default_scheme
		if scheme is None:
			raise Invalid("Could not find grade scheme for %s", name)
		sum_weight += value.weight if value is not None else 0.0
		
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
		for name, value in self.items.items():
			scheme = value.scheme if value.scheme else self.DefaultGradeScheme
			result[name] = scheme
		return result

	@Lazy
	def _weights(self):
		result = {}
		for name, value in self.items.items():
			result[name] = value.weight
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

from zope.proxy import ProxyBase

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
	dropLowest = alias('DropLowest')
	assigments = items = alias('AssigmentGradeSchemes')
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)
	
class GradeProxy(ProxyBase):
	
	scheme = property(
			lambda s: s.__dict__.get('_v_grade_scheme'),
			lambda s, v: s.__dict__.__setitem__('_v_grade_scheme', v))
	
	weight = property(
			lambda s: s.__dict__.get('_v_grade_weight'),
			lambda s, v: s.__dict__.__setitem__('_v_grade_weight', v))
			
	def __new__(cls, base, *args, **kwargs):
		return ProxyBase.__new__(cls, base)

	def __init__(self, base, weight, scheme):
		ProxyBase.__init__(self, base)
		self.weight = weight
		self.scheme = scheme

	@property
	def correctness(self):
		result = to_correctness(self.value, self.scheme)
		return result
	
@interface.implementer(ICS1323CourseGradingPolicy)
class CS1323CourseGradingPolicy(BaseGradingPolicy):
	
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(ICS1323CourseGradingPolicy)
	
	scheme = alias('DefaultGradeScheme')
	categories = alias('CategoryGradeSchemes')

	def validate(self):
		book = self.book
		sum_weight = 0.0
		assigments = set()

		# validate categories
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
	def _rev_categories(self):
		result = {}
		for name, category in self.categories.items():
			result.update({x:name for x in category.AssigmentGradeSchemes.keys()})
		return result
		
	@Lazy
	def _weights(self):
		result = {}
		for category in self.categories.values():
			for name, value in category.items.items():
				result[name] = value.weight * category.weight
		return result

	@Lazy
	def _schemes(self):
		result = {}
		for category in self.categories.values():
			for name, value in category.items.items():
				scheme = value.scheme or category.scheme or self.scheme
				result[name] = scheme
		return result

	def _grade_map(self, username):
		result = defaultdict(list)
		
		# parse all grades and bucket them by category
		for grade in self.book.iter_grades(username):
			assignmentId = grade.AssignmentId
			weight = self._weights[assignmentId]
			scheme = self._schemes[assignmentId]
			cat_name = self._rev_categories[assignmentId]
			result[cat_name].append(GradeProxy(grade, weight, scheme))
		
		# sort by correctness
		for name in result.keys():
			result[name].sort(key=lambda g: g.correctness)

		# return
		return result
		
	def grade(self, principal):
		result = 0
		username = IPrincipal(principal).id
		grade_map = self._grade_map(username)
		for name, grades in grade_map.items():
			category = self.categories[name]
			if category.DropLowest:
				grades = grades[1:]
			for grade in grades:
				weight = grade.weight
				if IExcusedGrade.providedBy(grade):
					result += weight
					continue
				correctness = grade.correctness
				result += correctness * weight
		return result
