#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.contenttypes.courses.interfaces import ICourseGradingPolicy

from nti.schema.field import Dict
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import ValidTextLine

from ..interfaces import IGradeScheme

class IAssigmentGradeScheme(interface.Interface):
	GradeScheme = Object(IGradeScheme, required=False, title="Grade scheme")
	Weight = Number(title="Grade weight", default=0.0, min=0.0, max=1.0)
	
class IDefaultCourseGradingPolicy(ICourseGradingPolicy):
	DefaultGradeScheme = Object(IGradeScheme, required=False)
	AssigmentGradeSchemes = Dict(key_type=ValidTextLine(title="Assigment ID/Name"),
								 value_type=Object(IAssigmentGradeScheme))
