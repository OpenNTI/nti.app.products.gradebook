#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from six import string_types
from datetime import datetime
from collections import defaultdict

from zope import component
from zope import interface
from zope.interface import Invalid
from zope.container.contained import Contained
from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.datastructures import CreatedAndModifiedTimeMixin

from nti.externalization.representation import WithRepr

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.schema.schema import EqHash
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.utils.property import Lazy, readproperty
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
	
class GradeProxy(object):
	
	def __init__(self, value, weight, scheme, excused=False, penalty=0.0):
		self.value = value
		self.weight = weight
		self.scheme = scheme
		self.excused = excused
		self.penalty = penalty

	@readproperty
	def correctness(self):
		try:
			result = to_correctness(self.value, self.scheme)
			result = result * (1 - self.penalty)
		except (ValueError, TypeError):
			logger.error("Invalid value %s for grade scheme %s", self.value, self.scheme)
			result = 0
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
	@Lazy
	def _dateContext(self):
		context = self.__parent__
		result = IQAssignmentDateContext(ICourseInstance(context, None), None)
		return result
		
	def synchronize(self):
		pass

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
		
		if value is None:
			raise Invalid("No AssigmentGradeScheme object defined for %s", name)
		
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
	
	if round(sum_weight, 2) > 1:
		if category:
			msg = "Total weight for category %s is greater than to one" % category
		else:
			msg = "Total weight in policy is greater than one"
		raise Invalid(msg)
	return names
		
@interface.implementer(IAssigmentGradeScheme)
@WithRepr
@EqHash('GradeScheme', 'Weight')
class AssigmentGradeScheme(Persistent, SchemaConfigured):
	
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(IAssigmentGradeScheme)
	
	LatePenalty = 1
	
	weight = alias('Weight')
	scheme = alias('GradeScheme')
	penalty = alias('LatePenalty')
	
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
	
	def _grades(self, username):
		result = []
		entered = set()	
	
		# parse all grades
		for grade in self.book.iter_grades(username):
			# save grade info
			value = grade.value 
			assignmentId = grade.AssignmentId
			weight = self._weights[assignmentId]
			scheme = self._schemes[assignmentId]
			excused = IExcusedGrade.providedBy(grade)
			# record grade
			entered.add(assignmentId)
			result.append(GradeProxy(value, weight, scheme, excused))
		
		# now create proxy grades with 0 correctes for missing ones
		for assignmentId in self.items.keys():
			if assignmentId not in entered:
				weight = self._weights[assignmentId]
				scheme = self._schemes[assignmentId]
				proxy = GradeProxy(0, weight, scheme)
				proxy.correctness = 0.0
				result.append(proxy)

		# return
		return result
	
	def grade(self, principal):
		result = 0
		username = IPrincipal(principal).id		
		for grade in self._grades(username):
			weight = grade.weight
			if grade.excused:
				result += weight
				continue
			correctness = grade.correctness
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

	LatePenalty = 1
		
	weight = alias('Weight')
	scheme = alias('GradeScheme')
	penalty = alias('LatePenalty')
	dropLowest = alias('DropLowest')
	assigments = items = alias('AssigmentGradeSchemes')
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__(self)
		SchemaConfigured.__init__(self, *args, **kwargs)
		
	def __len__(self):
		return len(self.assigments)
	
	def __getitem__(self, key):
		return self.assigments[key]

	def __iter__(self):
		return iter(self.assigments)
	
@interface.implementer(ICS1323CourseGradingPolicy)
class CS1323CourseGradingPolicy(BaseGradingPolicy):
	
	__metaclass__ = MetaGradeBookObject
	createDirectFieldProperties(ICS1323CourseGradingPolicy)
	
	PresentationGradeScheme = None
	
	scheme = alias('DefaultGradeScheme')
	categories = alias('CategoryGradeSchemes')
	presentation = alias('PresentationGradeScheme')

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
			sum_weight += category.Weight
		
		if round(sum_weight, 2) > 1:
			msg = "Total category weight in policy is greater than one"
			raise Invalid(msg)
		
		if len(self._rev_categories) != len(assigments):
			raise Invalid("There are assigments assigned to multiple categories")

	@Lazy
	def _total_weight(self):
		result = 0
		for category in self.categories.values():
			result += category.Weight
		return result

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

	@Lazy
	def _penalties(self):
		result = {}
		for category in self.categories.values():
			for name, value in category.items.items():
				penalty = value.penalty if value.penalty is not None else category.penalty
				result[name] = 0 if penalty is None else penalty
		return result
	
	def _is_late(self, assignmentId, now=None):
		dates = self._dateContext
		now = now or datetime.utcnow() 
		assignment = component.queryUtility(IQAssignment, name=assignmentId)
		if assignment is not None and dates is not None:
			_ending = dates.of(assignment).available_for_submission_ending
			return bool (_ending and now > _ending)
		return False
	
	def _grade_map(self, username):
		now = datetime.utcnow() 
		result = defaultdict(list)
		entered = defaultdict(set)	
		
		# parse all grades and bucket them by category
		for grade in self.book.iter_grades(username):
			assignmentId = grade.AssignmentId
				
			# save grade info
			value = grade.value 
			if value is None:
				logger.info("No grade entered for %s", assignmentId)
				continue

			weight = self._weights.get(assignmentId)
			if not weight:
				logger.error("Incomplete policy, no weight found for %s", assignmentId)
				continue
			
			scheme = self._schemes.get(assignmentId)
			if not scheme:
				logger.error("Incomplete policy, no grading scheme found for %s",
							 assignmentId)
				continue
			
			excused = IExcusedGrade.providedBy(grade)
			penalty = self._penalties.get(assignmentId, 0) \
					  if self._is_late(assignmentId, now) else 0
		
			# record grade
			cat_name = self._rev_categories[assignmentId]
			result[cat_name].append(GradeProxy(value, weight, scheme, excused, penalty))
			entered[cat_name].add(assignmentId)
		
		# now create proxy grades with 0 correctes for missing ones
		# that we know about in the policy
		for cat_name, category in self.categories.items():
			inputed = entered[cat_name]
			assignments = set(category.items.keys())
			for assignmentId in assignments.difference(inputed):
				
				# we assume the assigment is correct
				correctness = 1
				weight = self._weights.get(assignmentId)
				scheme = self._schemes.get(assignmentId)
				
				# check if the assigment is late
				if self._is_late(assignmentId, now):
					penalty = self._penalties.get(assignmentId, 0)
					correctness = 1 - penalty
						
				# create proxy grade
				proxy = GradeProxy(0, weight, scheme)
				proxy.correctness = correctness
				result[cat_name].append(proxy)
			
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
			
			# drop lowest grades in the category
			# make sure we don't drop excused grades
			if category.DropLowest:
				idx = count = 0
				while count < category.DropLowest and idx < len(grades):
					grade = grades[idx]
					if not grade.excused:
						result += grade.weight
						grades.pop(idx)
						count += 1
					else:
						idx += 1		
						
			# go through remaining grades
			for grade in grades or ():
				weight = grade.weight
				if grade.excused:
					result += weight
					continue
				correctness = grade.correctness
				result += correctness * weight
		
		# divide over the total weight in case the policy
		# is not complete
		result = result / self._total_weight
		return round(result, 2)

	def __len__(self):
		return len(self.categories)
	
	def __getitem__(self, key):
		return self.categories[key]
	
	def __iter__(self):
		return iter(self.categories)
