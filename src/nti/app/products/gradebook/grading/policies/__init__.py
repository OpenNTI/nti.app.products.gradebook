#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.deprecation import deprecated

from persistent import Persistent

from nti.app.products.gradebook.grading.policies.simple import SimpleTotalingGradingPolicy

from nti.app.products.gradebook.grading.policies.trytten import CategoryGradeScheme
from nti.app.products.gradebook.grading.policies.trytten import CS1323EqualGroupGrader
from nti.app.products.gradebook.grading.policies.trytten import CS1323CourseGradingPolicy


deprecated('AssigmentGradeScheme', 'Use lastest implementation')
class AssigmentGradeScheme(Persistent):
    pass

import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "Moved to nti.app.products.gradebook.grading.policies.simple",
    "nti.app.products.gradebook.grading.policies.simple",
    "SimpleTotalingGradingPolicy")

zope.deferredimport.deprecatedFrom(
    "Moved to nti.app.products.gradebook.grading.policies.trytten",
    "nti.app.products.gradebook.grading.policies.trytten",
    "CategoryGradeScheme"
    "CS1323EqualGroupGrader",
    "CS1323CourseGradingPolicy")
