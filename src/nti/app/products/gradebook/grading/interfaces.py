#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.deprecation import deprecated

from nti.app.products.gradebook.interfaces import IGradeScheme

from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy
from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme as ICTGCategoryGradeScheme

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import Object
from nti.schema.field import ValidTextLine

deprecated('IAssigmentGradeScheme', 'Use lastest implementation')
class IAssigmentGradeScheme(interface.Interface):
	pass

class IGradeBookGradingPolicy(ICourseGradingPolicy):

	PresentationGradeScheme = Object(IGradeScheme, required=False)

	def verify(gradebook=None):
		pass

	def grade(principal, verbose=False):
		pass

class ICategoryGradeScheme(ICTGCategoryGradeScheme):
	GradeScheme = Object(IGradeScheme, required=False)
	DropLowest = Int(title="Drop lowest grade in category", min=0, required=False)

class ICS1323EqualGroupGrader(IEqualGroupGrader):
	Groups = Dict(key_type=ValidTextLine(title="Category Name"),
	  			  value_type=Object(ICategoryGradeScheme, required=True),
				  min_length=1)

class ICS1323CourseGradingPolicy(IGradeBookGradingPolicy):
	Grader = Object(ICS1323EqualGroupGrader, required=True, title="Grader")
