#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,arguments-differ

from zope import interface

from zope.deprecation import deprecated

from nti.app.products.gradebook.interfaces import IGradeScheme

from nti.contenttypes.courses.grading.interfaces import ICourseGradingPolicy

from nti.schema.field import Object


deprecated('IAssigmentGradeScheme', 'Use lastest implementation')
class IAssigmentGradeScheme(interface.Interface):
    pass


class IGradeBookGradingPolicy(ICourseGradingPolicy):

    PresentationGradeScheme = Object(IGradeScheme, required=False)

    def verify(gradebook=None):
        """
        verify this policy.

        :returns True if the policy is valid
        """

    def grade(principal, verbose=False):
        pass


import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "Moved to nti.app.products.gradebook.grading.policies.interfaces",
    "nti.app.products.gradebook.grading.policies.interfaces",
    "ICategoryGradeScheme",
    "ICS1323EqualGroupGrader",
    "ICS1323CourseGradingPolicy",
    "ISimpleTotalingGradingPolicy")
