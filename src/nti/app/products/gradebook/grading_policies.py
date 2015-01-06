#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

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

from nti.externalization.representation import WithRepr

from nti.mimetype.mimetype import ModeledContentTypeAwareRegistryMetaclass

from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.schema import EqHash
from nti.schema.field import ValidTextLine
from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.utils.property import alias

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
class AssigmentGradeScheme(SchemaConfigured):
	__metaclass__ = ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(IAssigmentGradeScheme)

	weight = alias('Weight')
	scheme = alias('GradeScheme')
	
@interface.implementer(IDefaultCourseGradingPolicy)
class DefaultCourseGradingPolicy(SchemaConfigured):
	__metaclass__ = ModeledContentTypeAwareRegistryMetaclass
	createDirectFieldProperties(IAssigmentGradeScheme)
	
	Items = items = alias('AssigmentGradeSchemes')

	def validate(self, context):
		pass
	
	def grade(self, principal):
		pass
