#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.deprecation import deprecated

from persistent import Persistent

# [re]/export for BWC
from nti.app.products.gradebook.grading.policies.simple import SimpleTotalingGradingPolicy

# [re]/export for BWC
from nti.app.products.gradebook.grading.policies.trytten import CategoryGradeScheme
from nti.app.products.gradebook.grading.policies.trytten import CS1323EqualGroupGrader
from nti.app.products.gradebook.grading.policies.trytten import CS1323CourseGradingPolicy


deprecated('AssigmentGradeScheme', 'Use lastest implementation')
class AssigmentGradeScheme(Persistent):
    pass
