#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import component
from zope import interface
from zope.interface import Invalid
from zope.container.contained import Contained

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

def find_grading_policy_for_course(course):
	# We need to actually be registering these as annotations
	policy = ICourseGradingPolicy(course, None)
	if policy is not None:
		return policy

	registry = component
	try:
		# Courses may be ISites 
		registry = course.getSiteManager()
		names = ('',)
	except LookupError:
		# try content pacakges
		names = [x.ntiid for x in course.ContentPackageBundle.ContentPackages]
		# try catalog entry
		cat_entry = ICourseCatalogEntry(course, None)
		if cat_entry:
			names.append(cat_entry.ntiid)
			names.append(cat_entry.ProviderUniqueID)

	for name in names:
		try:
			return registry.getUtility(ICourseGradingPolicy, name=name)
		except LookupError:
			pass
	return None

from zope.security.interfaces import IPrincipal

from persistent import Persistent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.representation import WithRepr

from nti.mimetype.mimetype import ModeledContentTypeAwareRegistryMetaclass

from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.schema import EqHash
from nti.schema.field import ValidTextLine
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.utils.property import alias, Lazy

from .interfaces import IGradeBook
from .interfaces import IGradeScheme

class IAssigmentGradeScheme(interface.Interface):
	GradeScheme = Object(IGradeScheme, required=False, title="Grade scheme")
	Weight = Number(title="Grade weight", default=0.0, min=0.0, max=1.0)
	
class IDefaultCourseGradingPolicy(ICourseGradingPolicy):
	DefaultGradeScheme = Object(IGradeScheme, required=False)
	AssigmentGradeSchemes = Dict(key_type=ValidTextLine(title="Assigment ID/Name"),
								 value_type=Object(IAssigmentGradeScheme))
	
@interface.implementer(IAssigmentGradeScheme)
@WithRepr
@EqHash('GradeScheme', 'Weight')
class AssigmentGradeScheme(Persistent, SchemaConfigured):
	__metaclass__ = ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(IAssigmentGradeScheme)

	weight = alias('Weight')
	scheme = alias('GradeScheme')
	
	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__()
		SchemaConfigured.__init__(self, *args, **kwargs)
	
@interface.implementer(IDefaultCourseGradingPolicy)
class DefaultCourseGradingPolicy(Persistent, SchemaConfigured, Contained):
	__metaclass__ = ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(IAssigmentGradeScheme)
	
	items = alias('AssigmentGradeSchemes')

	def __init__(self, *args, **kwargs):
		# SchemaConfigured is not cooperative
		Persistent.__init__()
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
			value = grade.value
			weight = self._weights.get(grade.AssignmentId)
			scheme = self._schemes.get(grade.AssignmentId)
			correctness = self._to_correctness(value, scheme)
			result += correctness * weight
		return result
