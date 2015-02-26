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

from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy
from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme as ICTGCategoryGradeScheme 

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ValidTextLine

from ..interfaces import IGradeScheme

deprecated('IAssigmentGradeScheme', 'Use lastest implementation')
class IAssigmentGradeScheme(interface.Interface):
	pass

class ICategoryGradeScheme(ICTGCategoryGradeScheme):
	GradeScheme = Object(IGradeScheme, required=False)
	DropLowest = Int(title="Drop lowest grade in category", min=0, required=False)
	LatePenalty = Number(title="Late penalty", default=1, min=0.0, max=1.0, required=True)

class ICS1323EqualGroupGrader(IEqualGroupGrader):	
	Groups = Dict(key_type=ValidTextLine(title="Category Name"),
	  			  value_type=Object(ICategoryGradeScheme, required=True),
				  min_length=1)
		
class ICS1323CourseGradingPolicy(ICourseGradingPolicy):	
	PresentationGradeScheme = Object(IGradeScheme, required=False)
	Grader = Object(ICS1323EqualGroupGrader, required=True, title="Grader")
