#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

from nti.app.products.gradebook.interfaces import IGradeScheme

from nti.contenttypes.courses.grading.interfaces import INullGrader
from nti.contenttypes.courses.grading.interfaces import IEqualGroupGrader
from nti.contenttypes.courses.grading.interfaces import ICategoryGradeScheme as IBaseCategoryGradeScheme

from nti.schema.field import Int
from nti.schema.field import Dict
from nti.schema.field import Object
from nti.schema.field import ValidTextLine


class ICategoryGradeScheme(IBaseCategoryGradeScheme):
    GradeScheme = Object(IGradeScheme, required=False)
    DropLowest = Int(title="Drop lowest grade in category",
                     min=0,
                     required=False)


class ICS1323EqualGroupGrader(IEqualGroupGrader):
    Groups = Dict(key_type=ValidTextLine(title="Category Name"),
                  value_type=Object(ICategoryGradeScheme, required=True),
                  min_length=1)


class ICS1323CourseGradingPolicy(IGradeBookGradingPolicy):
    Grader = Object(ICS1323EqualGroupGrader, required=True, title="Grader")


class ISimpleTotalingGradingPolicy(IGradeBookGradingPolicy):
    Grader = Object(INullGrader, required=False, title="Grader")
