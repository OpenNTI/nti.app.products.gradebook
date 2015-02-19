#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division


__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.interface.common.mapping import IItemMapping
from zope.interface.common.sequence import IFiniteSequence

from dolmen.builtins.interfaces import IIterable

from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ValidTextLine

from ..interfaces import IGradeScheme

class IAssigmentGradeScheme(interface.Interface):
	GradeScheme = Object(IGradeScheme, required=False, title="Grade scheme")
	Weight = Number(title="Grade weight", default=0.0, min=0.0, max=1.0, required=False)
	LatePenalty = Number(title="Late penalty", default=1, min=0.0, max=1.0, required=True)
	
class IDefaultCourseGradingPolicy(ICourseGradingPolicy):
	DefaultGradeScheme = Object(IGradeScheme, required=False)
	AssigmentGradeSchemes = Dict(key_type=ValidTextLine(title="Assigment ID/Name"),
								 value_type=Object(IAssigmentGradeScheme),
								 min_length=1)

class ICategoryGradeScheme(	interface.Interface, 
							IIterable, IFiniteSequence, IItemMapping):
	GradeScheme = Object(IGradeScheme, required=False)
	Weight = Number(title="Category weight", default=0.0, min=0.0, max=1.0, required=True)
	AssigmentGradeSchemes = Dict(key_type=ValidTextLine(title="Assigment ID/Name"),
								 value_type=Object(IAssigmentGradeScheme, required=False),
								 min_length=1)
	DropLowest = Int(title="Drop lowest grade in category", min=0, required=False)
	LatePenalty = Number(title="Late penalty", default=1, min=0.0, max=1.0, required=True)
	
class ICS1323CourseGradingPolicy(ICourseGradingPolicy,
								 IIterable, IFiniteSequence, IItemMapping):
	DefaultGradeScheme = Object(IGradeScheme, required=False)
	PresentationGradeScheme = Object(IGradeScheme, required=False)
	CategoryGradeSchemes = Dict(key_type=ValidTextLine(title="Category Name"),
					  			value_type=Object(ICategoryGradeScheme),
					  			min_length=1)
